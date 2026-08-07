# server-state 설계

> [개요](index.md) · [운영](operations.md)

> **GitHub 코드 링크:** `admin_infra_server`는 비공개 저장소다. 링크를 누르면
> GitHub 로그인 화면을 거쳐 해당 파일과 line으로 이동한다. 조직 저장소에 접근
> 권한이 있는 계정으로 로그인해야 한다.

## 1. 개요

FARM/LAB GPU 서버는 OS 공통 패키지, Docker, NVIDIA driver/runtime,
Kubernetes, storage network, Kerberos/NFS와 monitoring 설정을 공통으로
사용한다. 운영 기준과 설정 작업이 여러 playbook에 흩어져 있으면 신규 서버를
구성할 때 일부 단계가 빠지기 쉽고, 운영 서버가 기준에서 벗어났을 때도 서버마다
다른 방법으로 점검하게 된다.

`server-state`는 이 문제를 해결하기 위해 다음 정보를 하나의 운영 정책으로
연결한다.

1. **운영 서버 점검**: 선택한 서버가 각 구성요소의 목표 상태를 만족하는지
   읽기 전용 Ansible 작업으로 점검한다.
2. **신규 서버 구성**: 같은 구성요소 순서에 따라 예상 변경을 확인하고, 안전
   수준에 맞는 승인 후 목표 상태를 적용한다.

여기서 **구성요소(component)**는 독립적으로 점검하고 구성할 수 있는 운영
상태의 단위다. 예를 들어 `docker-engine` 구성요소는
"Docker가 설치되어 있고, service와 daemon이 정상이며, systemd cgroup driver를
사용한다"는 하나의 목표 상태를 뜻한다.

## 2. 설계 구조

`server-state`는 공통 운영 기준과 실행 코드를 파일 역할에 따라 구분한다.

| 계층 | 저장 위치 | 역할 |
| --- | --- | --- |
| 정책 | `policy/standard-gpu-server.yml` | 관리 서버에 필요한 구성요소와 실행 순서를 기록한다. |
| 구성요소 정의 | `components/*.yml` | 구성요소별 목표 상태, 담당 모듈, 점검·설정 방법과 적용 승인 수준을 기록한다. |
| 서버·환경 정보 | 공용 `servers.jsonl`, `config/environments.yml` | 서버 접속·network 정보와 FARM/LAB별 Kerberos, NFS, Kubernetes 값을 제공한다. |
| 명령 구성 | `server_state/` Python package | 대상 서버에 맞는 playbook, tag와 서버별 변수를 조합한다. |
| Ansible 작업 | `ansible/roles/`와 담당 모듈 playbook | 구성요소별 점검과 서버 설정을 수행한다. |
| 실행 파일 | `bin/server-state` | 정책 조회, 서버 점검, 변경 계획과 설정 적용 명령을 시작한다. |

관리자가 실행하는 CLI는 [`bin/server-state`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fbin%2Fserver-state)다.
내부 코드는 모듈 이름과 같은 `server_state/` Python package에 두고,
`commands.py`, `catalog.py`, `inventory.py`, `planner.py`가 각각 명령 처리,
정책 로딩, 서버 정보 처리, Ansible 명령 구성을 담당한다.

처리 순서는 다음과 같다.

1. 공용 inventory에서 `--hosts`에 맞는 서버를 선택한다.
2. 정책에서 `--component`에 맞는 구성요소를 정책 순서대로 선택한다.
3. FARM/LAB 설정을 서버 정보와 결합해 Kerberos principal, NFS mount,
   Kubernetes context 등의 실행값을 만든다.
4. 각 구성요소 정의에서 `audit` 또는 `converge` playbook과 tag를 선택한다.
5. 완성된 Ansible 명령을 화면에 보여주거나 실행한다.

정책과 실제 task를 분리했기 때문에 전체 서버가 따라야 할 순서는 한곳에서 읽을
수 있고, Docker·Kerberos/NFS·monitoring 같은 구현은 각각의 소유 위치에서
수정할 수 있다. 점검과 설정 명령은 각 모듈의 Ansible task 파일에서 관리한다.

## 3. 정책 구성과 소유권

[`standard-gpu-server.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fpolicy%2Fstandard-gpu-server.yml%23L1-L15)은
다음 구성요소를 선행 조건에 맞는 순서로 사용한다.

| 순서 | 구성요소 | 담당 모듈 | 서버가 갖춰야 할 상태 | 적용 방식 |
| ---: | --- | --- | --- | --- |
| 1 | `baseline-access` | `server-state` | inventory 정보, hostname, SSH와 sudo 접속 조건이 준비되어 있다. | 수동 준비 |
| 2 | `os-common` | `server-state` | 지원 Ubuntu와 공통 package가 설치되어 있다. | 즉시 적용 가능 |
| 3 | `docker-engine` | `server-state` | Docker service가 실행되고 daemon이 systemd cgroup driver를 사용한다. | 검토 후 적용 |
| 4 | `nvidia-driver` | `server-state` | 지정 NVIDIA driver가 설치되어 GPU를 인식하고 package가 hold되어 있다. | 고위험 검토 후 적용 |
| 5 | `nvidia-runtime` | `server-state` | NVIDIA Container Toolkit이 Docker와 containerd에 연결되어 있다. | 검토 후 적용 |
| 6 | `kubernetes-packages` | `server-state` | kubeadm, kubelet, kubectl이 설치·hold되고 kubelet service가 활성화되어 있다. | 검토 후 적용 |
| 7 | `kubernetes-membership` | `server-state` | 서버가 지정 cluster에 join되고 FARM/LAB domain label을 가진다. | 수동 작업 |
| 8 | `storage-network` | `server-state` | storage NIC의 RX queue가 재부팅 후에도 4096으로 설정된다. | 즉시 적용 가능 |
| 9 | `kerberos-nfs` | `kerberos-nfs` | host Kerberos 인증과 NFS service 인증이 성공하고 공유 경로가 `sec=krb5`로 mount된다. | 검토 후 적용 |
| 10 | `monitoring` | `monitoring` | exporter service가 실행되고 metrics·health endpoint가 응답한다. | 즉시 적용 가능 |
| 11 | `user-container` | `user-lifecycle` | user-lifecycle이 DB와 Docker를 사용해 사용자 container를 관리할 수 있다. | 수동 작업 |

담당 모듈은 구성요소의 점검·설정 코드와 운영 절차를 관리하는 책임 주체다.
공통 host 설정은 `server-state/ansible/roles/`, Kerberos/NFS 점검과 role은
`kerberos-nfs/`, exporter 점검·배포는 `monitoring/`, 사용자 container
전제조건은 `user-lifecycle/`에서 관리한다. `server-state`는 각 모듈의 실행
파일을 연결하여 전체 순서와 책임 범위를 함께 보여준다.

### 3.1 운영 서버 점검

운영 서버 점검은 대상 서버의 현재 상태를 정책의 목표 상태와 비교한다. `audit`은
각 구성요소의 점검 playbook을 정책 순서대로 실행한다. catalog는 모든 audit의
안전 수준이 `safe`인지 확인한다.

`server-state`가 소유하는 구성요소는
[`ansible/playbooks/audit.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fansible%2Fplaybooks%2Faudit.yml%23L1-L54)이
해당 role의 `tasks/audit.yml`을 선택한다. 예를 들어 Docker 점검은
[`docker_engine/tasks/audit.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fansible%2Froles%2Fdocker_engine%2Ftasks%2Faudit.yml%23L1-L13)에서
service 활성 상태, daemon 응답, cgroup driver를 읽는다. Kerberos/NFS와
monitoring은 각각
[`kerberos-nfs/ansible/audit_client.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fkerberos-nfs%2Fansible%2Faudit_client.yml)과
[`monitoring/ansible_playbook/audit_exporters.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fmonitoring%2Fansible_playbook%2Faudit_exporters.yml)을
직접 사용한다.

점검은 실제 서버에 접속해 읽기 전용 task를 수행한다. `--show-command`는 생성된
명령을 화면에 출력한다. 명령 확인과 점검 실행이 같은 audit 정의를 사용하므로
동일한 playbook, tag와 서버 변수가 사용된다.

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

Kubernetes join은 짧은 수명의 token, cluster 선택과 controller 승인을 사용한다.
`kubernetes-membership`은 이 값을 관리자가 확인하는 수동 절차로 진행한다.
`baseline-access`는 Ansible 실행 전 준비 작업으로 진행하고, `user-container`는
`user-lifecycle` 운영 절차로 진행한다. 수동 구성요소가 포함된 `apply` 요청은
Ansible 실행 전 단계에서 종료된다.

## 4. 설정 구조

### 4.1 정책과 구성요소

정책 파일은 구성요소 ID와 실행 순서를 관리한다. 각 구성요소 파일은 목표 상태와
실행 방법을 관리한다. 이 구분을 통해 전체 순서와 구성요소별 내용을 각각 한
위치에서 확인할 수 있다.

`audit`은 현재 서버 상태를 읽고 목표 상태 충족 여부를 확인하는 작업이다.
`converge`는 package, 설정 파일과 service를 목표 상태에 맞추는 작업이다.

각 `components/<id>.yml`은 다음 정보를 가진다.

| 필드 | 의미 |
| --- | --- |
| `id` | CLI의 `--component`에서 사용하는 이름 |
| `owner` | 점검·설정 코드와 운영 절차를 관리하는 모듈 |
| `desired_state` | 점검과 설정이 기준으로 사용하는 서버 상태 |
| `audit` | 점검에 사용할 playbook과 tag |
| `converge` | 설정에 사용할 playbook과 tag 또는 수동 절차, 적용 승인 수준 |

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

이 정의를 사용하는 흐름은 다음과 같다.

1. `audit`은 `audit.yml`에 `docker-engine` tag를 전달한다.
2. audit playbook은 `docker_engine/tasks/audit.yml`을 실행해 Docker service,
   daemon 응답과 cgroup driver를 점검한다.
3. `plan`과 `apply`는 `converge.yml`에 `docker-engine,cgroups` tag를 전달한다.
4. converge playbook은 `docker_engine/tasks/main.yml`을 실행해 Docker package,
   `daemon.json`과 service를 설정한다.

구성요소 파일은 목표 상태와 실행 위치를 연결하고, role의 task 파일은 점검과
설정 절차를 구현한다.

[`catalog.py`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fserver_state%2Fcatalog.py%23L19-L147)는
정책과 구성요소를 읽으면서 ID 중복, 구성요소 누락, 실행 종류, 안전 수준과
audit의 `safe` 설정을 확인한다. 선택된 구성요소는 정책에 기록된 순서로
정렬된다.

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
만든다. FARM/LAB 규칙은 설정 파일에 모여 있어 각 값의 출처를 바로 확인할 수
있다.

### 4.3 실행 계획과 안전 수준

[`planner.py`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fserver_state%2Fplanner.py%23L15-L120)는
대상 서버, 구성요소와 FARM/LAB 설정을 결합해 Ansible 명령을 만든다. 명령에는
inventory 경로, playbook, 대상 host, tag와 서버별 extra vars가 포함된다.
`plan`에는 `--check --diff`가 추가되고, 수동 구성요소에는 운영 문서 경로가
표시된다.

구성 안전 수준은 다음과 같다.

| 수준 | 적용 조건 | 예시 |
| --- | --- | --- |
| `safe` | `apply --execute` | 공통 package, storage RX queue, exporter 배포 |
| `gated` | `--approve-gated` 또는 더 강한 `--approve-risky` 추가 | Docker, NVIDIA runtime, Kubernetes package, Kerberos/NFS |
| `risky` | `--approve-risky` 추가 | NVIDIA driver |
| 수동 | reference에 표시된 운영 절차 사용 | 초기 접속 조건, Kubernetes join, 사용자 container 전제조건 구성 |

[`commands.py`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fserver_state%2Fcommands.py%23L150-L230)는
`audit`, `plan`, `apply`를 동일한 계획 모델로 처리한다. `apply`는 실행 전 모든
항목의 실행 방식과 승인 수준을 확인한다. 전체 항목이 실행 조건을 충족하면
Ansible 작업을 시작하고, 수동 작업이나 추가 승인이 필요하면 상태와 안내를
출력한 뒤 실행 전 단계에서 종료한다.

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
