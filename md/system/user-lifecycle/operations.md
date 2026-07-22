# user-lifecycle 운영

> [개요](index.md) · [설계](design.md)

## 1. 주요 CLI 사용법

설치/실행 위치:

```bash
cd /home/jy/server_manage/user-lifecycle/script
python3 -m pip install -e .
uidctl --help
```

### 생성 dry-run

```bash
uidctl create-container \
  --name '홍길동' \
  --username hong \
  --server-id FARM8 \
  --expiration-date 2026-12-31 \
  --image decs \
  --version cuda12.5-tf2.20-ubuntu22.04-260706 \
  --created-by admin \
  --email hong@example.org \
  --phone 000-0000-0000 \
  --dry-run
```

Kerberos/VNC는 필요할 때 명시한다.

```bash
uidctl create-container ... --enable-kerberos --enable-vnc --dry-run
```

GPU 모델이 여러 종류인 서버(현재는 LAB5)는 `--gpu-profile`로 사용할 GPU
묶음을 선택한다. 생략하면 서버의 기본 profile이 쓰이고, 그 서버가
`GPU_PROFILE_REQUIRED_SERVERS`에 등록되어 있는데 카탈로그에 없는 profile을
요청하면 오류로 중단된다.

```bash
uidctl create-container ... \
  --server-id LAB5 \
  --gpu-profile a6000 \
  --dry-run
```

### 삭제

DB record 검색 조건으로 대상이 하나인지 먼저 확인하고 dry-run한다.

```bash
uidctl delete-container \
  --server-id FARM8 \
  --container-name hong \
  --dry-run
```

### 만료 연장과 정리

연장은 기본적으로 계획만 만들고 실제 변경에 `--apply`가 필요하다.

```bash
uidctl extend-container \
  --username hong \
  --expiration-date 2027-06-30

uidctl extend-container \
  --username hong \
  --expiration-date 2027-06-30 \
  --apply
```

만료 정리도 대상 날짜와 domain을 제한해 먼저 dry-run한다.

```bash
uidctl expired-cleanup \
  --today 2026-07-17 \
  --domains FARM,LAB \
  --dry-run
```

### sync와 group

```bash
uidctl sync-containers --domain FARM --dry-run
uidctl manage-group show --domain FARM --group research
uidctl manage-group add-user \
  --domain FARM \
  --group research \
  --user hong \
  --dry-run
```

`--force`, `--auto-delete`, 실제 group delete는 영향 범위를 확인한 뒤 사용한다.
`sync-containers`는 DB의 `gpu_profile`과 실제 Docker `--gpus` 설정이 어긋나는
경우도 함께 찾아낸다.

## 2. 설정과 secret

공개 template:

- `config/db_config.example.env`
- `config/email_config.example.env`
- `config/daily_maintenance.example.env`
- `config/google-client.example.json`
- `config/reminder_admins.example.txt`
- `config/gpu_profiles.example.json`
- `ad_backup/config.example.env`

실제 값은 대응하는 `.local.*` 또는 ignored 운영 파일에 둔다. 문서, log,
OperationPlan과 exception에 DB password, SMTP credential, Google secret,
AD password, keytab 내용이 나타나지 않도록 command redaction을 유지한다.

`config/gpu_profiles.local.json`은 서버별 GPU profile 이름과 실제 GPU UUID
목록의 카탈로그다. `config/db_config.local.env`의 `GPU_PROFILES_FILE`이 이
파일의 경로를, `GPU_PROFILE_REQUIRED_SERVERS`가 profile 지정을 강제할
서버 목록을 정한다. GPU UUID 자체는 credential이 아니지만, 실제 서버의 GPU
구성과 어긋나면 엉뚱한 GPU가 배정되므로 하드웨어를 바꿀 때마다 함께
갱신해야 한다.

`config/network_topology.json`과 `server_info/servers.jsonl`은 secret 저장소가
아니다. 접근 경로에 필요한 주소와 port만 넣고 password/private key는 외부
SSH/Ansible 설정이 관리한다.

## 3. Post action과 생성물

성공한 생명주기 작업 뒤 `PostActions`가 이메일, DB backup과 export 도구를
호출한다. 핵심 transaction과 알림을 분리한 이유는 메일 실패가 identity/DB
일관성을 되돌리는 근거가 되지 않기 때문이다. 반대로 DB transaction이
실패했는데 성공 메일을 보내지 않도록 실행 순서는 transaction 뒤에 둔다.

`excel_exports/`, AD `backups/`, `server_info`의 생성된 raw 정보는 운영
artifact다. source code처럼 수정하거나 매뉴얼의 권위 있는 입력으로 삼지
않는다. 보존·암호화·삭제 주기는 별도 운영 정책에 따라야 한다.

## 4. 테스트

```bash
cd /home/jy/server_manage/user-lifecycle/script
python3 -m unittest discover -s tests -v
```

또는 프로젝트 test runner:

```bash
python3 tests/run_tests.py
```

중요 회귀 범위:

- 자동/고정 port 할당과 중복 거부
- DB/AD/storage 기존 identity 채택 우선순위
- GPU profile 카탈로그 해석과 필수 서버의 fail-closed 동작
- create 실패 시 DB rollback과 container cleanup
- dry-run에서 원격/DB 변경이 없는지
- FARM/LAB Kerberos command와 path 차이
- group 삭제/primary 변경의 안전 gate
- sync가 DB에 없는/멈춘 container와 GPU profile drift를 구분하는지
- command/log에서 password redaction

shell legacy test는 호환성 확인용이며 Python service test를 대체하지 않는다.

## 5. 변경 가이드

### 새 lifecycle command

1. request/result 또는 record를 `models.py`에 정의한다.
2. 비즈니스 순서를 `services/`의 class로 구현한다.
3. DB query는 `Repository` protocol과 `MySqlRepository`에 추가한다.
4. 외부 명령은 runner를 통하고 secret redaction을 적용한다.
5. CLI에는 parsing과 dependency 조립만 추가한다.
6. fake repository/runner를 사용한 dry-run, success와 partial failure test를
   작성한다.

### schema 변경

- 기존 운영 DB에 idempotent하게 적용되는 migration/ensure path를 준비한다.
  (예: `maintenance/migrate_add_gpu_profile.sql`처럼 컬럼 존재 여부를 먼저
  확인한다.)
- unique/foreign key와 기존 데이터 backfill 순서를 검토한다.
- FARM/LAB DB를 독립적으로 적용·검증한다.
- exporter가 읽는 column과 query 호환성을 `monitoring`에서 함께 확인한다.

### Kerberos 변경

- password/keytab이 DB, plan과 log에 들어가지 않는지 확인한다.
- DB, AD, NAS/NFS와 container identity 불변 조건을 test한다.
- 공유 NAS service restart를 정상 경로에 추가하지 않는다.
- 운영 policy 변경이면 `kerberos-nfs/docs/farm.md` 또는 `docs/lab.md`를 갱신한다.

## 6. 운영 안전 수칙

- 모든 destructive 명령은 domain, server와 대상 container가 하나인지 확인한다.
- 실제 생성 전 `--dry-run`의 identity source, mount, image, port와 GPU profile을
  검토한다.
- 기존 AD 또는 storage identity와 요청 UID/GID 충돌을 강제로 덮지 않는다.
- DB와 실제 Docker 상태가 어긋나면 원인을 확인하고 `sync --auto-delete`를 바로
  사용하지 않는다.
- keytab과 사용자 password를 container나 backup export에 포함하지 않는다.
- GPU profile 카탈로그가 실제 서버의 GPU 구성과 다르면 먼저 카탈로그를
  맞추고, DB의 `gpu_profile` 값을 임의로 고쳐 맞추지 않는다.
- `legacy/`를 수정해 신규 규칙을 우회하지 않는다.
- DB 없는 test container는 이름, 수명과 정리 책임을 명확히 한다.
