# server-state 설계

> [개요](index.md) · [운영](operations.md)

## 1. 이 모듈이 하는 일

`server-state`는 FARM/LAB의 GPU 서버가 모두 같은 공통 설정을 유지하도록
기준을 정의하는 모듈이다. 목적은 크게 두 가지다.

1. **기존 서버 점검**: 각 서버에 Docker, NVIDIA driver/toolkit, Kubernetes,
   network tuning, Kerberos/NFS, monitoring 설정이 빠짐없이 적용되어 있는지
   확인하고 차이가 있으면 복구할 방법을 제시한다.
2. **신규 서버 구축**: 새 서버에 공통 설정을 같은 순서로 적용하여 기존
   서버와 동일한 표준 상태로 만든다.

즉, 서버마다 설치 방법을 다시 기억해서 수동으로 설정하는 대신 하나의 공통
기준을 사용하려고 만든 코드다.

```text
                  공통 서버 기준
                 profiles.yml
                       │
          ┌────────────┴────────────┐
          │                         │
     기존 서버 점검              신규 서버 구축
   빠진 설정과 상태 확인       같은 순서로 설정 적용
          │                         │
          └────────────┬────────────┘
                       │
              동일한 GPU 서버 상태
```

`server-state`가 모든 기능을 직접 구현하는 것은 아니다. 공통 OS, Docker,
NVIDIA와 network 설정은 직접 관리하고, Kerberos/NFS와 monitoring처럼 별도
모듈이 소유한 기능은 해당 모듈의 점검·복구 명령을 한 순서로 연결한다.

## 2. 무엇을 확인하고 설정하는가

`new-host-bootstrap`과 `existing-host-drift`는 다음 항목을 같은 순서로
사용한다. 따라서 새로운 공통 설정을 추가할 때 두 흐름에 함께 넣을 수 있다.

| 순서 | 영역 | 기존 서버에서 확인하는 것 | 신규 서버에 설정하는 것 |
| --- | --- | --- | --- |
| 1 | 기본 접속 조건 | inventory 등록, Ansible 접속, 비대화형 sudo, hostname | 자동 설정 전 SSH, sudo, hostname, IP와 inventory를 확인 |
| 2 | 공통 OS | Ubuntu 계열 여부, 공통 package 설치 여부 | apt repository, NFS, Kerberos와 network 도구 설치 |
| 3 | Docker Engine | service 활성 상태, daemon 응답, systemd cgroup driver | Docker repository/package와 `daemon.json` 설정 |
| 4 | NVIDIA driver | `nvidia-smi`가 GPU와 driver version을 정상 출력하는지, package hold 여부 | 설정된 driver package 설치와 apt hold |
| 5 | NVIDIA Container Toolkit | `nvidia-ctk`, Docker NVIDIA runtime, containerd NVIDIA runtime | toolkit 설치 후 Docker/containerd runtime 설정 |
| 6 | Kubernetes node | kubeadm/kubelet/kubectl, kubelet, cluster join 파일과 node label | Kubernetes package 설치와 kubelet 활성화 |
| 7 | network tuning | storage NIC 정보, RX queue 4096 이상, 영속화 service | storage NIC RX queue를 4096으로 유지하는 systemd service |
| 8 | Kerberos/NFS | realm 설정, machine keytab, service ticket, `rpc-gssd`, fstab과 mount 상태 | client package/config와 GSS 준비 상태 구성 |
| 9 | monitoring | 두 exporter service와 metrics/health endpoint | monitoring 모듈의 exporter 배포 playbook 사용 |
| 10 | 사용자 container 전제조건 | 사용자 DB 환경, server inventory, Docker 접근 | 사용자 생성·삭제는 `user-lifecycle`을 통해 처리 |

### 2.1 NVIDIA version 확인 범위

현재 점검 명령은 `nvidia-smi`를 실행하여 GPU 이름과 실제 driver version이
출력되는지 확인한다. 따라서 driver가 GPU를 인식하지 못하거나 명령 자체가
실패하는 상태는 찾을 수 있다.

신규 설치 playbook의 기본 package는 현재 `nvidia-driver-580`이며 설치 후
의도하지 않은 major version 변경을 막기 위해 apt hold한다. 다만 기존 서버의
driver version을 `580`과 자동 비교하여 불일치 판정을 내리는 규칙은 아직 없다.
현재는 출력된 version을 관리자가 확인해야 한다.

### 2.2 network 설정 범위

현재 `network-tuning`이 관리하는 대상은 **스토리지 통신에 사용하는 NIC의 RX
queue 크기**다. inventory에서 서버별 storage interface를 읽고, RX queue가
4096 이상인지와 `decs-rx-queue.service`가 활성화되어 있는지 확인한다.

IP 주소, gateway, DNS와 netplan 전체를 자동으로 설정하는 기능은 아직 없다.
신규 서버의 IP, hostname, SSH와 sudo는 bootstrap을 시작하기 전에 준비해야
하는 조건이다. 향후 모든 서버의 netplan까지 통일하려면 별도의 profile과
검증 규칙을 추가해야 한다.

## 3. 현재 구현 수준

이 모듈은 최종적으로 공통 기준과 실제 서버 상태를 자동 비교하고 필요한
복구까지 안전하게 실행하는 것을 목표로 한다. 현재 구현 수준은 다음과 같다.

| 기능 | 현재 상태 |
| --- | --- |
| 전체 서버가 따라야 할 공통 profile 정의 | 구현됨 |
| 신규/기존 서버에 같은 profile 순서 사용 | 구현됨 |
| 서버별 점검 명령 생성 | 구현됨 |
| 신규 서버 설정용 Ansible task | 구현됨 |
| `check`가 원격 서버를 순회하고 결과 판정 | 아직 구현되지 않음 |
| `apply --execute`로 복구 자동 실행 | 아직 구현되지 않음. 명시적으로 거부됨 |
| 주기적인 전체 서버 drift 검사와 알림 | 아직 구현되지 않음 |
| IP/DNS/netplan 전체 표준화 | 아직 구현되지 않음 |

따라서 “모든 서버가 같은 설정인지 확인하고 새 서버를 똑같이 설정한다”는
이해는 맞다. 다만 현재는 **기준, 점검 명령, 복구 playbook을 한곳에 정리한
단계**이고, 한 명령으로 전체 서버를 자동 검사·복구하는 controller까지 완성된
상태는 아니다.

## 4. profile 구조

`config/profiles.yml`에는 작은 단위의 profile과 이를 순서대로 묶은 profile
set이 있다.

| profile set | 용도 |
| --- | --- |
| `new-host-bootstrap` | 신규 SSH-ready 서버의 표준 구축 순서 |
| `existing-host-drift` | 기존 서버의 공통 설정 점검·복구 순서 |
| `managed-host` | 기존 관리 서버용 기본 별칭 |
| `monitoring-host` | monitoring 항목만 확인할 때 사용 |

새 공통 설정을 모든 서버에 적용하려면 작은 profile로 추가한 뒤
`new-host-bootstrap`과 `existing-host-drift` 양쪽에 넣는다. 이렇게 해야 새
서버 설치에는 들어갔지만 기존 서버 점검에서는 빠지거나, 그 반대가 되는
문제를 줄일 수 있다.

각 profile은 다음 정보를 가진다.

- 이 설정을 실제로 소유하는 모듈
- 부작용 없이 상태를 읽는 check
- 차이가 있을 때 사용할 remediation 명령
- 자동 실행할 수 없는 작업의 runbook과 safety level

## 5. 모듈별 소유권

| 영역 | 실제 소유자 | `server-state`의 역할 |
| --- | --- | --- |
| 공통 OS, Docker, NVIDIA, Kubernetes package, network tuning | `server-state` | 공통 기준과 bootstrap task 관리 |
| NAS, AD, Kerberos와 NFS 정책 | `kerberos-nfs` | 점검 순서와 승인된 runbook 연결 |
| exporter와 metrics endpoint | `monitoring` | 배포·점검 playbook 연결 |
| 사용자와 container 생성·삭제 | `user-lifecycle` | 공용 inventory 사용과 전제조건 확인 |
| 서버 전원과 boot sequence | `remote-operations` | 이 모듈에서 다루지 않음 |
| 사용자 container image | `container-images` | 이 모듈에서 image 내부를 변경하지 않음 |

소유권을 나눈 이유는 `server-state`에 모든 운영 코드를 복사하지 않고, 실제
담당 모듈의 rollback과 안전 절차를 그대로 사용하기 위해서다.

## 6. 상태 표시

| 상태 | 의미 |
| --- | --- |
| `OK` | inventory나 로컬 파일처럼 즉시 확인 가능한 조건이 충족됨 |
| `MISSING` | 필요한 로컬 파일이나 값이 없음 |
| `DRY-RUN` | 실행할 원격 점검 또는 복구 명령만 표시함 |
| `MANUAL` | 도메인 가입, join, mount처럼 담당자 확인이 필요한 작업 |
| `UNKNOWN` | 아직 지원하지 않는 check 또는 remediation 형식 |

## 7. 디렉터리 구조

| 경로 | 기능 |
| --- | --- |
| `bin/server-state` | CLI 실행 파일 |
| `script/cli.py` | `list-hosts`, `check`, `plan`, `apply` 출력 |
| `script/inventory.py` | 공용 JSONL inventory 로드와 host 선택 |
| `script/profiles.py` | profile set 확장과 서버별 변수 치환 |
| `config/profiles.yml` | 공통 상태, 점검과 복구 명령의 기준 |
| `ansible_playbook/bootstrap_gpu_server.yml` | 신규/기존 서버의 공통 설정 task |
| `ansible_playbook/kerberos_nfs_client_recovery.yml` | Kerberos NFS 상태 점검과 제한된 복구 |
| `docs/standard-gpu-server-pipeline.md` | 신규/기존 서버 표준 단계의 개발 문서 |
| `tests/` | inventory와 profile 처리 unit test |
