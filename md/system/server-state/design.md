# server-state 설계

> [개요](index.md) · [운영](operations.md)

> **GitHub 코드 링크:** `admin_infra_server`는 비공개 저장소다. 링크를 누르면
> GitHub 로그인 화면을 거쳐 해당 파일로 이동한다. 조직 저장소에 접근 권한이
> 있는 계정으로 로그인해야 한다.

## 1. 개요

`server-state`의 주요 목표는 FARM/LAB GPU 서버가 공통 운영 기준에 맞게
설정되어 있는지 일관된 방법으로 점검하는 것이다. 운영 기준은 OS 공통 패키지,
Docker, NVIDIA driver/runtime, Kubernetes, storage network, Kerberos/NFS와
monitoring의 목표 상태와 점검 순서를 정의한다.

각 구성요소에는 서버를 목표 상태로 만드는 설정 작업도 연결되어 있다. 같은
구성요소 순서로 예상 변경과 작업 영향을 확인하면 신규 서버를 공통 운영 기준에
맞게 구성할 때도 사용할 수 있다.

**구성요소(component)**는 독립적으로 점검하고 설정할 수 있는 운영 상태의
단위다. 예를 들어 `docker-engine`은 Docker 설치, service, daemon과 cgroup
driver 상태를 하나의 구성요소로 관리한다.

## 2. 설계 구조

| 구분 | 저장 위치 | 역할 |
| --- | --- | --- |
| 정책 | `policy/standard-gpu-server.yml` | 구성요소와 실행 순서를 기록한다. |
| 구성요소 정의 | `components/*.yml` | 목표 상태, 점검 방법, 설정 방법과 승인 수준을 기록한다. |
| 서버·환경 정보 | `servers.jsonl`, `config/environments.yml` | 서버 접속·network 정보와 FARM/LAB별 설정값을 제공한다. |
| 명령 구성 | `server_state/` | 대상 서버에 맞는 playbook, tag와 변수를 조합한다. |
| Ansible 작업 | `ansible/roles/`와 playbook | 구성요소별 점검과 서버 설정을 수행한다. |
| 실행 파일 | `bin/server-state` | `describe`, `audit`, `plan`, `apply` 명령을 시작한다. |

처리 순서는 다음과 같다.

1. `--hosts`로 대상 서버를 선택한다.
2. `--component`로 구성요소를 선택한다.
3. 서버 정보와 FARM/LAB 설정을 결합해 실행값을 만든다.
4. 구성요소에 연결된 audit 또는 converge playbook을 선택한다.
5. Ansible 명령을 화면에 보여주거나 실행한다.

## 3. 구성요소

[`standard-gpu-server.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fpolicy%2Fstandard-gpu-server.yml%23L1-L14)은
10개 구성요소의 실행 순서를 정의한다. 모든 구성요소는 `server-state` 정책과
CLI에서 관리한다.

각 구성요소는 서버의 현재 상태를 점검하는 작업과, 서버를 목표 상태에 맞게
설정하는 작업을 정의한다. 설정 작업에는 실행 형태와 안전 수준이 각각 지정된다.

| 실행 형태 | 동작 |
| --- | --- |
| `ansible-playbook` | `plan`으로 예상 변경을 확인하고 `apply`로 설정 playbook을 실행한다. |
| `manual` | CLI가 운영 절차를 표시하고 관리자가 해당 절차를 수행한다. |

| 안전 수준 | 실행 조건 |
| --- | --- |
| `safe` | `apply --execute`로 실행한다. |
| `gated` | 운영 영향을 확인하고 `--approve-gated`로 승인한다. |
| `risky` | 작업 영향과 운영 일정을 확인하고 `--approve-risky`로 승인한다. |

### 3.1 `baseline-access`

**목표 상태:** 서버가 inventory와 Ansible inventory에 등록되어 있고, 설정된
hostname으로 SSH 접속과 비대화형 sudo를 사용할 수 있다.

**점검:** Ansible ping으로 접속을 확인하고, `sudo -n true` 실행과 실제
hostname·inventory hostname 일치 여부를 확인한다.

**설정:** IP, hostname, SSH key, 관리 계정과 sudo 권한을 준비하고 두
inventory에 서버를 등록한다.

**설정 실행:** `manual`, `gated`. 관리자가 준비 절차를 수행한다. 이 구성요소는
이후 Ansible 작업을 실행하기 위한 선행 조건이다.

관련 코드: [`baseline-access.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fcomponents%2Fbaseline-access.yml),
[`baseline_access/tasks/audit.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fansible%2Froles%2Fbaseline_access%2Ftasks%2Faudit.yml)

### 3.2 `os-common`

**목표 상태:** 서버가 지원 Ubuntu release를 사용하고, 다른 구성요소에 필요한
공통 package가 설치되어 있다. 주요 package는 `curl`, `gnupg`, `ethtool`,
`krb5-user`, `nfs-common`, `keyutils`, `adcli`와 `python3`이다.

**점검:** OS 종류와 version을 확인하고 package facts에서 필수 package를
하나씩 확인한다.

**설정:** apt cache를 갱신하고 공통 package 목록을 설치한다.

**설정 실행:** `ansible-playbook`, `safe`. `apply --execute`가 package 설치
task를 실행한다.

관련 코드: [`os-common.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fcomponents%2Fos-common.yml),
[`os_common/tasks/audit.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fansible%2Froles%2Fos_common%2Ftasks%2Faudit.yml),
[`os_common/tasks/main.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fansible%2Froles%2Fos_common%2Ftasks%2Fmain.yml)

### 3.3 `docker-engine`

**목표 상태:** Docker Engine package가 설치되고 service가 활성화·실행되며,
daemon이 응답하고 `systemd` cgroup driver를 사용한다. `daemon.json`에는
`overlay2`, `json-file`과 log size 설정이 포함된다.

**점검:** Docker service의 enabled·active 상태, `docker info` 응답과 cgroup
driver 값을 확인한다.

**설정:** Docker apt key와 repository를 등록하고 Engine package를 설치한다.
기존 `daemon.json`에 필요한 값을 병합하고 변경된 경우 Docker service를
재시작한다.

**설정 실행:** `ansible-playbook`, `gated`. package source와 daemon 설정 변경,
service 재시작 가능성을 확인한 뒤 `--approve-gated`로 승인한다.

관련 코드: [`docker-engine.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fcomponents%2Fdocker-engine.yml),
[`docker_engine/tasks/audit.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fansible%2Froles%2Fdocker_engine%2Ftasks%2Faudit.yml),
[`docker_engine/tasks/main.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fansible%2Froles%2Fdocker_engine%2Ftasks%2Fmain.yml)

### 3.4 `nvidia-driver`

**목표 상태:** 정책에 지정된 NVIDIA driver package가 설치되고 GPU를 정상
인식하며, 해당 package가 apt hold 상태로 유지된다.

**점검:** `nvidia-smi`로 GPU 이름과 driver version을 읽고 `apt-mark
showhold`에서 NVIDIA driver package를 확인한다.

**설정:** 지정 driver package를 설치하고 apt hold를 설정한다.

**설정 실행:** `ansible-playbook`, `risky`. driver 변경은 GPU workload와 reboot
일정에 영향을 줄 수 있으므로 `plan` 결과와 서버 운영 일정을 확인한 뒤
`--approve-risky`로 승인한다.

관련 코드: [`nvidia-driver.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fcomponents%2Fnvidia-driver.yml),
[`nvidia_driver/tasks/audit.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fansible%2Froles%2Fnvidia_driver%2Ftasks%2Faudit.yml),
[`nvidia_driver/tasks/main.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fansible%2Froles%2Fnvidia_driver%2Ftasks%2Fmain.yml)

### 3.5 `nvidia-runtime`

**목표 상태:** NVIDIA Container Toolkit이 설치되고 Docker와 containerd가
NVIDIA runtime을 사용할 수 있다.

**점검:** `nvidia-ctk` 설치, Docker runtime 목록과 containerd 설정의 NVIDIA
runtime 항목을 확인한다.

**설정:** NVIDIA repository와 toolkit package를 설치하고 `nvidia-ctk runtime
configure`를 Docker와 containerd에 실행한다. 설정 변경 후 관련 service를
재시작한다.

**설정 실행:** `ansible-playbook`, `gated`. container runtime 설정과 service
재시작 영향을 확인한 뒤 `--approve-gated`로 승인한다.

관련 코드: [`nvidia-runtime.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fcomponents%2Fnvidia-runtime.yml),
[`nvidia_runtime/tasks/audit.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fansible%2Froles%2Fnvidia_runtime%2Ftasks%2Faudit.yml),
[`nvidia_runtime/tasks/main.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fansible%2Froles%2Fnvidia_runtime%2Ftasks%2Fmain.yml)

### 3.6 `kubernetes-packages`

**목표 상태:** 정책 version의 `kubeadm`, `kubelet`, `kubectl` package가
설치·hold되고 kubelet service가 활성화되어 있다.

**점검:** 세 package의 설치 여부와 kubelet enabled 상태를 확인한다.

**설정:** Kubernetes apt key와 repository를 등록하고 세 package를 설치·hold한
뒤 kubelet을 활성화한다.

**설정 실행:** `ansible-playbook`, `gated`. Kubernetes package version과
kubelet 영향을 확인한 뒤 `--approve-gated`로 승인한다.

관련 코드: [`kubernetes-packages.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fcomponents%2Fkubernetes-packages.yml),
[`kubernetes_packages/tasks/audit.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fansible%2Froles%2Fkubernetes_packages%2Ftasks%2Faudit.yml),
[`kubernetes_packages/tasks/main.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fansible%2Froles%2Fkubernetes_packages%2Ftasks%2Fmain.yml)

### 3.7 `kubernetes-membership`

**목표 상태:** 서버가 FARM 또는 LAB의 지정 Kubernetes cluster에 join되고,
node에 해당 domain label이 설정되어 있다.

**점검:** 서버의 kubelet credential 파일을 확인하고 controller에서 node와
domain label을 조회한다.

**설정:** 관리자가 cluster, join token과 node 정보를 확인한 뒤 승인된
`kubeadm join` 명령을 실행한다.

**설정 실행:** `manual`, `risky`. join token의 유효 시간과 cluster 선택을
관리자가 확인한다.

관련 코드: [`kubernetes-membership.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fcomponents%2Fkubernetes-membership.yml),
[`kubernetes_membership/tasks/audit.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fansible%2Froles%2Fkubernetes_membership%2Ftasks%2Faudit.yml),
[`kubernetes_membership/tasks/main.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fansible%2Froles%2Fkubernetes_membership%2Ftasks%2Fmain.yml)

### 3.8 `storage-network`

**목표 상태:** inventory에 storage interface가 기록되고, 해당 NIC의 RX queue를
4096으로 설정하는 systemd service가 활성화되어 있다.

**점검:** storage interface 값, 현재 RX queue 크기와
`decs-rx-queue.service` enabled 상태를 확인한다.

**설정:** RX queue를 설정하는 oneshot systemd unit을 설치하고 활성화한다.

**설정 실행:** `ansible-playbook`, `safe`. `apply --execute`가 systemd unit
설치와 활성화 task를 실행한다.

관련 코드: [`storage-network.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fcomponents%2Fstorage-network.yml),
[`storage_network/tasks/audit.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fansible%2Froles%2Fstorage_network%2Ftasks%2Faudit.yml),
[`storage_network/tasks/main.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fansible%2Froles%2Fstorage_network%2Ftasks%2Fmain.yml)

### 3.9 `kerberos-nfs`

**목표 상태:** 서버가 FARM/LAB Kerberos 설정과 host keytab을 사용해 machine
principal 인증과 NFS service ticket 발급에 성공한다. `rpc-gssd`가 실행되고
공유 경로가 지정 source와 `sec=krb5` option으로 mount된다.

**점검:** `/etc/krb5.conf`, keytab, `kinit -k`, `kvno`, `rpc-gssd`와 mount
source·option을 순서대로 확인한다.

**설정:** domain Kerberos 설정을 설치하고 keytab과 principal을 검증한다. NFS
GSS readiness·recovery unit을 설치하고 fstab에 mount를 기록한다.

**설정 실행:** `ansible-playbook`, `gated`. Kerberos 설정, fstab과 mount
recovery 영향을 확인한 뒤 `--approve-gated`로 승인한다. 실제 mount 실행은
별도 `server_state_mount_now` 값으로 제어한다.

관련 코드: [`kerberos-nfs.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fcomponents%2Fkerberos-nfs.yml),
[`audit_client.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fkerberos-nfs%2Fansible%2Faudit_client.yml),
[`kerberos_nfs_client/`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Ftree%2Fmain%2Fkerberos-nfs%2Fansible%2Froles%2Fkerberos_nfs_client)

### 3.10 `monitoring`

**목표 상태:** `cluster-monitor-exporter`와 `gpu-user-exporter` service가
활성화·실행되고, 두 metrics endpoint와 public health endpoint가 HTTP 200으로
응답한다.

**점검:** 두 exporter service의 enabled·active 상태와 로컬 metrics·health
endpoint 응답을 확인한다.

**설정:** exporter binary를 build하고 설정 파일과 systemd unit을 설치한다.
service를 시작한 뒤 metrics 응답을 검증한다.

**설정 실행:** `ansible-playbook`, `safe`. `apply --execute`가 exporter 배포와
검증 playbook을 실행한다.

관련 코드: [`monitoring.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fcomponents%2Fmonitoring.yml),
[`audit_exporters.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fmonitoring%2Fansible_playbook%2Faudit_exporters.yml),
[`deploy_exporters.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fmonitoring%2Fansible_playbook%2Fdeploy_exporters.yml)

## 4. 명령별 동작

### 4.1 `audit`

`audit`은 구성요소의 읽기 전용 점검 playbook을 실행한다. 각 실행 결과는 서버와
구성요소 단위로 `OK` 또는 `FAILED`로 표시된다. `--show-command`는 같은
playbook과 변수를 사용한 명령을 화면에 출력한다.

### 4.2 `plan`

`plan`은 구성요소의 설정 playbook을 Ansible `--check --diff`로 실행한다.
package, 파일과 service의 예상 변경을 확인할 수 있다. `manual` 구성요소는 실행
명령 대신 준비 절차 reference를 표시한다.

### 4.3 `apply`

`apply`는 모든 선택 항목의 실행 형태와 안전 수준을 먼저 확인한다.
`ansible-playbook` 구성요소는 `--execute`로 실행하며, `gated`는
`--approve-gated`, `risky`는 `--approve-risky` 승인을 함께 사용한다. `manual`
구성요소는 운영 절차 reference를 표시한다.

## 5. 설정 구조

### 5.1 정책과 구성요소 정의

정책 파일은 구성요소 ID와 순서를 기록한다. 각 `components/<id>.yml`은 다음
정보를 기록한다.

| 필드 | 의미 |
| --- | --- |
| `id` | `--component`에서 사용하는 이름 |
| `desired_state` | 점검과 설정의 기준이 되는 서버 상태 |
| `audit` | 점검 playbook, tag와 `safe` 수준 |
| `converge` | 설정 playbook 또는 수동 절차와 안전 수준 |

[`docker-engine.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fcomponents%2Fdocker-engine.yml)은
다음과 같이 구성된다.

```yaml
id: docker-engine
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

`audit` 명령은 audit playbook에 `docker-engine` tag를 전달한다. `plan`과
`apply`는 converge playbook에 `docker-engine,cgroups` tag를 전달한다. 실제
점검 task는 role의 `tasks/audit.yml`, 설정 task는 `tasks/main.yml`에 있다.

### 5.2 서버와 FARM/LAB 설정

`servers.jsonl`은 host, server ID, domain, SSH 주소·port·계정과
management/storage interface 정보를 제공한다. `config/environments.yml`은
FARM/LAB별 realm, Kerberos config, storage host·mount와 Kubernetes context를
제공한다.

[`inventory.py`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fserver_state%2Finventory.py)는
두 정보를 결합해 Kerberos principal, NFS mount target, Kubernetes context와
public health port를 만든다.

### 5.3 명령 구성

[`planner.py`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fserver_state%2Fplanner.py)는
대상 서버와 구성요소를 결합해 inventory, playbook, host, tag와 extra vars가
포함된 Ansible 명령을 만든다.

[`commands.py`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fserver_state%2Fcommands.py)는
`audit`, `plan`, `apply`를 실행하고 결과를 text 또는 JSON으로 출력한다.

## 6. 코드 위치

| 파일·디렉터리 | 역할 |
| --- | --- |
| [`policy/standard-gpu-server.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fpolicy%2Fstandard-gpu-server.yml) | 구성요소와 실행 순서 |
| [`components/`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Ftree%2Fmain%2Fserver-state%2Fcomponents) | 구성요소별 목표 상태, 점검·설정 진입점과 승인 수준 |
| [`server_state/catalog.py`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fserver_state%2Fcatalog.py) | 정책과 구성요소 로딩·검증 |
| [`server_state/inventory.py`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fserver_state%2Finventory.py) | 서버 선택과 FARM/LAB 실행값 생성 |
| [`server_state/planner.py`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fserver_state%2Fplanner.py) | Ansible 명령 생성 |
| [`server_state/commands.py`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fserver_state%2Fcommands.py) | CLI 명령과 결과 처리 |
| [`ansible/playbooks/audit.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fansible%2Fplaybooks%2Faudit.yml) | 공통 구성요소 audit 순서 |
| [`ansible/playbooks/converge.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fansible%2Fplaybooks%2Fconverge.yml) | 공통 구성요소 설정 순서 |
| [`ansible/roles/`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Ftree%2Fmain%2Fserver-state%2Fansible%2Froles) | 구성요소별 점검·설정 task |
| [`kerberos-nfs/ansible/`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Ftree%2Fmain%2Fkerberos-nfs%2Fansible) | Kerberos/NFS 점검·설정 task |
| [`monitoring/ansible_playbook/`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Ftree%2Fmain%2Fmonitoring%2Fansible_playbook) | exporter 점검·배포 playbook |
| [`tests/`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Ftree%2Fmain%2Fserver-state%2Ftests) | 정책, 서버 정보, 명령 구성과 승인 test |
