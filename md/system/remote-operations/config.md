# remote-operations 설정

> [개요](index.md) · [설계](design.md) · [운영](operations.md)

## 1. 개요

이 문서는 `remote-operations`가 부팅 신호 전송, 서버 준비 상태 확인, 컨테이너 기동
후 점검과 알림에 사용하는 설정을 준비하는 방법을 설명한다. 실제 환경값은 Git에서
제외된 `config/remote_boot.local.env`에 두고, 저장소의
`config/remote_boot.example.env`에는 변수 구조와 공개 가능한 기본값만 유지한다.

로컬 설정 파일을 만든다.

```bash
cd <저장소>/remote-operations
cp config/remote_boot.example.env config/remote_boot.local.env
chmod 600 config/remote_boot.local.env
```

실제 MAC, 개인 경로와 Slack webhook을 example 파일이나 Git commit에 넣지 않는다.

## 2. 대상 서버 설정

```bash
REMOTE_BOOT_FARM_TARGETS="FARM1 FARM2"
REMOTE_BOOT_LAB_TARGETS="LAB1 LAB2 LAB10"
REMOTE_BOOT_TARGETS="all"
```

| 변수 | 의미 |
| --- | --- |
| `REMOTE_BOOT_FARM_TARGETS` | `all-farm`이 나타내는 FARM 서버 ID 목록 |
| `REMOTE_BOOT_LAB_TARGETS` | `all-lab`이 나타내는 LAB 서버 ID 목록 |
| `REMOTE_BOOT_TARGETS` | 명령행에서 대상을 지정하지 않았을 때 사용할 기본 대상 |

서버 ID는 `FARM<number>` 또는 `LAB<number>` 형식을 사용한다. 목록에 추가된 ID는
WOL MAC과 Ansible inventory의 서버가 같은 물리 서버를 가리켜야 한다.

## 3. WOL 네트워크 설정

```bash
REMOTE_BOOT_FARM_BROADCAST_IP="192.168.2.255"
REMOTE_BOOT_LAB_BROADCAST_IP="192.168.1.255"

REMOTE_BOOT_MAC_FARM1="<FARM1 MAC>"
REMOTE_BOOT_MAC_LAB1="<LAB1 MAC>"
```

구역별 broadcast IP는 관리 서버에서 해당 네트워크로 WOL 패킷을 보낼 수
있는 주소여야 한다. `REMOTE_BOOT_MAC_<SERVER_ID>`에는 서버의 WOL 대상 NIC MAC을
넣는다. MAC은 장비 관리 기준 문서나 실제 서버에서 확인하며 임의로 추정하지
않는다.

설정 파일만으로 Wake-on-LAN이 활성화되지는 않는다. 서버 firmware, NIC와 네트워크의
broadcast 전달 설정은 별도로 준비되어 있어야 한다.

## 4. Ansible 원격 접근

`remote-operations`는 서버 ID를 소문자 Ansible 별칭으로 바꾸어 사용한다. 예를
들어 `FARM1`은 inventory의 `farm1`, `LAB10`은 `lab10`에 연결된다.

inventory는 **저장소의 공용 `ansible/inventory.ini`**를 사용한다. 개인 사본을
만들지 않는다. clone 경로가 관리자마다 다르므로 자신의 경로로 적는다.

```bash
REMOTE_BOOT_ANSIBLE_INVENTORY="<저장소>/ansible/inventory.ini"
```

**접속 계정(`ansible_user`)은 inventory에 적지 않는다.** 공용 파일이라 계정을
적으면 다른 관리자가 자기 계정으로 접속할 수 없다. 계정은 각 관리자의
`~/.ansible.cfg`에 있는 `remote_user`가 담당한다. inventory 형식과 우선순위
규칙은 [Ansible 기초 개념](../ansible/basic.md#inventory)과
[Ansible 설정](../ansible/config.md#3-공용-inventory)에 있다.

inventory는 접속 주소를 정할 뿐 SSH 권한을 부여하지 않는다. 이 서비스를 실행하는
계정의 SSH key가 원격 계정의 `authorized_keys`에 등록되어 있어야 한다. mount와
GPU 복구에는 대상 서버에서 password 입력 없이 실행할 수 있는 `sudo -n` 권한도
필요하다. 두 준비 절차는 [Ansible 설정](../ansible/config.md#22-ssh-키-등록)에 있다.

다음 명령으로 각 alias를 먼저 확인한다. inventory와 계정은 `~/.ansible.cfg`가
정하므로 옵션으로 지정하지 않는다.

```bash
ansible farm1 -m ping
ansible lab10 -m ping
```

## 5. 서버 준비 상태 확인과 제한 시간

```bash
REMOTE_BOOT_PRE_DELAY_SECONDS=0
REMOTE_BOOT_ENABLE_GATE=true
REMOTE_BOOT_GATE_TIMEOUT_SECONDS=360
REMOTE_BOOT_GATE_POLL_SECONDS=20
```

| 변수 | 의미 |
| --- | --- |
| `REMOTE_BOOT_PRE_DELAY_SECONDS` | 관리 서버의 네트워크 준비 후 WOL을 보내기 전 대기 시간 |
| `REMOTE_BOOT_ENABLE_GATE` | 컨테이너 시작 전에 모든 서버의 준비 상태를 확인할지 결정 |
| `REMOTE_BOOT_GATE_TIMEOUT_SECONDS` | 선택된 서버 전체의 준비 상태를 확인할 제한 시간 |
| `REMOTE_BOOT_GATE_POLL_SECONDS` | 아직 준비되지 않은 서버를 다시 확인할 간격 |

제한 시간은 서버마다 새로 시작되지 않는다. 동시에 선택한 서버 수와 가장 느린 실제
부팅 시간을 기준으로 정한다. 원인을 확인하지 않은 채 제한 시간만 계속 늘리지 않는다.

## 6. 서버 상태 확인 기준

```bash
REMOTE_BOOT_FARM_REQUIRED_MOUNT="<FARM NFS source>"
REMOTE_BOOT_LAB_REQUIRED_MOUNT="<LAB NFS source>"
REMOTE_BOOT_HOST_SHARE_MOUNT_TEMPLATE="/home/tako%s/share"
```

`REMOTE_BOOT_*_REQUIRED_MOUNT`는 `findmnt`에서 일치해야 하는 source다.
`REMOTE_BOOT_HOST_SHARE_MOUNT_TEMPLATE`의 `%s`는 서버 번호로 바뀐다. 예를 들어
`FARM6`은 `/home/tako6/share`를 검사한다.

이 값은 기존 서버 mount 설정을 확인하기 위한 기준이다. NFS export, fstab이나
Kerberos 인증을 생성하지 않는다. 실제 `findmnt -rn -T <path> -o SOURCE,TARGET`
출력과 동일한 source를 사용한다.

## 7. 컨테이너 시작과 기동 후 점검

```bash
REMOTE_BOOT_ENABLE_CONTAINER_RESTART=true
REMOTE_BOOT_CONTAINER_RESTART_TIMEOUT_SECONDS=600
REMOTE_BOOT_CONTAINER_RESTART_POLL_SECONDS=20
REMOTE_BOOT_CONTAINER_POST_RESTART_CHECK_TIMEOUT_SECONDS=60
REMOTE_BOOT_CONTAINER_POST_RESTART_CHECK_POLL_SECONDS=5
```

| 변수 | 의미 |
| --- | --- |
| `REMOTE_BOOT_ENABLE_CONTAINER_RESTART` | 서버 준비 상태 확인 후 기존 대상 컨테이너를 시작할지 결정 |
| `REMOTE_BOOT_CONTAINER_RESTART_TIMEOUT_SECONDS` | 선택한 서버 전체의 컨테이너 처리 제한 시간 |
| `REMOTE_BOOT_CONTAINER_RESTART_POLL_SECONDS` | 실패한 서버를 다시 처리할 간격 |
| `REMOTE_BOOT_CONTAINER_POST_RESTART_CHECK_TIMEOUT_SECONDS` | 컨테이너별 SSH와 GPU 확인 제한 시간 |
| `REMOTE_BOOT_CONTAINER_POST_RESTART_CHECK_POLL_SECONDS` | 컨테이너 기동 후 점검을 다시 시도할 간격 |

처리 대상 이미지는 `REMOTE_BOOT_CONTAINER_TARGET_IMAGE_REGEX`로 제한할 수 있다.
설정하지 않으면 `decs`와 `dguailab/decs` repository를 대상으로 한다.

```bash
REMOTE_BOOT_CONTAINER_TARGET_IMAGE_REGEX='^(decs|dguailab/decs)(:|$)'
```

정규식을 바꿀 때는 컨테이너 모의 실행에서 선택·제외되는 이미지를 반드시 확인한다.

## 8. 로그와 알림

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
| `REMOTE_BOOT_HEALTH_LOG_DIR` | 서버 상태 확인과 컨테이너 기동 후 점검의 실행별 로그 위치 |
| `REMOTE_BOOT_ALERT_STUB_LOG_FILE` | Slack을 사용할 수 없을 때 실패를 남길 대체 로그 |
| `REMOTE_BOOT_ALERT_STATE_DIR` | 같은 실패의 반복 전송을 억제하는 상태 파일 위치 |
| `REMOTE_BOOT_LOG_FILE` | systemd service의 전체 stdout·stderr 로그 |
| `REMOTE_BOOT_LOG_ROTATE_COUNT` | daily logrotate 보존 개수 |

Slack 알림을 사용하려면 다음 값을 설정한다.

```bash
REMOTE_BOOT_SLACK_ENABLED=true
REMOTE_BOOT_SLACK_WEBHOOK_URL_FARM="<Slack webhook URL>"
REMOTE_BOOT_SLACK_MESSAGE_PREFIX="[remote_boot]"
```

LAB/FARM 알림은 현재 하나의 FARM webhook을 사용하며, 서버 ID는 메시지에
반영된다. 최종 Slack 전송은 source에 고정된 내부 알림 API를 통한다. webhook은
secret이므로 terminal 출력, 예제 파일이나 Git commit에 남기지 않는다.

설정 후 실제 message를 확인한다.

```bash
./test/test_slack_notification.sh --server-id FARM1
```

## 9. 독립 시험용 컨테이너 설정

`REMOTE_BOOT_TEST_*` 변수는 `create_test_container.sh`와
`delete_test_container.sh`를 수동으로 사용할 때만 적용된다. WOL → 서버 준비 상태
확인 → 기존 컨테이너 시작으로 이어지는 기본 부팅 흐름에서는 읽지 않는다.

독립 시험 도구는 Docker image, UID/GID, memory, runtime과 mount를 실제로 사용할 수
있으므로 운영 부팅 검증과 구분해 별도 시험 계정과 resource로 실행한다.

## 10. 첫 설정 검증 순서

1. 로컬 설정 파일의 권한이 `0600`인지 확인한다.
2. `--list-targets`로 FARM/LAB 목록을 확인한다.
3. 각 대상 서버의 Ansible ping을 확인한다.
4. WOL 모의 실행에서 MAC과 broadcast IP를 확인한다.
5. 서버 상태 모의 실행에서 mount source와 경로를 확인한다.
6. 컨테이너 모의 실행에서 대상 이미지와 기동 후 점검 계획을 확인한다.
7. Slack을 사용하는 경우 시험 메시지를 전송한다.
8. 단일 서버에서 실제 WOL, 서버 상태 확인과 컨테이너 기동 후 점검을 순서대로 실행한다.
9. 마지막으로 systemd 설치 스크립트를 실행한다.

명령과 실제 상태 변경 범위는 [운영 문서](operations.md)를 따른다.
