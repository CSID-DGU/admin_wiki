# remote-operations 설정

> [개요](index.md) · [설계](design.md) · [운영](operations.md)

## 1. 개요

이 문서는 `remote-operations`가 WOL, host health gate, container post-check와 alert에
사용하는 runtime 입력을 준비하는 방법을 설명한다. 실제 환경값은 ignored 파일인
`config/remote_boot.local.env`에 두고, 저장소의
`config/remote_boot.example.env`에는 변수 구조와 공개 가능한 기본값만 유지한다.

local config를 만든다.

```bash
cd /home/jy/server_manage/remote-operations
cp config/remote_boot.example.env config/remote_boot.local.env
chmod 600 config/remote_boot.local.env
```

실제 MAC, 개인 경로와 Slack webhook을 example 파일이나 Git commit에 넣지 않는다.

## 2. target 설정

```bash
REMOTE_BOOT_FARM_TARGETS="FARM1 FARM2"
REMOTE_BOOT_LAB_TARGETS="LAB1 LAB2 LAB10"
REMOTE_BOOT_TARGETS="all"
```

| 변수 | 의미 |
| --- | --- |
| `REMOTE_BOOT_FARM_TARGETS` | `all-farm`이 확장할 FARM server ID 목록 |
| `REMOTE_BOOT_LAB_TARGETS` | `all-lab`이 확장할 LAB server ID 목록 |
| `REMOTE_BOOT_TARGETS` | target 인자가 없을 때 사용할 기본 대상 |

server ID는 `FARM<number>` 또는 `LAB<number>` 형식을 사용한다. 목록에 추가된 ID는
WOL MAC과 Ansible inventory host가 같은 물리 server를 가리켜야 한다.

## 3. WOL network 설정

```bash
REMOTE_BOOT_FARM_BROADCAST_IP="192.168.2.255"
REMOTE_BOOT_LAB_BROADCAST_IP="192.168.1.255"

REMOTE_BOOT_MAC_FARM1="<FARM1 MAC>"
REMOTE_BOOT_MAC_LAB1="<LAB1 MAC>"
```

domain별 broadcast IP는 management host에서 해당 network로 WOL packet을 보낼 수
있는 주소여야 한다. `REMOTE_BOOT_MAC_<SERVER_ID>`에는 server의 WOL 대상 NIC MAC을
넣는다. MAC은 장비 관리 기준 문서나 실제 server에서 확인하며 임의로 추정하지
않는다.

config만으로 Wake-on-LAN이 활성화되지는 않는다. server firmware, NIC와 network의
broadcast 전달 설정은 별도로 준비되어 있어야 한다.

## 4. Ansible 원격 접근

`remote-operations`는 server ID를 소문자 Ansible alias로 바꾸어 사용한다. 예를
들어 `FARM1`은 inventory의 `farm1`, `LAB10`은 `lab10`에 연결된다.

기본 Ansible 설정을 사용하지 않을 경우 local config에 개인 inventory를 지정한다.

```bash
REMOTE_BOOT_ANSIBLE_INVENTORY="/home/<관리자계정>/ansible/inventory.ini"
```

inventory 예시는 다음과 같다.

```ini
[farm]
farm1 ansible_host=<FARM1 address> ansible_user=<관리자계정>

[lab]
lab10 ansible_host=<LAB10 address> ansible_user=<관리자계정>
```

inventory는 접속 주소와 사용자를 정할 뿐 SSH 권한을 부여하지 않는다. management
host의 해당 service 사용자 SSH key가 remote account의 `authorized_keys`에 등록되어
있어야 한다. mount와 GPU recovery에는 target host에서 password 입력 없이 실행할
수 있는 `sudo -n` 권한도 필요하다.

다음 명령으로 각 alias를 먼저 확인한다.

```bash
ansible farm1 -i /home/<관리자계정>/ansible/inventory.ini -m ping
ansible lab10 -i /home/<관리자계정>/ansible/inventory.ini -m ping
```

## 5. gate와 timeout

```bash
REMOTE_BOOT_PRE_DELAY_SECONDS=0
REMOTE_BOOT_ENABLE_GATE=true
REMOTE_BOOT_GATE_TIMEOUT_SECONDS=360
REMOTE_BOOT_GATE_POLL_SECONDS=20
```

| 변수 | 의미 |
| --- | --- |
| `REMOTE_BOOT_PRE_DELAY_SECONDS` | management host의 network 준비 후 WOL을 보내기 전 대기 시간 |
| `REMOTE_BOOT_ENABLE_GATE` | container 시작 전에 모든 target의 host health 통과를 요구할지 결정 |
| `REMOTE_BOOT_GATE_TIMEOUT_SECONDS` | 선택된 모든 target이 공유하는 전체 gate deadline |
| `REMOTE_BOOT_GATE_POLL_SECONDS` | 아직 통과하지 못한 server를 다시 확인할 간격 |

timeout은 server마다 새로 시작되지 않는다. 동시에 선택한 server 수와 가장 느린 실제
부팅 시간을 기준으로 정한다. 원인을 확인하지 않은 채 timeout만 계속 늘리지 않는다.

## 6. host health 기준

```bash
REMOTE_BOOT_FARM_REQUIRED_MOUNT="<FARM NFS source>"
REMOTE_BOOT_LAB_REQUIRED_MOUNT="<LAB NFS source>"
REMOTE_BOOT_HOST_SHARE_MOUNT_TEMPLATE="/home/tako%s/share"
```

`REMOTE_BOOT_*_REQUIRED_MOUNT`는 `findmnt`에서 일치해야 하는 source다.
`REMOTE_BOOT_HOST_SHARE_MOUNT_TEMPLATE`의 `%s`는 server 번호로 바뀐다. 예를 들어
`FARM6`은 `/home/tako6/share`를 검사한다.

이 값은 기존 host mount 설정을 확인하기 위한 기준이다. NFS export, fstab이나
Kerberos 인증을 생성하지 않는다. 실제 `findmnt -rn -T <path> -o SOURCE,TARGET`
출력과 동일한 source를 사용한다.

## 7. container 시작과 post-check

```bash
REMOTE_BOOT_ENABLE_CONTAINER_RESTART=true
REMOTE_BOOT_CONTAINER_RESTART_TIMEOUT_SECONDS=600
REMOTE_BOOT_CONTAINER_RESTART_POLL_SECONDS=20
REMOTE_BOOT_CONTAINER_POST_RESTART_CHECK_TIMEOUT_SECONDS=60
REMOTE_BOOT_CONTAINER_POST_RESTART_CHECK_POLL_SECONDS=5
```

| 변수 | 의미 |
| --- | --- |
| `REMOTE_BOOT_ENABLE_CONTAINER_RESTART` | host gate 후 기존 target container를 시작할지 결정 |
| `REMOTE_BOOT_CONTAINER_RESTART_TIMEOUT_SECONDS` | 선택한 server 전체의 container 처리 deadline |
| `REMOTE_BOOT_CONTAINER_RESTART_POLL_SECONDS` | 실패한 server를 다시 처리할 간격 |
| `REMOTE_BOOT_CONTAINER_POST_RESTART_CHECK_TIMEOUT_SECONDS` | container별 SSH와 GPU 확인 제한 시간 |
| `REMOTE_BOOT_CONTAINER_POST_RESTART_CHECK_POLL_SECONDS` | container post-check 재시도 간격 |

처리 대상 image는 `REMOTE_BOOT_CONTAINER_TARGET_IMAGE_REGEX`로 제한할 수 있다.
설정하지 않으면 `decs`와 `dguailab/decs` repository를 대상으로 한다.

```bash
REMOTE_BOOT_CONTAINER_TARGET_IMAGE_REGEX='^(decs|dguailab/decs)(:|$)'
```

정규식을 바꿀 때는 container dry-run에서 선택·제외되는 image를 반드시 확인한다.

## 8. log와 alert

```bash
REMOTE_BOOT_ENABLE_HEALTH_LOGGING=true
REMOTE_BOOT_HEALTH_LOG_DIR="./logs/health"
REMOTE_BOOT_ALERT_STUB_LOG_FILE="./logs/alerts/remote_boot_alert_stub.log"
REMOTE_BOOT_ALERT_STATE_DIR="./state/alerts"
REMOTE_BOOT_LOG_FILE="/var/log/remote-boot.log"
REMOTE_BOOT_LOG_ROTATE_COUNT=14
```

| 변수 | 의미 |
| --- | --- |
| `REMOTE_BOOT_HEALTH_LOG_DIR` | host health와 container post-check 실행별 log 위치 |
| `REMOTE_BOOT_ALERT_STUB_LOG_FILE` | Slack을 사용할 수 없을 때 실패를 남길 fallback log |
| `REMOTE_BOOT_ALERT_STATE_DIR` | 같은 실패의 반복 전송을 억제하는 state 위치 |
| `REMOTE_BOOT_LOG_FILE` | systemd service의 전체 stdout·stderr log |
| `REMOTE_BOOT_LOG_ROTATE_COUNT` | daily logrotate 보존 개수 |

Slack alert를 사용하려면 다음 값을 설정한다.

```bash
REMOTE_BOOT_SLACK_ENABLED=true
REMOTE_BOOT_SLACK_WEBHOOK_URL_FARM="<Slack webhook URL>"
REMOTE_BOOT_SLACK_MESSAGE_PREFIX="[remote_boot]"
```

LAB/FARM alert는 현재 하나의 FARM webhook을 사용하며, server ID는 message label에
반영된다. 최종 Slack 전송은 source에 고정된 내부 notify API를 통한다. webhook은
secret이므로 terminal 출력, example 파일이나 Git commit에 남기지 않는다.

설정 후 실제 message를 확인한다.

```bash
./test/test_slack_notification.sh --server-id FARM1
```

## 9. 독립 test container 설정

`REMOTE_BOOT_TEST_*` 변수는 `create_test_container.sh`와
`delete_test_container.sh`를 수동으로 사용할 때만 적용된다. WOL → host gate → 기존
container 시작으로 이어지는 기본 부팅 흐름에서는 읽지 않는다.

독립 test 도구는 Docker image, UID/GID, memory, runtime과 mount를 실제로 사용할 수
있으므로 운영 부팅 검증과 구분해 별도 test 계정과 resource로 실행한다.

## 10. 첫 설정 검증 순서

1. local config의 권한이 `0600`인지 확인한다.
2. `--list-targets`로 FARM/LAB 목록을 확인한다.
3. 각 target의 Ansible ping을 확인한다.
4. WOL dry-run에서 MAC과 broadcast IP를 확인한다.
5. health dry-run에서 mount source와 path를 확인한다.
6. container dry-run에서 대상 image와 post-check 계획을 확인한다.
7. Slack을 사용하는 경우 test message를 전송한다.
8. 단일 server에서 실제 WOL, host health와 container post-check를 순서대로 실행한다.
9. 마지막으로 systemd installer를 실행한다.

명령과 실제 상태 변경 범위는 [운영 문서](operations.md)를 따른다.
