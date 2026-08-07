# remote-operations 설계

> [개요](index.md) · [운영](operations.md) · [설정](config.md)

> **GitHub 코드 링크:** `admin_infra_server`는 비공개 저장소다. 코드 링크를
> 누르면 GitHub 로그인 화면을 거쳐 원래 파일과 line으로 이동한다. 조직 저장소에
> 접근 권한이 있는 계정으로 로그인해야 한다.

## 1. 개요

`remote-operations`는 관리 서버에서 FARM/LAB GPU 서버를 원격으로 깨운 뒤,
각 서버가 운영 가능한 상태인지 확인하고 기존 사용자 컨테이너를 시작하는 일련의
부팅 작업을 제공한다.

Wake-on-LAN 패킷을 전송한 것만으로는 서버를 사용할 수 있다고 판단할 수 없다.
OS가 부팅되어 SSH가 열리고, 공유 스토리지와 NVIDIA driver가 준비된 뒤, 기존
컨테이너 안의 SSH와 GPU까지 동작해야 사용자 작업을 재개할 수 있다. 이 모듈은 이
과정을 하나의 제한 시간 안에서 순서대로 수행하고, 복구되지 않은 실패를 로그와
알림으로 남긴다.

NIC·firmware의 Wake-on-LAN 설정, 네트워크 전달, Ansible inventory, 서버 mount와 GPU
driver, 사용자 컨테이너 정의는 미리 준비되어 있어야 한다. `remote-operations`는
이 설정을 새로 만드는 대신 부팅 대상으로 지정된 서버의 상태를 확인하고,
안전하게 제한할 수 있는 복구만 수행한다.

## 2. 실행 구조

전체 작업은 `run_remote_boot.sh`에서 시작한다. 관리 서버가 부팅될 때
`remote-boot.service`가 한 번 실행하거나, 운영자가 같은 스크립트를 수동으로 실행할
수 있다.

| 단계 | 담당 스크립트 | 수행하는 작업 |
| --- | --- | --- |
| 대상 서버 결정 | `run_remote_boot.sh`, `common.sh` | 설정 또는 명령행 입력을 구체적인 서버 ID 목록으로 변환한다. |
| 부팅 신호 전송 | `wake_targets.sh` | 각 서버의 MAC과 broadcast IP로 Wake-on-LAN 패킷을 보낸다. |
| 서버 준비 상태 확인 | `wait_for_priority_servers.sh`, `check_server_boot_health.sh` | 선택한 모든 서버에서 SSH·공유 스토리지·GPU가 준비될 때까지 다시 확인한다. |
| 컨테이너 시작 | `restart_all_remote_containers.sh` | 대상 이미지의 기존 컨테이너를 시작하고 내부 SSH·GPU를 확인한다. |
| 실패 기록 | `common.sh` | 단계별 로그를 남기고 같은 내용의 반복 전송을 억제한 알림을 보낸다. |

실행 순서는 다음과 같다.

1. 설정된 사전 대기 시간이 지나면 대상 서버 전체에 WOL 패킷을 전송한다.
2. 서버 준비 상태 확인이 활성화되어 있으면 선택한 모든 서버의 SSH·공유
   스토리지·GPU가 준비될 때까지 기다린다.
3. 하나라도 제한 시간 안에 준비되지 않으면 컨테이너 시작으로 넘어가지 않고
   실패를 기록한다.
4. 모든 서버가 준비되면 선택한 서버에서 중지되어 있던 대상 컨테이너를 시작한다.
5. 각 대상 컨테이너의 SSH와 GPU를 확인하고, 복구되지 않은 실패가 있으면 전체
   실행을 실패로 종료한다.

서버 준비 상태 확인과 컨테이너 시작 단계는 설정으로 각각 끌 수 있다. 기본
실행에서는 두 단계를 모두 사용하여 서버가 준비되기 전에 사용자 컨테이너가
시작되는 것을 막는다.

**관련 코드**

- [`run_remote_boot.sh`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/remote-operations/script/run_remote_boot.sh%23L84-L242):
  설정 읽기, 대상 서버 확장, WOL, 서버 준비 상태 확인과 컨테이너 시작 단계를 조합한다.
- [`install_remote_boot_service.sh`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/remote-operations/script/install_remote_boot_service.sh%23L147-L208):
  관리 서버 부팅 시 전체 부팅 작업을 호출하는 systemd unit을 만든다.

## 3. 대상 서버 지정과 원격 접근

설정에는 FARM/LAB에서 관리할 서버 ID와 기본 실행 대상을 둔다. 실행 시
`FARM1`, `LAB10` 같은 개별 ID뿐 아니라 `all-farm`, `all-lab`, `all`을 받을 수
있으며, `common.sh`가 이를 중복 없는 구체적인 서버 ID 목록으로 확장한다.

서버 ID는 두 종류의 연결 정보에 사용된다.

| 목적 | 사용하는 정보 |
| --- | --- |
| WOL 패킷 전송 | 서버별 MAC address와 FARM/LAB broadcast IP |
| 상태 확인과 원격 명령 | 서버 ID에서 변환한 Ansible inventory 별칭 |

부팅 신호를 보내는 네트워크 주소와 OS 부팅 후 접속하는 Ansible 주소를 분리했기
때문에 SSH 주소나 port가 바뀌어도 `FARM1`과 같은 운영 ID는 유지할 수 있다. 반대로
두 정보가 같은 물리 서버를 가리키도록 설정되어 있어야 한다.

명령행에서 대상을 지정하면 설정의 기본 대상을 대체한다. 이 구조를 통해 전체 부팅,
구역 단위 부팅과 단일 서버 점검에 같은 실행 절차를 사용할 수 있다.

**관련 코드**

- [`common.sh`의 대상 서버 목록 변환](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/remote-operations/script/common.sh%23L514-L612):
  대상 문자열을 정리하고 그룹 이름을 구체적인 서버 목록으로 변환한다.
- [`wake_targets.sh`의 주소 선택](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/remote-operations/script/wake_targets.sh%23L87-L133):
  서버 ID에 해당하는 MAC과 구역별 broadcast IP를 선택한다.
- [`common.sh`의 Ansible 실행`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/remote-operations/script/common.sh%23L656-L780):
  서버 ID를 inventory 별칭으로 변환하고 원격 shell을 실행한다.

## 4. 부팅 단계별 설계

### 4.1 Wake-on-LAN

`wake_targets.sh`는 선택한 각 서버의 MAC address를 확인하고 FARM/LAB 네트워크에
맞는 broadcast IP로 magic packet을 전송한다. 서버별 상태 확인을 중간에 수행하지
않고 모든 패킷을 먼저 보낸 뒤 서버 준비 상태 확인 단계로 이동한다.

WOL 명령의 성공은 패킷을 보냈다는 의미다. 실제 전원 인가, firmware 부팅과
OS 준비는 확인하지 못하므로 다음 단계에서 먼저 SSH 접속 가능 여부를 확인한다.
서버의 MAC이 없거나 알 수 없는 ID가 들어오면 패킷을 보내지 않고
실패한다.

**관련 코드**

- [`send_magic_packet`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/remote-operations/script/wake_targets.sh%23L57-L76):
  서버별 WOL 명령을 실행하거나 모의 실행 계획을 기록한다.

### 4.2 전체 서버 준비 상태 확인

이 단계는 선택한 모든 서버가 준비된 뒤에만 컨테이너 시작을 허용한다. 아직
준비되지 않은 서버만 목록에 남겨 설정된 주기마다 다시 확인하며, 한 번 준비가
확인된 서버는 같은 실행에서 다시 검사하지 않는다.

제한 시간은 서버마다 따로 적용되지 않고 선택한 서버 전체에 한 번 적용된다. 한
서버라도 제한 시간까지 준비되지 않으면 확인 단계가 실패하고 컨테이너 시작 단계는
실행되지 않는다. 이를 통해 일부 서버만 준비된 상태에서 사용자 컨테이너가 먼저
올라오는 것을 막는다.

`wait_for_priority_servers.sh`라는 파일명은 과거 명칭이 남아 있는 것이며, 현재
구현은 우선순위 서버를 따로 선택하지 않고 전달된 모든 대상 서버를 동일하게
확인한다.

**관련 코드**

- [`wait_for_priority_servers.sh`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/remote-operations/script/wait_for_priority_servers.sh%23L115-L171):
  준비가 확인된 서버와 아직 확인 중인 서버를 구분하고 전체 제한 시간을 관리한다.

### 4.3 서버 상태 확인과 제한된 복구

`check_server_boot_health.sh`는 각 서버의 상태를 다음 순서대로
확인한다.

| 확인 항목 | 확인 방법 | 실패했을 때 수행하는 복구 |
| --- | --- | --- |
| SSH | Ansible remote shell로 `true` 실행 | 설정된 횟수만큼 연결을 다시 시도한다. |
| 공유 스토리지 | 지정한 source가 서버별 mount 경로에 연결됐는지 `findmnt`로 확인 | 해당 경로의 mount 또는 `mount -a`를 한 번 시도한 뒤 다시 확인한다. |
| 서버 GPU | 서버에서 `nvidia-smi` 실행 | NVIDIA module load와 persistence service 재시작을 한 번 시도한 뒤 다시 확인한다. |

mount와 GPU 복구는 한 번의 상태 확인 과정에서 각각 한 번만 수행한다. 그래도
실패하면 서버가 아직 준비되지 않은 것으로 처리하며, 전체 제한 시간이 남아 있으면
해당 서버의 상태를 다시 확인한다.

이 복구는 이미 준비된 mount 설정과 NVIDIA driver를 다시 활성화하는 범위다. fstab,
NFS 인증이나 driver package를 새로 구성하지 않는다. 따라서 설정 자체가 잘못된
경우에는 재시도로 숨기지 않고 실패로 남겨 해당 운영 절차에서 수정할 수 있게 한다.

**관련 코드**

- [`run_step_with_single_recovery`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/remote-operations/script/check_server_boot_health.sh%23L40-L84):
  mount와 GPU를 확인하고 한 번의 복구 후 재확인한다.
- [`check_server_boot_health.sh`의 실행 순서](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/remote-operations/script/check_server_boot_health.sh%23L194-L262):
  서버 ID를 mount·Ansible 정보로 변환하고 SSH, mount, GPU를 순서대로 확인한다.

### 4.4 기존 컨테이너 시작과 기동 후 점검

모든 서버의 준비가 확인되면 `restart_all_remote_containers.sh`가 Docker 목록에서
설정한 이미지 정규식에 맞는 컨테이너만 선택한다. 기본값은 `decs` 또는
`dguailab/decs` 이미지를 대상으로 한다.

선택된 컨테이너 중 중지된 항목을 시작하고, 이미 실행 중인 항목도 포함해 다음
기동 후 점검을 수행한다.

1. 컨테이너가 실행 상태인지 확인한다.
2. 컨테이너 내부 SSH service를 확인하고, 준비되지 않았으면 service 시작을
   시도한다.
3. 컨테이너 내부에서 `nvidia-smi`를 실행한다.
4. GPU 확인이 처음 실패하면 컨테이너를 한 번 재시작하고 제한 시간 동안 다시
   확인한다.

중지된 컨테이너의 일괄 시작이 실패하면 Docker service를 한 번 재시작한 뒤 다시
시도한다. 서버별 처리가 실패하면 전체 제한 시간이 남아 있는 동안 해당 서버를
다시 처리한다.

사용자 계정, mount, port와 Docker option은 기존 컨테이너에 이미 들어 있다.
이 모듈은 그 정보를 다시 결정하거나 컨테이너를 재생성하지 않고, 기존 컨테이너를
시작하고 준비 상태만 확인한다. 임시 GPU 컨테이너를 만드는
`create_test_container.sh`와 `delete_test_container.sh`는 독립 점검 도구이며 이
부팅 흐름에서는 호출하지 않는다.

**관련 코드**

- [`restart_all_remote_containers.sh`의 대상 선택](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/remote-operations/script/restart_all_remote_containers.sh%23L95-L185):
  이미지 정규식과 Docker 목록으로 처리할 컨테이너를 고른다.
- [`restart_remote_containers`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/remote-operations/script/restart_all_remote_containers.sh%23L199-L304):
  중지된 컨테이너 시작과 SSH·GPU 기동 후 점검을 수행한다.
- [서버별 재시도와 제한 시간](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/remote-operations/script/restart_all_remote_containers.sh%23L306-L358):
  실패한 서버만 남겨 전체 제한 시간 안에서 재시도한다.

### 4.5 로그와 실패 알림

각 스크립트는 시각, 실행 구분값, 단계, 서버와 실패 원인을 포함한 로그를 남긴다.
서버 상태 확인과 컨테이너 기동 후 점검 로그는 실행별 파일로도 저장할 수 있어
systemd 전체 로그와 개별 실패 근거를 나누어 확인할 수 있다.

실패 알림은 내부 알림 API를 통해 Slack으로 전달한다. Slack이 설정되지 않았거나
전송이 실패하면 대체 로그에 남긴다. 같은 실패 내용을 기준으로 만든 상태 파일이
이미 있으면 반복 알림을 억제한다. 서버 상태 확인과 컨테이너 단계가 다시 성공하면
각각 관련 상태 파일을 지운다. 실행 로그와 알림 억제 상태를 분리하여 과거 로그를
지우지 않고도 중복 알림 상태만 초기화할 수 있다.

**관련 코드**

- [`common.sh`의 알림 상태 관리](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/remote-operations/script/common.sh%23L67-L138):
  실패 내용별 상태 파일을 만들고 성공한 단계의 상태를 정리한다.
- [`send_slack_message`와 `notify_failure`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/remote-operations/script/common.sh%23L440-L499):
  내부 알림 API 전송, 대체 로그 기록과 중복 억제를 처리한다.

## 5. 설정 모델

실제 실행값은 Git에서 제외된 `config/remote_boot.local.env`에 두고, 저장소에는 변수와
기본 구조만 보여 주는 `config/remote_boot.example.env`를 유지한다. 설정은 다음
영역으로 나뉜다.

| 설정 영역 | 결정하는 내용 |
| --- | --- |
| 대상 서버 | FARM/LAB 서버 목록과 기본 실행 대상 |
| WOL 네트워크 | 서버별 MAC과 구역별 broadcast IP |
| 서버 준비 상태 확인 | 확인 단계 사용 여부, 전체 제한 시간과 재확인 주기 |
| 서버 상태 기준 | 요구하는 NFS source와 서버별 mount 경로 |
| 컨테이너 | 시작 단계 사용 여부, 대상 이미지 정규식과 기동 후 점검 제한 시간 |
| 로그·알림 | 상태 확인 로그 위치, service 로그 보존, 알림 상태와 Slack 전달 |

스크립트는 설정값을 읽되 MAC, webhook 같은 실제 값은 예제나 source에 넣지
않는다. 설정 파일의 각 항목과 준비 방법은 [설정 문서](config.md)에서 설명한다.

**관련 코드**

- [`remote_boot.example.env`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/remote-operations/config/remote_boot.example.env):
  실행 설정의 공개 가능한 구조와 기본값을 정의한다.

## 6. systemd 연동

설치 스크립트는 관리 서버에 `remote-boot.service`와 logrotate 설정을 만든다.
service는 `network-online.target` 이후 설치를 실행한 사용자 권한으로
`run_remote_boot.sh`를 호출하고, 출력은 service 로그에 추가한다.

unit은 `Type=oneshot`이다. 부팅 작업이 완료되면 process가 종료되며 상태를 계속
관찰하는 daemon으로 남지 않는다. 따라서 제한 시간과 재시도는 이번 부팅 작업을
완료하기 위한 범위로 제한되고, 이후의 지속적인 서버 상태 관측과 알림은
`monitoring`에서 수행한다.

설치 스크립트를 다시 실행하면 생성할 unit과 현재 파일을 비교해 필요한 경우에만
갱신하고, `systemctl daemon-reload`와 enable을 적용한다. service 로그에는 daily
logrotate와 보존 개수가 함께 설정된다.

**관련 코드**

- [`install_remote_boot_service.sh`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/remote-operations/script/install_remote_boot_service.sh%23L130-L234):
  oneshot unit, logrotate와 enable 동작을 구성한다.

## 7. 디렉터리 지도

| 경로 | 역할 |
| --- | --- |
| `script/run_remote_boot.sh` | 전체 부팅 작업의 시작점 |
| `script/wake_targets.sh` | 대상 서버별 Wake-on-LAN 패킷 전송 |
| `script/wait_for_priority_servers.sh` | 선택한 모든 서버의 준비 상태 확인 |
| `script/check_server_boot_health.sh` | SSH·mount·서버 GPU 확인과 제한된 복구 |
| `script/restart_all_remote_containers.sh` | 기존 대상 컨테이너 시작과 SSH·GPU 기동 후 점검 |
| `script/common.sh` | 대상 서버, Ansible, 로그와 알림 공통 함수 |
| `script/install_remote_boot_service.sh` | systemd unit과 logrotate 설치 |
| `script/reset_remote_boot_alert_state.sh` | 중복 알림 억제 상태 초기화 |
| `script/create_test_container.sh`, `script/delete_test_container.sh` | 부팅 흐름과 분리된 임시 GPU 컨테이너 점검 도구 |
| `config/remote_boot.example.env` | 공개 가능한 설정 구조와 기본값 |
| `config/remote_boot.local.env` | 실제 환경값을 두는 Git 제외 설정 파일 |
| `test/dry_run_remote_boot.sh` | WOL, 서버 상태, 컨테이너와 전체 흐름 모의 실행 |
| `test/integration_smoke_test.sh` | Ansible·Docker·GPU 통합 확인 |
| `test/test_slack_notification.sh` | 내부 알림 API와 Slack 알림 경로 확인 |
