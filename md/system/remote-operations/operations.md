# remote-operations 운영

> [개요](index.md) · [설계](design.md) · [설정](config.md)

## 1. 개요

이 문서의 목표는 `remote-operations`를 management host에 배포하고, 변경 내용을
실제 server에 적용하기 전에 검증하며, WOL·host health·container 시작 단계를
목적에 맞게 실행하고 실패 원인을 확인하는 절차를 제공하는 것이다.

운영은 다음 순서를 기준으로 한다.

1. local config와 Ansible 원격 접근을 준비한다.
2. target과 실행 계획을 dry-run으로 확인한다.
3. WOL, host health와 container 단계를 개별 server에서 검증한다.
4. 전체 흐름을 수동 실행해 log와 alert를 확인한다.
5. systemd unit을 설치하거나 갱신해 management host 부팅에 연결한다.

모든 명령은 다음 directory에서 실행한다.

```bash
cd /home/jy/server_manage/remote-operations
```

## 2. 목적별 실행 위치

| 운영 목적 | 사용할 명령 또는 파일 |
| --- | --- |
| 사용 가능한 target을 확인한다. | `./script/wake_targets.sh --list-targets` |
| WOL packet만 보낸다. | `./script/wake_targets.sh TARGET...` |
| 한 server의 SSH·mount·GPU를 확인한다. | `./script/check_server_boot_health.sh --server-id SERVER_ID` |
| 기존 target container를 시작하고 SSH·GPU를 확인한다. | `./script/restart_all_remote_containers.sh SERVER_ID...` |
| WOL부터 container post-check까지 전체 흐름을 실행한다. | `./script/run_remote_boot.sh TARGET...` |
| management host 부팅에 전체 흐름을 연결한다. | `./script/install_remote_boot_service.sh` |
| Slack alert 전달을 확인한다. | `./test/test_slack_notification.sh` |
| 저장된 alert suppression state를 초기화한다. | `./script/reset_remote_boot_alert_state.sh` |

## 3. 실행 전 준비

실제 server에 접근하기 전에 다음 조건을 확인한다.

- `config/remote_boot.local.env`가 준비되어 있다.
- target의 MAC과 broadcast IP가 실제 network와 일치한다.
- 각 server의 Wake-on-LAN이 firmware와 NIC에서 활성화되어 있다.
- 설정한 Ansible inventory로 target host에 SSH 접속할 수 있다.
- mount와 GPU 복구에 필요한 원격 명령은 `sudo -n`으로 실행할 수 있다.
- host의 NFS mount와 NVIDIA driver가 이미 구성되어 있다.
- container 시작 대상 image 정규식이 실제 사용자 container와 일치한다.

config 파일을 처음 만드는 절차와 변수 의미는 [설정 문서](config.md)를 따른다.

## 4. 변경 전 검증

### 4.1 target 확인

```bash
./script/wake_targets.sh --list-targets
./script/run_remote_boot.sh --list-targets
```

local config의 FARM/LAB 목록과 `all-farm`, `all-lab`, `all` 확장 결과를 확인한다.
새 server를 추가했다면 이 목록에 먼저 나타나야 한다.

### 4.2 dry-run

```bash
./test/dry_run_remote_boot.sh wake FARM1 LAB1
./test/dry_run_remote_boot.sh health FARM1
./test/dry_run_remote_boot.sh containers FARM1
./test/dry_run_remote_boot.sh full FARM1 LAB1
```

`wake`, `health`, `full` dry-run은 WOL packet, sleep과 상태 변경 command를 실행하지
않고 계획을 출력한다. `containers` dry-run은 실제 container를 시작하거나
재시작하지 않지만 현재 Docker inventory를 읽어 처리 대상과 post-check 계획을
만든다. 따라서 container dry-run에도 Ansible inventory와 read-only 원격 연결이
필요하다.

출력에서 다음을 확인한다.

- 입력한 group token이 의도한 구체적 server ID로 확장되는가?
- 각 ID의 MAC, broadcast IP와 Ansible host alias가 같은 장비를 가리키는가?
- domain별 요구 mount source와 server별 mount path가 올바른가?
- target image 정규식이 시작해야 할 container만 선택하는가?
- timeout과 poll interval이 선택한 server 수와 실제 부팅 시간을 감당하는가?

### 4.3 실제 연결 smoke test

```bash
./test/integration_smoke_test.sh
```

이 명령은 선택된 target에 Ansible ping, Docker daemon과 host GPU 확인을 실제로
수행한 뒤 host health gate를 실행한다. health gate는 mount와 GPU가 실패하면 제한된
복구도 수행하므로 단순 조회 명령이 아니다.

`--full-flow`를 추가하면 WOL부터 container 시작까지 실제 전체 흐름을 실행한다.
변경 검증의 첫 단계에서는 사용하지 않고, 개별 단계가 통과한 뒤 명시적으로
실행한다.

```bash
./test/integration_smoke_test.sh --full-flow
```

### 4.4 Slack alert test

```bash
./test/test_slack_notification.sh --server-id FARM1
```

이 명령은 내부 notify API를 통해 실제 Slack message를 전송한다. test 전에
`REMOTE_BOOT_SLACK_ENABLED`와 webhook 설정을 확인하고 운영 채널에 test message가
전송된다는 점을 공유한다.

## 5. 수동 실행

### 5.1 WOL만 실행

```bash
./script/wake_targets.sh FARM1
./script/wake_targets.sh all-farm
./script/wake_targets.sh FARM1 LAB1
```

command 성공은 magic packet을 전송했다는 의미이며 server 부팅 완료를 보장하지
않는다. 이후 host health check로 실제 SSH·mount·GPU를 확인한다.

### 5.2 한 server의 host health 확인

```bash
./script/check_server_boot_health.sh --server-id FARM1
```

SSH, 요구 mount와 host `nvidia-smi`를 순서대로 확인한다. mount 실패 시 mount 또는
`mount -a`, GPU 실패 시 module load와 persistence service 재시작을 시도하므로 실제
server 상태가 바뀔 수 있다.

### 5.3 기존 container 시작과 post-check

```bash
./script/restart_all_remote_containers.sh FARM1
```

설정된 image 정규식에 맞는 기존 container만 처리한다. stopped container를 시작한
뒤 container 내부 SSH와 GPU를 확인하며, 실패 시 Docker service 또는 container
재시작이 발생할 수 있다.

### 5.4 전체 부팅 orchestration

```bash
./script/run_remote_boot.sh FARM1 LAB1
./script/run_remote_boot.sh --targets "all-farm"
```

명령행 target은 `REMOTE_BOOT_TARGETS` 기본값을 대체한다. 실제 전체 server를
대상으로 실행하기 전에 한 server, 한 domain 순서로 범위를 늘린다.

## 6. systemd 배포와 갱신

### 6.1 최초 설치

```bash
./script/install_remote_boot_service.sh
```

installer는 다음 항목을 적용한다.

- `/etc/systemd/system/remote-boot.service`
- `/etc/logrotate.d/remote-boot`
- service log 파일과 소유권
- `systemctl daemon-reload`와 service enable

installer를 실행한 사용자와 group이 oneshot service의 실행 identity가 된다. 해당
계정이 repository, local config, Ansible inventory와 SSH key를 읽을 수 있어야 한다.

설치 직후 실행까지 확인하려면 `--start-now`를 사용한다.

```bash
./script/install_remote_boot_service.sh --start-now
```

### 6.2 변경 후 재설치가 필요한 경우

`run_remote_boot.sh`를 비롯한 source script와 기존 local config 값은 service가 다음
실행 때 같은 path에서 다시 읽으므로 일반적으로 unit 재설치가 필요하지 않다.
다음 항목을 바꾸면 installer를 다시 실행한다.

- repository 또는 runner script path
- service 실행 사용자와 group
- config path
- service log path나 logrotate 보존 개수
- systemd unit의 dependency나 실행 option

unit 내용을 강제로 다시 쓰려면 `--force`를 사용한다.

```bash
./script/install_remote_boot_service.sh --force
```

### 6.3 배포 확인

```bash
systemctl is-enabled remote-boot.service
systemctl status remote-boot.service
journalctl -u remote-boot.service -b
tail -f /var/log/remote-boot.log
```

`Type=oneshot`이므로 실행을 완료한 뒤 계속 실행 중인 daemon process는 없다. exit
status와 이번 boot의 log로 성공 여부를 판단한다.

## 7. 새 server 추가

1. server의 Wake-on-LAN을 firmware와 NIC에서 활성화하고 실제 MAC을 확인한다.
2. management host의 Ansible inventory에 해당 host alias를 추가하고 SSH 접속을
   검증한다.
3. `REMOTE_BOOT_FARM_TARGETS` 또는 `REMOTE_BOOT_LAB_TARGETS`에 server ID를 추가한다.
4. `REMOTE_BOOT_MAC_<SERVER_ID>`에 MAC을 설정한다.
5. domain broadcast IP와 요구 mount source, server별 mount path를 확인한다.
6. `--list-targets`와 `wake` dry-run으로 target 해석과 WOL command를 확인한다.
7. 실제 WOL 후 해당 server 하나에 host health check를 실행한다.
8. 기존 target container가 있는 경우 container dry-run과 post-check를 수행한다.
9. 마지막으로 전체 orchestration의 단일-server dry-run과 실제 실행을 확인한다.

새 server를 target 목록에 추가하는 것만으로 Ansible 접근, mount, GPU driver나
container가 구성되지는 않는다. 각 영역의 준비가 완료된 뒤 이 모듈의 검증 절차를
연결한다.

## 8. 실패 진단

| 실패 stage 또는 reason | 먼저 확인할 내용 |
| --- | --- |
| `wake_failed` | MAC 누락, `wakeonlan` 설치, broadcast IP와 management network |
| `ssh_connection_failed` | 실제 전원 상태, inventory host, SSH key·사용자와 boot 시간 |
| `mount_unavailable` | `findmnt` source/target, fstab, NFS·Kerberos 상태와 `sudo -n` |
| `host_gpu_unavailable` | host `nvidia-smi`, module, persistence service와 driver log |
| `docker_start_failed` | Docker daemon, target container 상태와 host resource |
| `ssh_unavailable` | container log, entrypoint와 container 내부 sshd |
| `gpu_unavailable` | container image, NVIDIA runtime, 할당 GPU와 container log |
| Slack 전송 실패 | notify API 도달성, webhook 설정과 alert stub log |

gate 실패를 단순히 timeout 증가로 처리하기 전에 어떤 stage가 pending인지 확인한다.
mount·GPU 설정 자체가 잘못되었거나 container 정의가 오래된 경우에는 해당 설정을
수정한 뒤 단일 server부터 다시 검증한다.

## 9. alert suppression 초기화

같은 실패가 이미 전송되어 새 alert가 억제되는 경우, 저장된 message를 확인한 뒤
필요한 범위만 초기화한다.

```bash
./script/reset_remote_boot_alert_state.sh --server-id FARM1
./script/reset_remote_boot_alert_state.sh --stage mount_check
./script/reset_remote_boot_alert_state.sh --reason mount_unavailable
```

여러 filter를 같이 주면 모두 일치하는 state만 지운다. 전체 state 삭제는 현재 실패
상태와 alert 재전송 영향을 확인한 뒤 실행한다.

```bash
./script/reset_remote_boot_alert_state.sh --all
```

이 명령은 실행 log를 지우지 않고 alert suppression state 파일만 삭제한다.

## 10. 운영 안전 수칙

- 실제 실행 전에 같은 target으로 dry-run을 확인한다.
- `all` 실행보다 단일 server와 domain 단위 검증을 먼저 수행한다.
- local config의 MAC, SSH 경로와 webhook을 source나 log에 복사하지 않는다.
- mount와 GPU recovery가 상태를 변경한다는 점을 고려해 maintenance 범위를 정한다.
- 실제 사용자 container를 임시 test container로 대체하거나 재생성하지 않는다.
- 지속적으로 반복되는 장애는 부팅 retry로 숨기지 않고 해당 모듈의 운영 절차에서
  원인을 수정한다.
