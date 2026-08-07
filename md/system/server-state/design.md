# server-state 설계

> [개요](index.md) · [운영](operations.md)

## 1. 개요

`server-state`는 FARM/LAB 서버가 모두 같은 공통 설정을 유지하도록
기준을 정의하는 모듈이다. 목적은 크게 두 가지다.

1. **운영 서버 점검**: 각 서버에 Docker, NVIDIA driver/toolkit, Kubernetes,
   network tuning, Kerberos/NFS, monitoring 설정이 빠짐없이 적용되어 있는지
   확인하고 차이가 있으면 복구할 방법을 제시한다.
2. **신규 서버 구축**: 새 서버에 공통 설정을 같은 순서로 적용하여 운영
   서버와 동일한 표준 상태로 만든다.

이 문서에서 **확인**은 운영 서버의 현재 상태를 공통 기준과 비교하여 빠진
설정이나 차이를 찾는 것을 의미한다. **설정**은 신규 서버를 구축하거나 확인에서
발견한 차이를 해소하기 위해 필요한 공통 설정을 적용하는 것을 의미한다.

공통 기준은 코드에서 `profile`이라고 부르는 **상태 기준** 단위로 정의한다.
하나의 상태 기준(profile)은 Docker, NVIDIA driver, monitoring처럼 하나의 관리
대상을 기준 상태, 점검 명령, 복구 방법과 담당 모듈까지 묶어 이름 붙인 것이다.
여러 상태 기준을 실행할 순서대로 묶은 것은 **작업 흐름(profile set)**이라고
하며, 운영 서버 점검과 신규 서버 구축에 같은 기준을 적용할 때 사용한다.

즉, 서버마다 설치 방법을 다시 기억해서 수동으로 설정하는 대신 하나의 공통
기준을 사용하려고 만든 코드다.

```text
                  공통 서버 기준
                  profiles.yml
                       │
          ┌────────────┴────────────┐
          │                         │
    [운영 서버 점검]            [신규 서버 구축]
  빠진 설정과 상태 확인        같은 순서로 설정 적용
          │                         │
          └────────────┬────────────┘
                       │
               동일한 서버 상태 유지
```

`server-state`가 모든 기능을 직접 구현하는 것은 아니다. 공통 OS, Docker,
NVIDIA와 network 설정은 직접 관리하고, Kerberos/NFS와 monitoring처럼 별도
모듈이 소유한 기능은 해당 모듈의 점검·복구 명령을 한 순서로 연결한다.

## 2. 관리 범위

`new-host-bootstrap`과 `existing-host-drift`는 다음 항목을 같은 순서로
사용한다. 따라서 새로운 공통 설정을 추가할 때 두 흐름에 함께 넣을 수 있다.

| 순서 | 영역 | 1. 운영 서버 점검에서 확인하는 것 | 2. 신규 서버 구축에서 설정하는 것 |
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

### 2.1 운영 서버 점검

`existing-host-drift`는 표의 **확인하는 것** 열에 정의된 항목을 사용해 운영
서버와 공통 기준의 차이를 찾는다. 현재는 각 항목의 점검 명령을 생성해
`DRY-RUN`으로 보여주며, 관리자가 명령을 실행하고 결과를 판정한다.

NVIDIA 점검은 `nvidia-smi`가 GPU 이름과 실제 driver version을 출력하는지
확인한다. driver가 GPU를 인식하지 못하거나 명령이 실패하는 상태는 찾을 수
있지만, 출력된 version을 기준 version과 자동 비교하지는 않는다.

network 점검은 inventory의 storage interface를 기준으로 NIC RX queue가 4096
이상인지와 `decs-rx-queue.service`가 활성화되어 있는지 확인한다. IP 주소,
gateway, DNS와 netplan 전체는 현재 점검 범위에 포함하지 않는다.

### 2.2 신규 서버 구축

`new-host-bootstrap`은 표의 **설정하는 것** 열에 정의된 항목을 위에서 아래
순서로 적용해 신규 서버를 공통 상태로 만든다. 현재 playbook은 공통 package,
Docker, NVIDIA, Kubernetes, RX queue와 관련된 설정 task를 제공한다.

NVIDIA driver의 기본 package는 `nvidia-driver-580`이며, 설치 후 의도하지 않은
major version 변경을 막기 위해 apt hold한다. network 설정은 storage NIC의 RX
queue를 4096으로 유지하는 systemd service까지만 담당한다.

IP, gateway, DNS, netplan, hostname, SSH와 sudo는 bootstrap 전에 준비해야 하는
조건이다. 이 항목까지 자동화하려면 별도의 상태 기준(profile)과 검증 규칙을
추가해야 한다.

## 3. 상태 기준 구조

`config/profiles.yml`에는 작은 단위의 상태 기준(profile)과 이를 순서대로 묶은
작업 흐름(profile set)이 있다.

| 작업 흐름(profile set) | 용도 |
| --- | --- |
| `new-host-bootstrap` | 신규 서버의 표준 구축 순서 |
| `existing-host-drift` | 운영 서버의 공통 설정 점검·복구 순서 |
| `managed-host` | 운영 관리 서버용 기본 별칭 |
| `monitoring-host` | monitoring 항목만 확인할 때 사용 |

새 공통 설정을 모든 서버에 적용하려면 작은 상태 기준으로 추가한 뒤
`new-host-bootstrap`과 `existing-host-drift` 양쪽에 넣는다. 이렇게 해야 새
서버 설치에는 들어갔지만 운영 서버 점검에서는 빠지거나, 그 반대가 되는
문제를 줄일 수 있다.

각 상태 기준은 다음 정보를 가진다.

- 이 설정을 실제로 소유하는 모듈
- 부작용 없이 상태를 읽는 check
- 차이가 있을 때 사용할 remediation 명령
- 자동 실행할 수 없는 작업의 runbook과 safety level

## 4. 모듈별 소유권

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

## 5. 상태 표시

| 상태 | 의미 |
| --- | --- |
| `OK` | inventory나 로컬 파일처럼 즉시 확인 가능한 조건이 충족됨 |
| `MISSING` | 필요한 로컬 파일이나 값이 없음 |
| `DRY-RUN` | 실행할 원격 점검 또는 복구 명령만 표시함 |
| `MANUAL` | 도메인 가입, join, mount처럼 담당자 확인이 필요한 작업 |
| `UNKNOWN` | 아직 지원하지 않는 check 또는 remediation 형식 |
