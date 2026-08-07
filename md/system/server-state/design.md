# server-state 설계

> [개요](index.md) · [운영](operations.md)

## 1. 개요

FARM/LAB GPU 서버는 Docker, NVIDIA, Kubernetes, network, Kerberos/NFS와
monitoring 설정을 공통으로 사용한다. 이 기준과 작업 순서가 여러 모듈과
playbook에 흩어져 있으면 신규 서버를 구축할 때 일부 단계가 누락될 수 있고,
운영 서버가 기준에서 벗어나도 같은 방식으로 점검하기 어렵다.

`server-state`는 서버가 갖춰야 할 공통 상태와 작업 순서를 한곳에 정의하여
다음 두 작업이 서로 다른 기준으로 운영되지 않도록 한다.

1. **운영 서버 점검**: 현재 상태를 공통 기준과 비교할 수 있는 점검 항목과
   복구 계획을 제공한다.
2. **신규 서버 구축**: 공통 설정을 정해진 순서로 적용하여 기존 운영 서버와
   같은 상태를 만든다.

코드에서는 하나의 관리 영역에 대한 기준을 `profile`, 여러 기준을 목적에 맞게
순서대로 묶은 작업 흐름을 `profile set`이라고 부른다. 이 문서에서는 각각
**상태 기준(profile)**과 **작업 흐름(profile set)**으로 표기한다.

## 2. 설계 구조

`server-state`는 서버에 직접 접속해 모든 설정을 자동 변경하는 controller가
아니라, **대상 서버 정보와 상태 기준을 결합하여 점검·복구 계획을 만드는 조정
계층**으로 설계되어 있다.

| 구성 요소 | 역할 |
| --- | --- |
| 공용 inventory | 대상 서버를 선택하고 domain, 접속 정보, network interface 등 서버별 값을 제공한다. |
| 상태 기준(profile) | 하나의 관리 영역에 대해 목표 상태, 점검 항목, 복구 방법과 담당 모듈을 정의한다. |
| 작업 흐름(profile set) | 여러 상태 기준을 운영 서버 점검이나 신규 서버 구축에 필요한 순서로 묶는다. |
| CLI | 대상 서버와 작업 흐름을 결합하고, 서버별 점검 명령과 복구 계획을 출력한다. |
| Ansible playbook과 담당 모듈 | 관리자가 계획을 검토한 뒤 실제 서버 설정을 적용할 때 사용한다. |

처리 순서는 다음과 같다.

1. inventory에서 작업 대상 서버와 서버별 설정값을 읽는다.
2. 선택한 작업 흐름을 순서가 있는 상태 기준 목록으로 확장한다.
3. 각 상태 기준의 점검·복구 명령에 서버별 값을 반영한다.
4. 실행할 계획과 안전 수준을 출력한다.
5. 관리자가 계획을 검토하고 필요한 명령이나 playbook을 실행한다.

현재 CLI가 어디까지 실행하고 어떤 결과를 출력하는지는
[운영 문서](operations.md)의 "현재 구현 수준"에서 설명한다.

## 3. 관리 범위와 소유권

`new-host-bootstrap`과 `existing-host-drift`는 다음 상태 기준을 같은 순서로
사용한다. 신규 서버 구축과 운영 서버 점검이 같은 기준을 공유하므로, 공통
설정이 한쪽 작업에만 반영되는 것을 줄일 수 있다.

| 순서 | 영역 | 담당 모듈 | 1. 운영 서버 점검 기준 | 2. 신규 서버 구축 기준 |
| --- | --- | --- | --- | --- |
| 1 | 기본 접속 조건 | `server-state` | inventory 등록, Ansible 접속, 비대화형 sudo, hostname | 자동 설정 전 SSH, sudo, hostname, IP와 inventory 준비 |
| 2 | 공통 OS | `server-state` | Ubuntu 계열 여부, 공통 package 설치 여부 | apt repository, NFS, Kerberos와 network 도구 설치 |
| 3 | Docker Engine | `server-state` | service 활성 상태, daemon 응답, systemd cgroup driver | Docker repository/package와 `daemon.json` 설정 |
| 4 | NVIDIA driver | `server-state` | GPU와 driver 인식 여부, driver package hold 여부 | 설정된 driver package 설치와 apt hold |
| 5 | NVIDIA Container Toolkit | `server-state` | `nvidia-ctk`, Docker와 containerd의 NVIDIA runtime | toolkit 설치 후 Docker/containerd runtime 설정 |
| 6 | Kubernetes node | `server-state` | Kubernetes package, kubelet, cluster join 정보와 node label | Kubernetes package 설치와 kubelet 활성화 |
| 7 | network tuning | `server-state` | storage NIC 정보, RX queue 4096 이상, 영속화 service | storage NIC RX queue를 4096으로 유지하는 systemd service |
| 8 | Kerberos/NFS | `kerberos-nfs` | realm, machine keytab, service ticket, `rpc-gssd`, mount 상태 | client package와 설정, GSS 준비 상태 구성 |
| 9 | monitoring | `monitoring` | exporter service와 metrics/health endpoint | monitoring 모듈의 exporter 배포 playbook 사용 |
| 10 | 사용자 container 전제조건 | `user-lifecycle` | 사용자 DB 환경, server inventory, Docker 접근 | 사용자·container 생성에 필요한 host 조건 준비 |

### 3.1 운영 서버 점검

운영 서버 점검의 목적은 한 대 이상의 서버가 공통 기준에서 벗어난 부분을 같은
방식으로 찾는 것이다. 점검 대상은 공용 inventory에서 전체 서버, FARM/LAB
영역 또는 개별 서버 단위로 선택한다. `existing-host-drift`는 선택된 각 서버에
대해 표의 **운영 서버 점검 기준**을 위에서 아래 순서로 전개한다.

각 상태 기준에는 서버를 변경하지 않고 현재 상태를 읽는 점검 항목이 들어 있다.
예를 들어 Docker Engine은 service와 daemon, cgroup driver를 확인하고, NVIDIA
driver는 GPU 인식과 package hold 상태를 확인한다. 명령에 필요한 host, domain,
network interface 등의 값은 inventory의 실제 서버 정보로 채운다.

점검 계획에는 다음 정보가 함께 나타난다.

- 어떤 서버의 어느 상태 기준을 점검하는지
- 정상 여부를 판단하기 위해 실행할 읽기 전용 명령
- 해당 영역을 소유하는 모듈
- 기준과 다를 때 검토할 복구 방법과 안전 수준

현재 구현은 원격 점검 명령을 자동 실행하거나 결과를 판정하지 않는다. 서버별
명령을 `DRY-RUN`으로 생성하며, 관리자가 실행 결과를 확인한 뒤 함께 제시된
복구 계획을 검토한다. 따라서 이 흐름은 운영 서버를 즉시 변경하는 작업이 아니라,
서버별 점검 방식과 후속 조치를 동일하게 만드는 역할을 한다.

**관련 코드**

- [`existing-host-drift` 작업 흐름](https://github.com/CSID-DGU/admin_infra_server/blob/main/server-state/config/profiles.yml#L30-L42):
  운영 서버에 적용할 상태 기준과 순서를 정의한다.
- [점검 대상 선택](https://github.com/CSID-DGU/admin_infra_server/blob/main/server-state/script/inventory.py#L136-L166):
  `all`, FARM/LAB 또는 개별 서버 조건을 inventory의 실제 서버 목록에 적용한다.
- [점검 계획 생성](https://github.com/CSID-DGU/admin_infra_server/blob/main/server-state/script/cli.py#L78-L86)과
  [점검 항목 처리](https://github.com/CSID-DGU/admin_infra_server/blob/main/server-state/script/cli.py#L126-L142):
  선택된 서버와 상태 기준을 순회하고 로컬 검사 결과 또는 `DRY-RUN` 명령을 만든다.

### 3.2 신규 서버 구축

신규 서버 구축의 목적은 새 서버를 기존 운영 서버와 같은 기준으로 재현 가능하게
구성하는 것이다. Ubuntu 설치, IP와 hostname 설정, SSH 접속, 비대화형 sudo와
inventory 등록까지 완료된 서버를 시작점으로 삼는다. 이 조건이 갖춰져야 이후
설정에 필요한 서버 정보와 원격 실행 경로가 확정된다.

`new-host-bootstrap`은 표의 **신규 서버 구축 기준**을 선행 조건에 맞춰 적용한다.
공통 OS와 package를 먼저 준비하고, Docker Engine과 NVIDIA driver/runtime,
Kubernetes node, network tuning을 차례로 구성한 뒤 Kerberos/NFS, monitoring과
사용자 container 전제조건을 연결한다. 각 단계에는 운영 서버 점검과 동일한 상태
기준이 사용되므로, 구축이 끝난 서버도 같은 항목으로 다시 점검할 수 있다.

서버별 IP, domain, storage interface와 Kerberos 정보는 inventory 값으로
채워진다. 실제 변경 방법은 상태 기준의 복구 항목에 연결되어 있으며, 작업의
위험도에 따라 다음과 같이 구분한다.

- 반복 실행해도 결과가 같은 설정은 Ansible playbook과 `--check --diff` 계획을
  먼저 제공한다.
- NVIDIA driver 변경, Kubernetes join, keytab과 mount처럼 서비스나 보안에
  영향을 주는 작업은 자동 적용하지 않고 관리자의 확인이 필요한 절차로 남긴다.
- Kerberos/NFS와 monitoring처럼 별도 모듈이 소유한 영역은 구현을 복제하지 않고
  해당 모듈의 playbook이나 runbook을 호출한다.

이 흐름의 결과물은 모든 변경을 즉시 실행하는 설치 프로그램이 아니라, 서버별로
값이 채워진 순서 있는 구축 계획이다. 관리자는 단계별 예상 변경과 담당 모듈을
확인한 뒤 실제 적용 여부를 결정한다.

**관련 코드**

- [`new-host-bootstrap` 작업 흐름](https://github.com/CSID-DGU/admin_infra_server/blob/main/server-state/config/profiles.yml#L16-L28):
  신규 서버에 적용할 상태 기준과 순서를 정의한다.
- [복구 계획 생성](https://github.com/CSID-DGU/admin_infra_server/blob/main/server-state/script/cli.py#L89-L108)과
  [안전 수준별 처리](https://github.com/CSID-DGU/admin_infra_server/blob/main/server-state/script/cli.py#L145-L166):
  상태 기준의 변경 방법을 서버별 `DRY-RUN` 명령 또는 수동 절차로 변환한다.
- [`bootstrap_gpu_server.yml`](https://github.com/CSID-DGU/admin_infra_server/blob/main/server-state/ansible_playbook/bootstrap_gpu_server.yml):
  공통 OS, Docker, NVIDIA, Kubernetes와 network 설정을 실제 서버에 적용하는
  Ansible task를 제공한다.

## 4. 설정 구조

### 4.1 상태 기준과 작업 흐름

[`config/profiles.yml`](https://github.com/CSID-DGU/admin_infra_server/blob/main/server-state/config/profiles.yml)이
공통 상태와 작업 순서의 기준 파일이다.

| 설정 | 의미 |
| --- | --- |
| `profiles` | Docker, NVIDIA, network처럼 독립적으로 점검·복구할 수 있는 상태 기준 목록 |
| `owner_module` | 해당 기준과 실제 변경 절차를 관리하는 모듈 |
| `checks` | 서버 상태를 읽거나 필수 값의 존재 여부를 검사하는 항목 |
| `remediations` | 기준과 다를 때 사용할 명령 또는 수동 절차와 안전 수준 |
| `profile_sets` | 목적별로 실행할 상태 기준의 이름과 순서 |

현재 작업 흐름은 다음과 같다.

| 작업 흐름(profile set) | 용도 |
| --- | --- |
| `new-host-bootstrap` | 신규 서버의 표준 구축 순서 |
| `existing-host-drift` | 운영 서버의 공통 설정 점검·복구 순서 |
| `managed-host` | 운영 관리 서버에 사용하는 기본 작업 흐름 |
| `monitoring-host` | monitoring 영역만 점검할 때 사용하는 작업 흐름 |

새 공통 설정은 하나의 상태 기준으로 추가한 뒤 `new-host-bootstrap`과
`existing-host-drift`에 함께 배치한다. 순서는 선행 조건을 기준으로 정한다.
예를 들어 NVIDIA Container Toolkit은 NVIDIA driver와 Docker Engine이 준비된
뒤에 구성한다.

**관련 코드**

- [`profiles.yml`](https://github.com/CSID-DGU/admin_infra_server/blob/main/server-state/config/profiles.yml):
  `profile_sets`와 `profiles`의 실제 설정을 관리한다.
- [설정 로딩](https://github.com/CSID-DGU/admin_infra_server/blob/main/server-state/script/profiles.py#L69-L111):
  YAML의 작업 흐름, 상태 기준, 점검 항목과 복구 항목을 내부 모델로 변환한다.
- [작업 흐름 확장](https://github.com/CSID-DGU/admin_infra_server/blob/main/server-state/script/profiles.py#L42-L61):
  선택한 profile set을 중복 없는 순서 있는 상태 기준 목록으로 바꾼다.
- [서버별 값 반영](https://github.com/CSID-DGU/admin_infra_server/blob/main/server-state/script/profiles.py#L114-L143):
  상태 기준의 자리표시자를 선택한 서버의 실제 값으로 치환한다.

### 4.2 서버별 설정값

상태 기준에는 `{host}`, `{storage_interface}`, `{kerberos_realm}`처럼 서버마다
달라지는 값의 자리가 들어 있다. 이 값은 공용
[`servers.jsonl`](https://github.com/CSID-DGU/admin_infra_server/blob/main/user-lifecycle/server_info/servers.jsonl)과
domain 규칙에서 가져온다. 서버 목록과 접속 정보를 별도로 복제하지 않기 때문에
다른 운영 모듈과 같은 대상을 기준으로 작업할 수 있다.

**관련 코드**

- [`servers.jsonl`](https://github.com/CSID-DGU/admin_infra_server/blob/main/user-lifecycle/server_info/servers.jsonl):
  host, server ID, domain, SSH 접속 정보와 network interface를 저장하는 공용
  inventory다.
- [서버 정보와 파생값](https://github.com/CSID-DGU/admin_infra_server/blob/main/server-state/script/inventory.py#L14-L83):
  inventory 필드와 domain별 Kerberos, mount, Kubernetes 값을 하나의 서버
  정보로 제공한다.
- [inventory 로딩과 검증](https://github.com/CSID-DGU/admin_infra_server/blob/main/server-state/script/inventory.py#L86-L133):
  JSONL을 읽고 필수 필드가 있는지 검사한 뒤 서버 정보로 변환한다.

## 5. 코드 지도

아래 순서로 보면 설정이 실행 계획으로 바뀌는 흐름을 확인할 수 있다. 각 파일의
세부 함수보다 **설정, 서버 정보, 조정, 실제 적용** 사이의 경계를 이해하는 것이
중요하다.

| 파일·디렉터리 | 역할 |
| --- | --- |
| [`config/profiles.yml`](https://github.com/CSID-DGU/admin_infra_server/blob/main/server-state/config/profiles.yml) | 상태 기준과 작업 흐름을 선언하는 기준 파일 |
| [`script/profiles.py`](https://github.com/CSID-DGU/admin_infra_server/blob/main/server-state/script/profiles.py) | 설정 파일을 읽고 작업 흐름을 상태 기준 목록으로 확장하며 서버별 값을 반영한다. |
| [`script/inventory.py`](https://github.com/CSID-DGU/admin_infra_server/blob/main/server-state/script/inventory.py) | 공용 inventory를 읽어 대상 서버를 선택하고 서버별 설정값을 제공한다. |
| [`script/cli.py`](https://github.com/CSID-DGU/admin_infra_server/blob/main/server-state/script/cli.py) | CLI 입력, 서버 선택과 상태 기준을 조합하여 점검 결과와 복구 계획을 출력한다. |
| [`bin/server-state`](https://github.com/CSID-DGU/admin_infra_server/blob/main/server-state/bin/server-state), [`script/__main__.py`](https://github.com/CSID-DGU/admin_infra_server/blob/main/server-state/script/__main__.py) | shell과 Python에서 CLI를 시작하는 진입점 |
| [`ansible_playbook/`](https://github.com/CSID-DGU/admin_infra_server/tree/main/server-state/ansible_playbook) | `server-state`가 직접 소유하는 공통 서버 설정을 실제 host에 적용한다. 다른 영역은 담당 모듈의 playbook을 사용한다. |
| [`tests/`](https://github.com/CSID-DGU/admin_infra_server/tree/main/server-state/tests) | inventory 선택, 설정 로딩, 작업 흐름 순서와 서버별 값 반영을 검증한다. |

## 6. 주요 설계 결정

| 결정 | 이유 |
| --- | --- |
| 공통 상태를 `profiles.yml`에 선언한다. | 점검 기준과 복구 방법을 한곳에서 확인하고, 서버별 절차가 서로 달라지는 것을 줄이기 위해서다. |
| 운영 서버 점검과 신규 서버 구축이 같은 상태 기준을 사용한다. | 신규 서버에 적용한 설정이 운영 서버 점검에서 빠지거나 그 반대가 되는 것을 방지하기 위해서다. |
| 서버별 값은 공용 inventory에서 가져온다. | host, IP, domain과 network 정보를 여러 위치에서 중복 관리하지 않기 위해서다. |
| 영역별 담당 모듈을 명시하고 기존 절차를 연결한다. | `server-state`에 운영 로직을 복제하지 않고, 각 모듈의 안전 절차와 변경 책임을 유지하기 위해서다. |
| 원격 점검과 복구는 계획을 먼저 보여준다. | driver 변경, Kubernetes join, keytab과 mount처럼 서비스에 영향을 줄 수 있는 작업을 관리자가 검토한 뒤 실행하도록 하기 위해서다. |

이 구조에서 `server-state`의 역할은 모든 작업을 대신 구현하는 것이 아니라,
서버가 따라야 할 기준과 순서를 일관되게 유지하고 실제 변경 책임을 명확한 코드
영역으로 연결하는 것이다.
