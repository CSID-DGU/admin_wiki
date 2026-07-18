# Kerberos/NFS

> 역할: FARM/LAB에서 AD Kerberos로 사용자를 인증하고, 같은 UID/GID로 NFS
> 공유 스토리지에 접근하게 하는 구조와 운영 기준을 설명한다.

이 문서는 Kerberos/NFS 문서의 시작점이다. 처음 읽는 사람은 **설계**에서 전체
인증 흐름을 먼저 이해한 뒤 **운영**에서 생성·점검·복구 명령을 확인한다. 과거
장애의 증거와 재현 실험은 **디버깅 로그**에서 확인한다. 환경별 실제 값과 최종
실행 절차는 인프라 저장소의 FARM/LAB canonical runbook을 단일 기준으로 삼는다.

## 문서 구성

| 문서 | 읽어야 하는 경우 | 핵심 내용 |
| --- | --- | --- |
| 현재 페이지 | 전체 범위와 문서 위치를 빠르게 확인할 때 | 목적, 원칙, 소유 경계 |
| [설계](design.md) | 인증이 어느 서버와 프로세스를 거치는지 이해할 때 | keytab 발급, ticket 발급, RPCSEC_GSS, NAS 권한 판정, 설정 근거 |
| [운영](operations.md) | 계정/컨테이너 생성, timer 확인, mount·KVNO 장애를 처리할 때 | 명령, 점검표, 모니터링 코드, 수동 repair/rotation |
| [디버깅 로그](debugging/index.md) | 재현된 장애의 원인과 실험 조건·명령·증거를 확인할 때 | 장애별 증상, 가설, 재현, 판정, 복구·예방 |

## 한눈에 보는 구조

```text
관리 서버(uidctl)
  ├─ AD DC: 사용자·RFC2307·keytab 생성
  ├─ 계산 호스트: root-only keytab + ccache refresh timer
  ├─ NAS/storage: NFS service keytab + 사용자 home
  └─ container: keytab이 아닌 ccache만 사용

사용자 I/O
  container process -> host kernel NFS client -> rpc.gssd
  -> AD KDC ticket -> NAS svcgssd/NFS -> UID/GID 권한 판정
```

현재 구현의 중요한 경계는 다음과 같다.

- 사용자 keytab은 장기 자격증명이므로 계산 호스트의
  `/etc/decs-krb/keytabs/<username>.keytab`에 `root:root 0400`으로만 둔다.
- 컨테이너에는 keytab을 넣지 않는다. 호스트가 만든
  `/run/user/<uid>/krb5cc`와 읽기 전용 `/etc/krb5.conf`만 bind mount한다.
- 컨테이너가 시작되기 전에 사용자별 `decs-krb-refresh@<username>.timer`를
  활성화하고 유효한 ccache를 한 번 발급한다.
- NFS mount source는 IP가 아니라 NFS service principal과 일치하는 FQDN을 쓴다.
  FARM의 source는 `nas.farm.decs.internal:/volume1/share`다.
- `addr=100.100.100.120`은 FQDN이 해석된 실제 전송 주소로 사용할 수 있다.
  source 자체를 `100.100.100.120:/...`로 바꾸면 안 된다.
- 기본 security flavor는 `sec=krb5`다. `krb5i`와 `krb5p`는 무결성·암호화가
  명시적으로 필요한 경로에서 성능 비용과 함께 선택한다.

## Identity 불변 조건

한 사용자에 대해 다음 숫자가 같아야 한다.

```text
UID DB ubuntu_uid
 = AD RFC2307 uidNumber
 = NFS client에서 관측한 home owner UID
 = container UID

primary GID도 같은 원칙 적용
```

이 조건을 확인하지 않고 NAS에서 `chown`만 반복하면 AD, DB, NAS의 identity가
더 어긋날 수 있다. 계정 생성 흐름은 Docker와 DB를 확정하기 전에 AD/NAS/host
identity와 실제 Kerberos NFS 쓰기를 검증한다.

## 모듈 소유 경계

| 작업 | 소유 모듈 |
| --- | --- |
| AD 사용자·그룹, 사용자 keytab, host ccache timer, container 생성 | `user-lifecycle` |
| 공통 host Kerberos/NFS desired state와 fstab | `server-state` |
| NAS NFS service account·SPN·service keytab의 수동 변경 | `kerberos-nfs` |
| GSS readiness, keytab drift 관측, mount 상태, canary, forensics | `monitoring` |
| ccache 소비, 시작 전 credential 확인, restricted sudo | `container-images` |

관측 실패가 곧바로 AD password 변경이나 NAS service 재시작으로 이어지지 않게
읽기 전용 monitoring과 상태 변경 작업을 분리한다.

## 단일 기준 문서와 코드

- [FARM canonical runbook](https://github.com/CSID-DGU/admin_infra_server/blob/main/kerberos-nfs/docs/farm.md)
- [LAB canonical runbook](https://github.com/CSID-DGU/admin_infra_server/blob/main/kerberos-nfs/docs/lab.md)
- [user-lifecycle Kerberos 구현](https://github.com/CSID-DGU/admin_infra_server/tree/main/user-lifecycle/script/uid_manager/kerberos)
- [container 생성 구현](https://github.com/CSID-DGU/admin_infra_server/blob/main/user-lifecycle/script/uid_manager/services/create_container.py)
- [host Kerberos/NFS desired state](https://github.com/CSID-DGU/admin_infra_server/blob/main/server-state/ansible_playbook/kerberos_nfs_client_recovery.yml)
- [Kerberos/NFS keytab health check](https://github.com/CSID-DGU/admin_infra_server/tree/main/monitoring/health-checks/kerberos-nfs-keytab)
- [NFS GSS monitoring](https://github.com/CSID-DGU/admin_infra_server/tree/main/monitoring/prometheus/exporters/cluster-monitor-exporter)

실제 endpoint, principal, mount option이 바뀌면 이 위키보다 canonical runbook과
코드 설정을 먼저 갱신하고, 검증 시각과 대상 host를 함께 기록한다.
