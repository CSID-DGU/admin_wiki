# remote-operations 설계

> [개요](index.md) · [운영](operations.md) · [설정](config.md)

> 역할: FARM/LAB 서버를 깨우고, 부팅 시 한 번 상태를 확인한 뒤 기존 컨테이너를 시작한다.

## 1. 책임 범위

`remote-operations`는 management host의 `remote-boot.service`가 실행하는
부팅 orchestration이다. Wake-on-LAN, 전체 대상 host health gate, 1회 host
health check와 container post-check를 소유한다.

주기적인 mount/GPU/container 관측은 `monitoring`에 있다. 이 경계를 나눈
이유는 부팅 시 복구와 상시 self-healing이 서로 다른 retry 정책과 장애 의미를
가지기 때문이다. 이 디렉터리에서 관리하는 systemd unit은
`remote-boot.service` 하나다.

## 2. 디렉터리 지도

| 경로 | 핵심 기능 |
| --- | --- |
| `script/run_remote_boot.sh` | 전체 부팅 흐름의 entry point |
| `script/wake_targets.sh` | target 선택과 WOL magic packet 전송 |
| `script/wait_for_priority_servers.sh` | 선택된 대상 전체의 host health gate |
| `script/check_server_boot_health.sh` | host SSH 도달성, mount, host GPU 점검 |
| `script/restart_all_remote_containers.sh` | 기존 container 시작과 SSH/GPU post-check |
| `script/create_test_container.sh` | (부팅 흐름에서 호출되지 않는 독립 도구) 임시 GPU container 생성 |
| `script/delete_test_container.sh` | (부팅 흐름에서 호출되지 않는 독립 도구) 임시 container 정리 |
| `script/common.sh` | config, target, Ansible, log, alert 공통 함수 |
| `script/install_remote_boot_service.sh` | systemd unit 설치·활성화 |
| `test/dry_run_remote_boot.sh` | WOL/health/container/full flow simulation |
| `test/integration_smoke_test.sh` | 수동 Ansible/Docker/GPU 통합 확인 |
| `test/test_slack_notification.sh` | Slack webhook 설정과 알림 발송 테스트 |
| `config/remote_boot.example.env` | 공개 가능한 설정 구조 |
| `config/remote_boot.local.env` | 실제 MAC·webhook 등을 담는 ignored 설정 |

## 3. 부팅 상태 머신

```text
pre-delay
    |
    v
wake all selected targets (동시)
    |
    v
health gate for all selected targets -- failure --> stop + alert
    |
    v
start stopped target containers
    |
    v
per-container SSH/GPU post-check
```

과거에는 `LAB1`/`FARM1`에 있는 사용자 관리 DB(사용자, UID/GID, 할당 port와
사용자 container record를 관리하는 기준 데이터)를 먼저 기동하기 위해
`LAB1`/`FARM1`을 priority target으로 먼저 깨우고 health gate를 통과시킨 뒤
나머지 서버를 기동하는 2단계 구조였다. 이 priority/remaining 분리 로직은
제거되었고, 지금은 선택된 대상을 항상 동시에 wake + gate한다.

## 4. 핵심 기능

### 4.1 target 정규화

설정은 FARM/LAB 전체 목록과 기본 대상을 가진다. 명령행 target이 있으면 기본
대상을 덮어쓴다. `all`, domain group, 개별 `FARM1`/`LAB10`을 동일한 parser로
해석하여 중복을 제거한다.

MAC address와 broadcast IP는 WOL에만 쓰고, 상태 확인과 원격 명령은 Ansible
inventory를 사용한다. 네트워크 주소와 논리 server ID를 분리하면 SSH port나
주소가 바뀌어도 workflow 이름을 유지할 수 있다.

### 4.2 1회 host health check

`check_server_boot_health.sh`는 target에 대해 다음을 확인한다.

- Ansible/SSH 도달성
- 필수 FARM/LAB share mount
- host `nvidia-smi`

과거에는 이 뒤에 `create_test_container.sh`로 임시 GPU container를 만들어
container 내부의 GPU/SSH까지 확인하고 `delete_test_container.sh`로 정리하는
단계가 있었다. 여러 서버가 동시에 부팅되면 이 단계가 서버마다 GPU 전체와
메모리 192g를 잡고 무거운 이미지를 pull하는 부담으로 이어져 제거했다. 이제
host 레벨 확인까지만 하고, container GPU 연동이 실제로 살아있는지는
`restart_all_remote_containers.sh`가 기존 사용자 container를 대상으로
재확인한다 (§4.3). `create_test_container.sh`/`delete_test_container.sh`
자체는 삭제하지 않았으므로, 필요하면 독립적으로 실행할 수 있다.

### 4.3 기존 container 재시작과 post-check

선택된 서버의 stopped target container를 시작한 뒤 각 container의 SSH와
GPU를 제한 시간 동안 확인한다. post-check 실패는 container별로 기록하고
전체 stage 실패 정보에 포함한다.

container를 무조건 재생성하지 않는 이유는 사용자 홈과 DB record, 고정 포트,
실행 옵션의 권위가 `user-lifecycle`에 있기 때문이다. 부팅 모듈은 기존
container를 시작하고 준비 여부만 확인한다.

### 4.4 alert suppression과 로그

실패는 구성된 경우 내부 notify API를 통해 Slack으로 보내고, 그렇지 않으면
stub log에 남긴다. 동일 실패의 반복 알림을 줄이기 위한 alert state가 별도
디렉터리에 저장된다. `reset_remote_boot_alert_state.sh`는 이 suppression
상태만 초기화한다.

service log, host health log와 alert state를 나눈 이유는 실행 이력과 알림
deduplication 상태를 독립적으로 보존하기 위해서다.

## 5. 설계상 지켜야 할 경계

- systemd unit을 추가하기 전에 부팅 1회 책임인지 지속 monitor 책임인지 구분한다.
- 공통 shell helper를 수정하면 모든 stage의 dry-run과 alert redaction을 확인한다.
- 실제 secret을 example 또는 log에 쓰지 않는다.
- retry를 늘리는 것으로 storage/GSS 장애를 감추지 않는다.
- container 생성/삭제 비즈니스 규칙은 `user-lifecycle` CLI를 통해 수행한다.
