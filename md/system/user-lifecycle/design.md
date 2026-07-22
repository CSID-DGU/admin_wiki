# user-lifecycle 설계

> [개요](index.md) · [운영](operations.md)

> 역할: 사용자 identity, 그룹, 포트, 컨테이너와 개인 Kerberos/NFS 준비를 하나의 생명주기로 관리한다.

## 1. 이 모듈이 중심인 이유

DECS 사용자 컨테이너는 Docker object 하나가 아니다. 다음 자원이 서로 같은
identity와 상태를 가져야 하는 분산 작업이다.

- 도메인별 UID MySQL의 사용자, 그룹, 예약 ID, container와 port record
- FARM/LAB target host의 Docker container
- NAS 또는 LAB storage의 사용자 home
- 선택적인 AD RFC2307 user/group과 membership
- host의 root-only user keytab과 ccache refresh timer
- 생성·삭제·연장 안내 메일, DB backup과 Excel export

`user-lifecycle`는 이 자원의 순서와 실패 처리를 소유한다. 다른 모듈이 DB에
직접 쓰거나 container 생성 규칙을 복제하면 UID, 포트와 실제 Docker 상태가
어긋나므로 공개 `uidctl` CLI를 통과하는 것이 원칙이다.

## 2. 디렉터리 지도

| 경로 | 상태 | 핵심 기능 |
| --- | --- | --- |
| `script/uid_manager/` | primary | Python CLI, model, DB, service 구현 |
| `script/uid_manager/services/` | primary | create/delete/extend/sync/cleanup/group use case |
| `script/uid_manager/kerberos/` | primary | AD, keytab, ccache, NFS 검증 명령과 path 생성 |
| `script/ansible_playbook/` | primary | storage/NAS home과 host Kerberos identity 준비 |
| `script/tests/` | primary | fake runner/repository 기반 회귀 테스트 |
| `config/*.example.*` | template | DB, email, maintenance, GPU profile, Google, admin 설정 구조 |
| `config/*.local.*` | secret/local | 실제 credential과 운영 override; Git 제외 |
| `server_info/servers.jsonl` | shared authority | FARM/LAB 서버 주소와 SSH/NAT port inventory |
| `nfs_mysql/` | data layer | MySQL image, schema와 server config |
| `docker-compose.yml` | data layer | local UID DB service/volume |
| `maintenance/` | utility | 사용자 삭제, email CSV 갱신, schema migration 등 관리 작업 |
| `ad_backup/` | operations | AD backup 생성·검증과 timer 설치 |
| `legacy/` | compatibility | 이전 shell 구현; 신규 기능의 기준이 아님 |
| `excel_exports/` | generated | 사용자 export 결과, source가 아님 |

`legacy/`를 즉시 삭제하지 않은 이유는 기존 운영 절차의 비교·복구 근거가
필요하기 때문이다. 그러나 새 비즈니스 규칙은 Python service에 추가하고
테스트 가능하게 유지한다.

## 3. 코드 구조

### CLI와 service 분리

`uid_manager/cli.py`는 argument parsing, config/repository 생성과 결과 출력만
담는다. 실제 규칙은 service class가 소유한다.

| CLI | Service | 기능 |
| --- | --- | --- |
| `create-container` | `ContainerCreateService` | identity/port/GPU profile 결정, storage/Kerberos, Docker, DB transaction |
| `delete-container` | `ContainerDeleteService` | 대상 단일화, Docker 삭제, DB 비활성화/port 정리 |
| `extend-container` | `ContainerExtendService` | 만료일 검색·변경과 알림 |
| `expired-cleanup` | `ExpiredCleanupService` | 만료 대상 계획 또는 실제 정리 |
| `sync-containers` | `ContainerSyncService` | DB record와 local Docker 상태 비교·재생성 계획 |
| `manage-group` | `GroupManagementService` | AD/DB group과 membership 관리 |

이 분리는 CLI 외의 timer/test에서도 동일한 규칙을 호출하고, fake repository와
recording runner로 production 접속 없이 계획을 검증하기 위한 것이다.

### Port와 runner 추상화

`LocalRunner`와 `AnsibleRunner`는 subprocess와 원격 shell/playbook 호출을
한 곳에 모은다. `RecordingRunner`는 실행 대신 command를 기록한다.
`PortMapping`은 host port, container port와 purpose를 함께 보존하여 단순 문자열
port가 SSH/Jupyter/VNC 중 무엇인지 잃지 않게 한다.

`OperationPlan`은 facts, 단계와 명령을 렌더링한다. `--dry-run`이 실제 실행
경로와 같은 준비 로직을 통과하므로 문서용 예상 명령과 실제 입력 검증이
달라지는 것을 줄인다.

## 4. 데이터 모델과 권위

MySQL schema의 주요 관계:

```text
used_ids ---- group
    |           |
    +-------- user ---- user_group_membership
                 |
                 +---- user_kerberos_identity
                 |
                 +---- docker_container ---- used_ports
```

| 데이터 | 의미 |
| --- | --- |
| `used_ids` | UID/GID 숫자의 전역 예약 |
| `group` | group 이름과 GID |
| `user` | 실명, username, UID/GID, 연락처 |
| `user_group_membership` | supplemental/primary group 관계 |
| `user_kerberos_identity` | AD realm/SID/RFC2307과 최근 NAS/NFS 관측값 |
| `docker_container` | image, server, GPU profile, 만료, 생성자와 활성 상태 |
| `used_ports` | host port, 용도와 container record 연결 |

foreign key와 unique index를 쓰는 이유는 application 검증만으로 막기 어려운
중복 UID/GID, container와 port 충돌을 DB에서도 거부하기 위해서다. FARM과
LAB은 DB endpoint가 다를 수 있으므로 `AppConfig`가 domain별 host를 선택한다.

## 5. Container 생성 흐름

### 5.1 준비와 identity 채택

`ContainerCreateService.prepare()`는 이름, domain/server, 날짜, image와 port를
검증한 뒤 UID/GID source를 결정한다. 신규 사용자의 UID 우선순위는 다음과
같다.

1. DB에 기존 사용자가 있으면 DB UID/GID
2. 운영자가 명시한 `--uid`/`--gid`
3. Kerberos 모드에서 기존 AD RFC2307 identity
4. 기존 storage home의 숫자 owner
5. 모두 없으면 DB의 다음 사용 가능한 ID

기존 자원을 무조건 새 ID로 덮지 않고 채택하는 이유는 이미 소유권이 있는 NFS
home이나 AD object를 고아로 만들지 않기 위해서다. 여러 source가 서로 다른
값을 말하면 자동 보정하지 않고 validation error로 중단한다.

port는 DB 예약과 실제 target host Docker publish port를 함께 확인한다.
기본 SSH/Jupyter, 선택적 VNC와 추가 container port를 배정하거나
`--fixed-port-mappings`로 host:container[:purpose]를 명시할 수 있다.

같은 단계에서 GPU profile도 결정된다. 여러 GPU 모델이 섞여 있는 서버(현재는
`GPU_PROFILE_REQUIRED_SERVERS`에 등록된 LAB5만 해당)는 `--gpu-profile`로 사용할
GPU 묶음을 선택해야 한다. `AppConfig.resolve_gpu_profile()`이
`config/gpu_profiles.local.json` 카탈로그에서 서버별 profile 이름(예: `a6000`,
`pro5000`)을 실제 GPU UUID 목록으로 바꾸고, 이 값이 나중에 Docker 실행 시
`--gpus device=<uuid,...>`로 전달된다. 카탈로그에 없는 서버는 GPU 종류가
하나뿐이라고 보고 기본값 `all`(모든 GPU 노출)을 쓴다. 선택된 profile 이름은
`docker_container.gpu_profile`에 저장되어, 이후 `sync-containers`가 DB와 실제
Docker `--gpus` 설정의 drift를 비교하는 기준이 된다.

### 5.2 실행 순서

```text
입력 검증과 OperationPlan
        |
        v
target image inspect/pull
        |
        v
storage home + optional AD/keytab/ccache 준비
        |
        v
NSS/idmap/실제 NFS write 검증
        |
        v
docker run + inspect/port 검증
        |
        v
DB user/group/identity/container/port 단일 transaction
        |
        v
email + DB backup + export
```

storage와 Kerberos write 검증을 Docker/DB 확정 전에 두는 이유는 사용자가
로그인했지만 home에 쓸 수 없는 반쪽 container를 만들지 않기 위해서다.
Docker 생성 뒤 DB write는 한 transaction으로 묶는다. DB 단계가 실패하면
transaction을 rollback하고 방금 만든 container 정리를 시도하여 실제 상태와
record가 갈라지는 시간을 줄인다.

`--no-db-record`는 특수 검증용으로 Docker를 만들되 DB user/group/container/port
write를 생략한다. 일반 운영 생성에는 사용하지 않는다. DB에 없는 container는
GPU user attribution, 만료 정리와 sync에서 정상 관리 대상이 아니기 때문이다.

### 5.3 domain별 storage

일반 LAB root_squash 경로는 storage server에서 실제 export home을 만들고
선택한 UID/GID로 owner를 설정한 뒤, target host에 mount된
`/home/tako<N>/share/user-share`를 container `/home`에 bind한다.

FARM은 NAS의 user-share 구조를 사용한다. Kerberos가 아닌 모드도 target
host root가 NFS root_squash 때문에 직접 owner를 바꾸려 하지 않고 storage/NAS
소유 playbook을 통해 준비한다.

## 6. Kerberos 활성화 흐름

### 6.1 공통 보안 모델

```text
AD user/private group + RFC2307
        |
        v
root-only keytab on target host
        |
        v
systemd refresh -> /run/user/<uid>/krb5cc
        |
        v
container receives ccache only
```

사용자 password를 DB나 container에 저장하지 않는다. AD에서 keytab을 export한
뒤 target host의 `/etc/decs-krb/keytabs/`에 mode `0400`으로 설치한다. refresh
service는 ticket을 renew하거나 만료 여유가 부족하면 keytab으로 재발급하고,
container에는 ccache만 전달한다.

keytab rotation은 `--rotate-kerberos-keytab`처럼 명시적으로 요청한다. 정상
container 재생성이나 만료 연장이 credential rotation을 뜻하지 않게 하기
위해서다.

### 6.2 FARM

FARM 흐름은 AD user/group과 RFC2307을 보장하고 NAS mapping과 home을 준비한
뒤 target host에서 해당 UID와 ccache로 실제 NFS write를 수행한다.

공유 NAS GSS/idmap service restart는 기본적으로 꺼져 있다. 새 identity의
cache 문제가 의심되더라도 NAS service 재시작은 모든 client의 GSS context를
끊을 수 있으므로 명시적 유지보수 옵션으로만 허용한다.

### 6.3 LAB

LAB Kerberos PoC/지원 흐름은 LAB Samba AD, storage의 전용 Kerberos export,
target host의 NSS/idmap과 NFSv4.1을 함께 확인한다. storage와 client의 NFSv4
idmap domain이 다르면 owner가 `nobody`로 보이거나 `chgrp`가 실패할 수 있다.
따라서 ticket 성공만으로 완료하지 않고 숫자 owner와 실제 write를 검증한다.

### 6.4 DB에 남기는 Kerberos 정보

DB에는 password/keytab이 아니라 다음 비밀이 아닌 identity metadata만 둔다.

- AD username, realm, NetBIOS domain
- domain/object SID
- AD `uidNumber`, `gidNumber`
- 최근 NAS internal UID/GID
- 최근 NFS에서 본 UID/GID와 검증 시각

SID와 최근 관측값을 보존하면 같은 username이 재생성되었거나 mapping이
달라진 상황을 단순 문자열 일치보다 안전하게 발견할 수 있다.
