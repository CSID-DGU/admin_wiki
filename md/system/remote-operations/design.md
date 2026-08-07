# remote-operations 설계

> [개요](index.md) · [운영](operations.md) · [설정](config.md)

> **GitHub 코드 링크:** `admin_infra_server`는 비공개 저장소다. 코드 링크를
> 누르면 GitHub 로그인 화면을 거쳐 원래 파일과 line으로 이동한다. 조직 저장소에
> 접근 권한이 있는 계정으로 로그인해야 한다.

## 1. 개요

`remote-operations`는 management host에서 FARM/LAB GPU server를 원격으로 깨운 뒤,
각 server가 운영 가능한 상태인지 확인하고 기존 사용자 container를 시작하는 부팅
orchestration을 제공한다.

Wake-on-LAN packet을 전송한 것만으로는 server가 사용할 수 있다고 판단할 수 없다.
OS가 부팅되어 SSH가 열리고, 공유 스토리지와 NVIDIA driver가 준비된 뒤, 기존
container 안의 SSH와 GPU까지 동작해야 사용자 작업을 재개할 수 있다. 이 모듈은 이
과정을 하나의 제한 시간 안에서 순서대로 수행하고, 복구되지 않은 실패를 log와
alert로 남긴다.

NIC·firmware의 Wake-on-LAN 설정, network 전달, Ansible inventory, host mount와 GPU
driver, 사용자 container 정의는 미리 준비되어 있어야 한다. `remote-operations`는
이 설정을 새로 만드는 대신 부팅 시 전달된 target을 대상으로 상태를 확인하고,
안전하게 제한할 수 있는 복구만 수행한다.

## 2. 실행 구조

전체 흐름의 entry point는 `run_remote_boot.sh`다. management host가 부팅될 때
`remote-boot.service`가 한 번 실행하거나, 운영자가 같은 script를 수동으로 실행할
수 있다.

| 단계 | 담당 script | 수행하는 작업 |
| --- | --- | --- |
| target 결정 | `run_remote_boot.sh`, `common.sh` | config 또는 명령행 target을 구체적인 server ID 목록으로 변환한다. |
| 전원 신호 | `wake_targets.sh` | 각 target의 MAC과 broadcast IP로 Wake-on-LAN packet을 보낸다. |
| host 준비 gate | `wait_for_priority_servers.sh`, `check_server_boot_health.sh` | 선택한 모든 server가 SSH·mount·GPU 확인을 통과할 때까지 재시도한다. |
| container 시작 | `restart_all_remote_containers.sh` | 대상 image의 기존 container를 시작하고 container 내부 SSH·GPU를 확인한다. |
| 실패 기록 | `common.sh` | 단계별 log를 남기고 중복을 억제한 alert를 전송한다. |

실행 순서는 다음과 같다.

1. 선택적인 pre-delay 후 target 전체에 WOL packet을 전송한다.
2. gate가 활성화되어 있으면 선택한 모든 target의 host health가 통과할 때까지
   기다린다.
3. 하나라도 제한 시간 안에 통과하지 못하면 container 시작으로 넘어가지 않고
   실패를 기록한다.
4. gate가 통과하면 선택한 server의 stopped target container를 시작한다.
5. 각 target container의 SSH와 GPU를 확인하고, 복구되지 않은 실패가 있으면 전체
   실행을 실패로 종료한다.

gate와 container 시작 단계는 config로 각각 끌 수 있다. 기본 실행에서는 두 단계를
모두 사용하여 host 준비가 확인되기 전에 사용자 container가 시작되는 것을 막는다.

**관련 코드**

- [`run_remote_boot.sh`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/remote-operations/script/run_remote_boot.sh%23L84-L242):
  config 로드, target 확장, WOL, gate와 container 시작 단계를 조합한다.
- [`install_remote_boot_service.sh`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/remote-operations/script/install_remote_boot_service.sh%23L147-L208):
  management host 부팅 시 orchestration을 호출하는 systemd unit을 만든다.

## 3. target과 원격 접근 모델

설정에는 FARM/LAB에서 관리할 server ID와 기본 실행 대상을 둔다. 실행 시
`FARM1`, `LAB10` 같은 개별 ID뿐 아니라 `all-farm`, `all-lab`, `all`을 받을 수
있으며, `common.sh`가 이를 중복 없는 구체적인 server ID 목록으로 확장한다.

server ID는 두 종류의 연결 정보에 사용된다.

| 목적 | 사용하는 정보 |
| --- | --- |
| WOL packet 전송 | target별 MAC address와 FARM/LAB broadcast IP |
| 상태 확인과 원격 명령 | server ID에서 변환한 Ansible inventory host alias |

전원 신호를 보내는 network 주소와 OS 부팅 후 접속하는 Ansible 주소를 분리했기
때문에 SSH 주소나 port가 바뀌어도 `FARM1`과 같은 운영 ID는 유지할 수 있다. 반대로
target은 두 정보가 같은 물리 server를 가리키도록 설정되어 있어야 한다.

명령행에서 target을 지정하면 config의 기본 target을 대체한다. 이 구조는 전체 부팅,
domain 단위 부팅과 단일 server 점검이 같은 orchestration을 공유하게 한다.

**관련 코드**

- [`common.sh`의 target 확장](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/remote-operations/script/common.sh%23L514-L612):
  target 문자열을 정규화하고 group token을 구체적인 server 목록으로 변환한다.
- [`wake_targets.sh`의 주소 선택](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/remote-operations/script/wake_targets.sh%23L87-L133):
  server ID에 해당하는 MAC과 domain broadcast IP를 선택한다.
- [`common.sh`의 Ansible 실행`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/remote-operations/script/common.sh%23L656-L780):
  server ID를 inventory alias로 변환하고 원격 shell을 실행한다.

## 4. 부팅 단계별 설계

### 4.1 Wake-on-LAN

`wake_targets.sh`는 선택한 각 server의 MAC address를 확인하고 FARM/LAB network에
맞는 broadcast IP로 magic packet을 전송한다. target 사이에 health 확인을 끼우지
않고 packet 전송을 먼저 마친 뒤 gate 단계로 이동한다.

WOL command의 성공은 packet 전송 성공만 의미한다. 실제 전원 인가, firmware 부팅과
OS 준비는 확인하지 못하므로 다음 gate가 SSH 도달성을 기준으로 부팅 결과를
판단한다. target에 MAC이 없거나 알 수 없는 ID가 들어오면 packet을 보내지 않고
실패한다.

**관련 코드**

- [`send_magic_packet`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/remote-operations/script/wake_targets.sh%23L57-L76):
  target별 WOL command를 실행하거나 dry-run 계획을 기록한다.

### 4.2 전체 target health gate

gate는 선택한 모든 server가 준비된 뒤에만 container 시작을 허용한다. 아직 통과하지
못한 server만 pending 목록에 남겨 poll interval마다 다시 확인하며, 한번 통과한
server는 같은 gate 실행에서 다시 검사하지 않는다.

timeout은 server별 시간이 아니라 선택한 target 전체가 공유하는 deadline이다. 한
server라도 deadline까지 통과하지 못하면 gate가 실패하고 container 시작 단계는
실행되지 않는다. 이를 통해 일부 server만 준비된 상태에서 사용자 container가 먼저
올라오는 것을 막는다.

`wait_for_priority_servers.sh`라는 파일명은 과거 명칭이 남아 있는 것이며, 현재
구현은 priority server를 따로 선택하지 않고 전달된 모든 target에 같은 gate를
적용한다.

**관련 코드**

- [`wait_for_priority_servers.sh`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/remote-operations/script/wait_for_priority_servers.sh%23L115-L171):
  passed/pending 목록과 전체 deadline을 관리한다.

### 4.3 host health 확인과 제한된 복구

각 gate 시도는 `check_server_boot_health.sh`로 한 server의 상태를 다음 순서대로
확인한다.

| 확인 항목 | 확인 방법 | 실패했을 때 수행하는 복구 |
| --- | --- | --- |
| SSH | Ansible remote shell로 `true` 실행 | 설정된 횟수만큼 연결을 다시 시도한다. |
| 공유 스토리지 | 요구한 source가 server별 mount path에 연결됐는지 `findmnt`로 확인 | 해당 path mount 또는 `mount -a`를 한 번 시도한 뒤 다시 확인한다. |
| host GPU | host에서 `nvidia-smi` 실행 | NVIDIA module load와 persistence service 재시작을 한 번 시도한 뒤 다시 확인한다. |

mount와 GPU 복구는 각 health-check 호출 안에서 한 번만 수행한다. 그래도 실패하면
gate에 실패를 반환하며, gate는 전체 deadline이 남아 있는 동안 해당 server의 health
check를 다시 호출할 수 있다.

이 복구는 이미 준비된 mount 설정과 NVIDIA driver를 다시 활성화하는 범위다. fstab,
NFS 인증이나 driver package를 새로 구성하지 않는다. 따라서 설정 자체가 잘못된
경우에는 retry로 숨기지 않고 실패로 남겨 해당 운영 절차에서 수정할 수 있게 한다.

**관련 코드**

- [`run_step_with_single_recovery`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/remote-operations/script/check_server_boot_health.sh%23L40-L84):
  mount와 GPU를 확인하고 한 번의 복구 후 재확인한다.
- [`check_server_boot_health.sh`의 실행 순서](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/remote-operations/script/check_server_boot_health.sh%23L194-L262):
  server ID를 mount·Ansible 정보로 변환하고 SSH, mount, GPU를 순서대로 확인한다.

### 4.4 기존 container 시작과 post-check

host gate가 통과하면 `restart_all_remote_containers.sh`가 Docker inventory에서 설정한
image 정규식에 맞는 container만 선택한다. 기본값은 `decs` 또는
`dguailab/decs` image를 대상으로 한다.

선택된 container 중 stopped 상태인 항목을 시작하고, 이미 실행 중인 항목도 포함해
다음 post-check를 수행한다.

1. container가 실행 상태인지 확인한다.
2. container 내부 SSH service를 확인하고, 준비되지 않았으면 service 시작을
   시도한다.
3. container 내부에서 `nvidia-smi`를 실행한다.
4. GPU 확인이 처음 실패하면 container를 한 번 재시작하고 제한 시간 동안 다시
   확인한다.

stopped container의 일괄 시작이 실패하면 Docker service를 한 번 재시작한 뒤 다시
시도한다. server별 처리가 실패하면 아직 전체 deadline이 남아 있는 동안 해당
server를 다시 처리한다.

사용자 identity, mount, port와 Docker option은 기존 container에 이미 들어 있다.
이 모듈은 그 정보를 다시 결정하거나 container를 재생성하지 않고, 기존 container를
시작하고 준비 상태만 확인한다. 임시 GPU container를 만드는
`create_test_container.sh`와 `delete_test_container.sh`는 독립 점검 도구이며 이
부팅 흐름에서는 호출하지 않는다.

**관련 코드**

- [`restart_all_remote_containers.sh`의 대상 선택](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/remote-operations/script/restart_all_remote_containers.sh%23L95-L185):
  image 정규식과 Docker inventory로 처리할 container를 고른다.
- [`restart_remote_containers`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/remote-operations/script/restart_all_remote_containers.sh%23L199-L304):
  stopped container 시작과 SSH·GPU post-check를 수행한다.
- [server별 retry와 deadline](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/remote-operations/script/restart_all_remote_containers.sh%23L306-L358):
  실패한 server만 남겨 전체 제한 시간 안에서 재시도한다.

### 4.5 log와 실패 alert

각 script는 timestamp, 실행 context, stage, server와 reason을 포함한 log를 남긴다.
host health와 container post-check log는 실행별 파일로도 저장할 수 있어 systemd 전체
log와 개별 실패 근거를 나누어 확인할 수 있다.

실패 alert는 내부 notify API를 통해 Slack으로 전달한다. Slack이 설정되지 않았거나
전송이 실패하면 alert stub log에 남긴다. 같은 실패 message를 정규화해 만든 state
파일이 이미 있으면 반복 alert를 억제한다. host health와 container 단계가 다시
성공하면 각각 관련 state를 지운다. 실행 log와 alert suppression state를 분리하여
과거 log를 지우지 않고도 중복 알림 상태만 초기화할 수 있다.

**관련 코드**

- [`common.sh`의 alert state 관리](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/remote-operations/script/common.sh%23L67-L138):
  실패 message별 state 파일을 만들고 성공한 stage의 state를 정리한다.
- [`send_slack_message`와 `notify_failure`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/remote-operations/script/common.sh%23L440-L499):
  내부 notify API 전송, stub fallback과 중복 억제를 처리한다.

## 5. 설정 모델

실제 실행값은 ignored 파일인 `config/remote_boot.local.env`에 두고, 저장소에는 key와
기본 구조만 보여 주는 `config/remote_boot.example.env`를 유지한다. 설정은 다음
영역으로 나뉜다.

| 설정 영역 | 결정하는 내용 |
| --- | --- |
| target | FARM/LAB server 목록과 기본 실행 대상 |
| WOL network | target별 MAC과 domain별 broadcast IP |
| gate | host health gate 사용 여부, 전체 timeout과 poll interval |
| host health | 요구하는 NFS source와 server별 mount path |
| container | 시작 단계 사용 여부, 대상 image 정규식과 post-check timeout |
| log·alert | health log 위치, service log 보존, alert state와 Slack 전달 |

script는 config 값을 읽되 MAC, webhook 같은 실제 값은 example이나 source에 넣지
않는다. 설정 파일의 각 항목과 준비 방법은 [설정 문서](config.md)에서 설명한다.

**관련 코드**

- [`remote_boot.example.env`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/remote-operations/config/remote_boot.example.env):
  runtime config의 공개 가능한 구조와 기본값을 정의한다.

## 6. systemd 연동

installer는 management host에 `remote-boot.service`와 logrotate 설정을 만든다.
service는 `network-online.target` 이후 설치를 실행한 사용자 권한으로
`run_remote_boot.sh`를 호출하고, 출력은 service log에 추가한다.

unit은 `Type=oneshot`이다. 부팅 orchestration이 완료되면 process가 종료되며 상태를
계속 관찰하는 daemon으로 남지 않는다. 따라서 timeout과 retry는 이번 부팅 실행을
완료하기 위한 범위로 제한되고, 이후의 지속적인 server 상태 관측과 alert는
`monitoring`에서 수행한다.

installer를 다시 실행하면 생성할 unit과 현재 파일을 비교해 필요한 경우에만
갱신하고, `systemctl daemon-reload`와 enable을 적용한다. service log에는 daily
logrotate와 보존 개수가 함께 설정된다.

**관련 코드**

- [`install_remote_boot_service.sh`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/remote-operations/script/install_remote_boot_service.sh%23L130-L234):
  oneshot unit, logrotate와 enable 동작을 구성한다.

## 7. 디렉터리 지도

| 경로 | 역할 |
| --- | --- |
| `script/run_remote_boot.sh` | 전체 부팅 orchestration entry point |
| `script/wake_targets.sh` | target별 Wake-on-LAN packet 전송 |
| `script/wait_for_priority_servers.sh` | 선택한 모든 target의 host health gate |
| `script/check_server_boot_health.sh` | SSH·mount·host GPU 확인과 제한된 복구 |
| `script/restart_all_remote_containers.sh` | 기존 target container 시작과 SSH·GPU post-check |
| `script/common.sh` | target, Ansible, log와 alert 공통 함수 |
| `script/install_remote_boot_service.sh` | systemd unit과 logrotate 설치 |
| `script/reset_remote_boot_alert_state.sh` | alert suppression state 초기화 |
| `script/create_test_container.sh`, `script/delete_test_container.sh` | 부팅 흐름과 분리된 임시 GPU container 점검 도구 |
| `config/remote_boot.example.env` | 공개 가능한 config 구조와 기본값 |
| `config/remote_boot.local.env` | 실제 환경값을 두는 ignored config |
| `test/dry_run_remote_boot.sh` | WOL, health, container와 전체 흐름 simulation |
| `test/integration_smoke_test.sh` | Ansible·Docker·GPU 통합 확인 |
| `test/test_slack_notification.sh` | notify API와 Slack alert 경로 확인 |
