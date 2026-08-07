# server-state 설계

> [개요](index.md) · [운영](operations.md)

> **GitHub 코드 링크:** `admin_infra_server`는 비공개 저장소다. 링크를 누르면
> GitHub 로그인 화면을 거쳐 해당 파일과 line으로 이동한다. 조직 저장소에 접근
> 권한이 있는 계정으로 로그인해야 한다.

## 1. 개요

FARM/LAB GPU 서버는 OS 공통 패키지, Docker, NVIDIA driver/runtime,
Kubernetes, storage network, Kerberos/NFS와 monitoring 설정을 공통으로
사용한다. 이 기준과 실제 구현이 여러 playbook에 흩어져 있기만 하면 신규 서버를
구성할 때 일부 단계가 빠지기 쉽고, 운영 서버가 기준에서 벗어났을 때도 서버마다
다른 방법으로 점검하게 된다.

`server-state`는 이 문제를 해결하기 위해 다음 정보를 하나의 운영 정책으로
연결한다.

1. **운영 서버 점검**: 선택한 서버가 각 구성요소의 목표 상태를 만족하는지
   읽기 전용 Ansible 작업으로 점검한다.
2. **신규 서버 구성**: 같은 구성요소 순서에 따라 예상 변경을 확인하고, 안전
   수준에 맞는 승인 후 목표 상태를 적용한다.

여기서 **구성요소(component)**는 서버 묶음이 아니라 독립적으로 점검하고
구성할 수 있는 운영 상태의 단위다. 예를 들어 `docker-engine` 구성요소는
"Docker가 설치되어 있고, service와 daemon이 정상이며, systemd cgroup driver를
사용한다"는 하나의 목표 상태를 뜻한다.

## 2. 설계 구조

`server-state`는 기준, 서버별 값, 실행 계획, 실제 구현을 다음과 같이 분리한다.

| 계층 | 저장 위치 | 역할 |
| --- | --- | --- |
| 정책 | `policy/standard-gpu-server.yml` | 모든 관리 서버에 필요한 구성요소와 적용 순서를 정의한다. |
| 구성요소 명세 | `components/*.yml` | 각 구성요소의 목표 상태, 담당 모듈, 점검·구성 진입점과 안전 수준을 정의한다. |
| 서버·환경 설정 | 공용 `servers.jsonl`, `config/environments.yml` | 대상 서버의 접속·network 정보와 FARM/LAB별 Kerberos, NFS, Kubernetes 값을 제공한다. |
| 실행 계획 | `server_state/` Python package | 입력을 검증하고 대상 서버와 구성요소를 결합하여 안전한 Ansible 인자 배열을 만든다. |
| 실제 구현 | `ansible/roles/`와 담당 모듈 playbook | 서버 상태를 읽거나 목표 상태에 맞게 구성한다. |
| 사용자 진입점 | `bin/server-state` | `describe`, `audit`, `plan`, `apply` 명령을 제공한다. |

사용자가 실행하는 파일은 [`bin/server-state`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fbin%2Fserver-state) 하나다.
내부 Python 구현은 기능별로 `commands.py`, `catalog.py`, `inventory.py`,
`planner.py`에 나뉜다. `cli/`나 `run/`처럼 실행 방식만 나타내는 디렉터리를
추가하지 않고 모듈 이름과 같은 `server_state/` package에 둔 이유는, 이 코드가
명령 실행뿐 아니라 정책 검증·서버 정보 해석·계획 생성을 함께 담당하기 때문이다.

처리 순서는 다음과 같다.

1. 공용 inventory에서 `--hosts`에 맞는 서버를 선택한다.
2. 정책에서 `--component`에 맞는 구성요소를 정책 순서대로 선택한다.
3. FARM/LAB 설정을 서버 정보와 결합해 Kerberos principal, NFS mount,
   Kubernetes context 등의 실행값을 만든다.
4. 각 구성요소 명세에서 현재 명령에 맞는 `audit` 또는 `converge` 진입점을
   선택한다.
5. `ansible-playbook` 인자와 extra vars를 배열로 만들고, 명령에 따라 출력하거나
   실행한다.

정책과 실제 task를 분리했기 때문에 전체 서버가 따라야 할 순서는 한곳에서 읽을
수 있고, Docker·Kerberos/NFS·monitoring 같은 구현은 각각의 소유 위치에서
수정할 수 있다. Python 코드에는 긴 점검·복구 shell 명령을 저장하지 않는다.

## 3. 정책 구성과 소유권

[`standard-gpu-server.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fpolicy%2Fstandard-gpu-server.yml%23L1-L15)은
다음 구성요소를 선행 조건에 맞는 순서로 사용한다.

| 순서 | 구성요소 | 담당 모듈 | 목표 상태 | 구성 안전 수준 |
| ---: | --- | --- | --- | --- |
| 1 | `baseline-access` | `server-state` | inventory, Ansible 접속, 비대화형 sudo와 hostname이 일치한다. | 수동·승인 필요 |
| 2 | `os-common` | `server-state` | 지원 Ubuntu와 공통 package가 준비되어 있다. | 안전 |
| 3 | `docker-engine` | `server-state` | Docker service와 daemon이 정상이고 systemd cgroup driver를 사용한다. | 승인 필요 |
| 4 | `nvidia-driver` | `server-state` | GPU를 인식하는 지정 driver가 설치·hold되어 있다. | 고위험 승인 필요 |
| 5 | `nvidia-runtime` | `server-state` | NVIDIA Container Toolkit이 Docker와 containerd에 설정되어 있다. | 승인 필요 |
| 6 | `kubernetes-packages` | `server-state` | kubeadm, kubelet, kubectl이 설치·hold되고 kubelet이 활성화되어 있다. | 승인 필요 |
| 7 | `kubernetes-membership` | `server-state` | 올바른 cluster에 join되어 있고 domain label이 설정되어 있다. | 수동·고위험 |
| 8 | `storage-network` | `server-state` | inventory의 storage NIC RX queue를 4096으로 유지한다. | 안전 |
| 9 | `kerberos-nfs` | `kerberos-nfs` | machine identity와 NFS service ticket이 유효하고 `sec=krb5` mount가 정상이다. | 승인 필요 |
| 10 | `monitoring` | `monitoring` | exporter service와 metrics·health endpoint가 정상이다. | 안전 |
| 11 | `user-container` | `user-lifecycle` | 관리형 사용자 container 작업에 필요한 DB 설정과 Docker 접근이 준비되어 있다. | 수동·승인 필요 |

담당 모듈은 단순한 문서 분류가 아니다. 구성요소 명세의 `owner`와 실제 파일
위치가 일치한다. 공통 host 설정은 `server-state/ansible/roles/`에 있고,
Kerberos/NFS 점검과 role은 `kerberos-nfs/`, exporter 점검·배포는
`monitoring/`, 사용자 container 전제조건은 `user-lifecycle/`에 있다. 다른
모듈이 이미 가진 로직을 `server-state`에 복사하지 않으므로 수정 책임과
rollback 범위가 분명해진다.

### 3.1 운영 서버 점검

운영 서버 점검은 대상 서버가 정책의 목표 상태에서 벗어난 부분을 구성요소
단위로 찾는다. `audit`은 서버와 구성요소를 정책 순서대로 결합하고 각 명세의
`audit` 진입점을 실행한다. 모든 audit 명세는 `safe`여야 하며, catalog를 읽을
때 이 조건을 검증한다.

`server-state`가 소유하는 구성요소는
[`ansible/playbooks/audit.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fansible%2Fplaybooks%2Faudit.yml%23L1-L54)이
해당 role의 `tasks/audit.yml`을 선택한다. 예를 들어 Docker 점검은
[`docker_engine/tasks/audit.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fansible%2Froles%2Fdocker_engine%2Ftasks%2Faudit.yml%23L1-L13)에서
service 활성 상태, daemon 응답, cgroup driver를 읽는다. Kerberos/NFS와
monitoring은 각각
[`kerberos-nfs/ansible/audit_client.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fkerberos-nfs%2Fansible%2Faudit_client.yml)과
[`monitoring/ansible_playbook/audit_exporters.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fmonitoring%2Fansible_playbook%2Faudit_exporters.yml)을
직접 사용한다.

점검은 기본적으로 실제 서버에 접속해 읽기 전용 task를 수행한다.
`--show-command`를 사용하면 접속하지 않고 생성된 명령만 확인할 수 있다. 이 두
동작을 같은 audit 정의에서 제공하므로, 화면에서 검토한 명령과 실제로 실행되는
명령이 달라지지 않는다.

### 3.2 신규 서버 구성

신규 서버 구성은 Ubuntu 설치, IP·hostname, SSH, 비대화형 sudo와 inventory
등록이 끝난 서버를 시작점으로 한다. `plan`은 각 구성요소의 `converge` 진입점을
Ansible `--check --diff`로 실행하여 예상 변경을 확인한다. `apply`는 같은
진입점을 실제 모드로 실행하되 명세의 안전 수준에 따라 명시적인 승인을 요구한다.

`server-state` 소유 구성요소의 구성 순서는
[`ansible/playbooks/converge.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fansible%2Fplaybooks%2Fconverge.yml%23L1-L25)에
role로 선언되어 있다. 각 role의 `tasks/main.yml`이 실제 설정을 맡는다. 예를
들어 [`docker_engine/tasks/main.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fansible%2Froles%2Fdocker_engine%2Ftasks%2Fmain.yml)은
apt source와 package, `daemon.json`, service 상태를 관리한다.

Kubernetes join은 짧은 수명의 token과 cluster 선택이 필요하고, 잘못 적용하면
scheduler와 workload에 영향을 준다. 따라서 `kubernetes-membership`의 구성은
자동 명령이 아니라 수동 절차로 남긴다. `baseline-access`와 `user-container`도
저장소의 값만으로 안전하게 완성할 수 없으므로 수동 진입점을 사용한다. 수동
구성요소가 포함된 `apply` 요청은 일부만 먼저 실행하지 않고 전체 요청을
중단한다.

## 4. 설정 구조

### 4.1 정책과 구성요소

정책 파일은 구성요소 ID와 순서만 가진다. 목표 상태나 실행 방법을 정책에
반복해서 적지 않으므로, 구성요소의 구현을 바꾸더라도 전체 순서는 그대로 유지할
수 있다.

각 `components/<id>.yml`은 다음 정보를 가진다.

| 필드 | 의미 |
| --- | --- |
| `id` | 파일 이름과 일치하는 구성요소 식별자 |
| `owner` | 해당 상태와 구현을 관리하는 모듈 |
| `desired_state` | 서버가 만족해야 할 목표 상태 |
| `audit` | 읽기 전용 점검 playbook, 선택 tag, host 변수와 `safe` 수준 |
| `converge` | 실제 구성 playbook 또는 수동 reference와 적용 안전 수준 |

예를 들어
[`components/docker-engine.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fcomponents%2Fdocker-engine.yml%23L1-L13)은
다음처럼 연결된다.

```yaml
id: docker-engine
owner: server-state
desired_state: Docker Engine is installed, enabled, responsive, and configured with the systemd cgroup driver.
audit:
  kind: ansible-playbook
  playbook: server-state/ansible/playbooks/audit.yml
  tags: [docker-engine]
  safety: safe
converge:
  kind: ansible-playbook
  playbook: server-state/ansible/playbooks/converge.yml
  tags: [docker-engine, cgroups]
  safety: gated
```

이 명세 안에 점검 command나 복구 task 자체가 들어 있는 것은 아니다. `audit`과
`converge`는 **어느 구현을 실행할지 가리키는 진입점**이고, 실제 내용은
`docker_engine/tasks/audit.yml`과 `docker_engine/tasks/main.yml`에 있다.
명세는 목표와 실행 경로를 설명하고, role은 구현을 담당하도록 나눈 것이다.

[`catalog.py`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fserver_state%2Fcatalog.py%23L19-L147)는
정책과 구성요소를 내부 모델로 읽으면서 중복 ID, 누락된 구성요소, 잘못된 실행
종류·안전 수준, 읽기 전용이 아닌 audit을 거부한다. 선택 순서는 사용자가
`--component`를 입력한 순서가 아니라 정책의 선행 조건 순서를 유지한다.

### 4.2 서버와 FARM/LAB 설정

서버별 사실과 환경별 운영값은 서로 다른 파일에서 관리한다.

| 출처 | 포함하는 값 |
| --- | --- |
| 공용 [`servers.jsonl`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fuser-lifecycle%2Fserver_info%2Fservers.jsonl) | host, server ID, domain, SSH 주소·port·계정, management/storage interface와 IP |
| [`config/environments.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fconfig%2Fenvironments.yml%23L1-L22) | FARM/LAB realm, Kerberos config, storage host와 mount, Kubernetes context, 공통 계산 규칙 |

[`inventory.py`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fserver_state%2Finventory.py%23L18-L219)는
inventory의 필수 필드를 검증하고 `all`, FARM/LAB, 개별 host/server ID를
선택한다. 그런 다음 server ID와 환경 설정을 결합해 machine principal, NFS
service principal, mount target, public health port 등의 Ansible extra vars를
만든다. FARM/LAB 규칙을 `Server` 객체나 command 문자열에 숨기지 않고 설정
파일로 분리했기 때문에 값의 출처를 코드 수정 없이 확인할 수 있다.

### 4.3 실행 계획과 안전 수준

[`planner.py`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fserver_state%2Fplanner.py%23L15-L120)는
서버별 context와 구성요소 진입점을 결합해 하나의 `PlanItem`을 만든다. 실행
명령은 shell 문자열이 아니라 argv tuple로 구성하고, 서버값은 JSON extra vars로
전달한다. `plan`일 때만 `--check --diff`를 추가하며, 수동 구성요소는 명령 대신
reference를 반환한다.

구성 안전 수준은 다음과 같다.

| 수준 | 적용 조건 | 예시 |
| --- | --- | --- |
| `safe` | `apply --execute` | 공통 package, storage RX queue, exporter 배포 |
| `gated` | `--approve-gated` 또는 더 강한 `--approve-risky` 추가 | Docker, NVIDIA runtime, Kubernetes package, Kerberos/NFS |
| `risky` | `--approve-risky` 추가 | NVIDIA driver |
| 수동 | CLI가 실행하지 않고 reference를 출력 | 초기 접속 조건, Kubernetes join, 사용자 container 전제조건 구성 |

[`commands.py`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fserver_state%2Fcommands.py%23L150-L230)는
`audit`, `plan`, `apply`를 동일한 계획 모델로 처리한다. `apply`는 실행 전 모든
항목을 먼저 검사한다. 승인되지 않았거나 수동인 항목이 하나라도 있으면 허용된
항목도 실행하지 않으므로, 부분 적용 후 중단되는 상태를 피한다.

## 5. 코드 위치

아래 순서로 보면 정책이 실제 Ansible 작업으로 이어지는 경계를 확인할 수 있다.

| 파일·디렉터리 | 역할 |
| --- | --- |
| [`policy/standard-gpu-server.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fpolicy%2Fstandard-gpu-server.yml) | 구성요소와 전체 적용 순서 |
| [`components/`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Ftree%2Fmain%2Fserver-state%2Fcomponents) | 구성요소별 목표 상태, owner, 진입점, 안전 수준 |
| [`server_state/catalog.py`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fserver_state%2Fcatalog.py) | 정책·구성요소 로딩, 검증과 순서 선택 |
| [`server_state/inventory.py`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fserver_state%2Finventory.py) | 서버 선택과 FARM/LAB 실행값 생성 |
| [`server_state/planner.py`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fserver_state%2Fplanner.py) | 서버·구성요소별 Ansible 실행 계획 생성 |
| [`server_state/commands.py`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fserver_state%2Fcommands.py) | CLI 입력, 안전 승인, subprocess 실행과 결과 출력 |
| [`ansible/playbooks/audit.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fansible%2Fplaybooks%2Faudit.yml) | `server-state` 소유 role의 읽기 전용 audit 순서 |
| [`ansible/playbooks/converge.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fansible%2Fplaybooks%2Fconverge.yml) | `server-state`와 Kerberos/NFS role의 구성 순서 |
| [`ansible/roles/`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Ftree%2Fmain%2Fserver-state%2Fansible%2Froles) | 공통 host 구성요소별 `audit.yml`과 `main.yml` |
| [`kerberos-nfs/ansible/`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Ftree%2Fmain%2Fkerberos-nfs%2Fansible) | Kerberos/NFS 점검과 client role |
| [`monitoring/ansible_playbook/audit_exporters.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fmonitoring%2Fansible_playbook%2Faudit_exporters.yml) | exporter service와 endpoint 점검 |
| [`monitoring/ansible_playbook/deploy_exporters.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fmonitoring%2Fansible_playbook%2Fdeploy_exporters.yml) | exporter build·배포·검증 |
| [`user-lifecycle/ansible_playbook/audit_host.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fuser-lifecycle%2Fansible_playbook%2Faudit_host.yml) | 사용자 container 작업의 host 전제조건 점검 |
| [`tests/`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Ftree%2Fmain%2Fserver-state%2Ftests) | 정책 순서, 설정 검증, server context, 계획과 안전 gate 테스트 |
