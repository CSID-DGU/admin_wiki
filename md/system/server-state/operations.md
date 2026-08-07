# server-state 운영

> [개요](index.md) · [설계](design.md)

## 1. 개요

이 문서의 목표는 `server-state`를 운영하면서 서버와 구성요소를 추가하고, 환경
설정과 실행 제어를 변경하며, 서버 점검과 설정 작업을 수행하는 절차를 제공하는
것이다. 설계 문서에서 정의한 구조를 기준으로 다음 작업을 다룬다.

| 작업 | 변경 위치 | 확인 방법 |
| --- | --- | --- |
| 서버 추가 | `servers.jsonl`, Ansible inventory | `list-hosts`, `baseline-access` 점검 |
| FARM/LAB 설정 변경 | `server-state/config/environments.yml` | `plan --show-command`의 extra vars 확인 |
| 구성요소 추가·수정 | `server-state/components/`, Ansible role·playbook | `describe`, `audit`, `plan` |
| 실행 형태·안전 수준 변경 | 구성요소 정의와 `server_state/` Python package | 단위 테스트와 승인 동작 확인 |
| 서버 점검·설정 | `bin/server-state` CLI | 실행 결과와 종료 코드 확인 |

명령은 `admin_infra_server` 저장소 루트에서 실행한다.

```bash
cd /home/jy/server_manage
./server-state/bin/server-state --help
```

## 2. 신규 서버 추가

신규 서버 추가는 서버 정보 등록, Ansible 접속 대상 등록, 접속 점검, 표준 구성
순서로 진행한다.

### 2.1 등록 정보 준비

| 정보 | 용도 |
| --- | --- |
| `host` | CLI의 `--hosts`에서 사용하는 소문자 서버 이름 |
| `server_id` | Kerberos principal과 서버 식별에 사용하는 대문자 ID |
| `domain` | FARM 또는 LAB 환경 선택 |
| `server_no` | 공유 경로와 public health port 계산 |
| `ansible_host`, `ansible_port`, `ansible_user` | SSH 접속 |
| management interface·IPv4 | 관리 network 정보 |
| storage interface·IPv4 | storage network 설정과 점검 |

`host`, `server_id`와 같은 domain의 `server_no`는 기존 서버와 구분되는 값을
사용한다. IP, hostname, SSH key와 비대화형 sudo도 이 단계에서 준비한다.

### 2.2 서버 정보 등록

공용 `servers.jsonl`에 서버 한 대를 한 줄의 JSON으로 추가한다. 다음 예시는
`server-state`가 사용하는 핵심 필드를 보여준다.

```json
{"host":"farm10","server_id":"FARM10","domain":"FARM","server_no":10,"inventory":{"group":"FARM","ansible_host":"192.168.2.20","ansible_port":8090,"ansible_user":"jy"},"networks":{"management":{"name":"eno1","ipv4":"192.168.2.20"},"storage":{"name":"eno2","ipv4":"100.100.100.110"}}}
```

같은 서버를
[`monitoring/ansible_playbook/inventory.ini`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fmonitoring%2Fansible_playbook%2Finventory.ini)의
FARM 또는 LAB group에도 등록한다. host 이름과 SSH 주소·port는
`servers.jsonl`의 값과 맞춘다.

```ini
[FARM]
farm10 ansible_host=192.168.2.20 ansible_port=8090
```

group과 다른 SSH 계정을 사용하는 서버는 해당 host 행에 `ansible_user`를 함께
지정한다.

### 2.3 등록 결과 확인

CLI가 새 서버의 ID, domain, SSH 주소와 계산된 public health port를 읽는지
확인한다.

```bash
./server-state/bin/server-state list-hosts --hosts farm10
```

Ansible 접속, hostname과 sudo 조건은 `baseline-access` 점검으로 확인한다.

```bash
./server-state/bin/server-state audit \
  --hosts farm10 \
  --component baseline-access
```

### 2.4 표준 구성 진행

전체 구성요소의 예상 변경과 수동 절차를 먼저 확인한다.

```bash
./server-state/bin/server-state plan --hosts farm10
```

`safe`, `gated`, `risky` 순서로 설정 작업을 나누어 실행하고 각 단계가 끝날 때
동일한 구성요소를 다시 점검한다. `baseline-access`와
`kubernetes-membership`은 출력된 운영 절차에 따라 진행한다. 실행 명령과 승인
옵션은 아래의 **서버 설정** 절에서 설명한다.

## 3. FARM/LAB 환경 설정 변경

[`server-state/config/environments.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fconfig%2Fenvironments.yml)은
여러 서버가 공유하는 환경 값을 관리한다.

| 설정 | 사용하는 작업 |
| --- | --- |
| `kerberos_realm`, `kerberos_config_source` | Kerberos principal과 client 설정 구성 |
| `storage_host`, `mount_source`, `mount_options` | NFS mount와 인증 점검 |
| `kubernetes_cluster` | 서버가 참여할 cluster 선택 |
| `mount_target_template` | 서버별 공유 경로 계산 |
| public health port 계산값 | monitoring health endpoint port 계산 |

환경 값을 변경할 때는 다음 순서를 사용한다.

1. FARM 또는 LAB 항목의 값을 수정한다.
2. 해당 domain의 서버 한 대를 선택해 생성될 Ansible 명령과 extra vars를
   확인한다.
3. 관련 구성요소를 `audit`하고 `plan`으로 예상 변경을 확인한다.
4. 한 서버에 설정한 뒤 같은 domain의 나머지 서버로 범위를 넓힌다.

```bash
./server-state/bin/server-state plan \
  --hosts farm8 \
  --component kerberos-nfs \
  --show-command
```

public health port 계산값은 다음 명령으로 확인한다.

```bash
./server-state/bin/server-state list-hosts --hosts FARM
```

## 4. 구성요소 추가·수정

구성요소는 하나의 목표 상태와 그 상태를 확인하는 점검 작업, 목표 상태를 만드는
설정 작업을 묶는다.

### 4.1 점검과 설정 작업 작성

점검 작업은 서버 상태를 읽어 목표 상태 충족 여부를 판단한다. 설정 작업은 여러
번 실행해도 같은 목표 상태에 도달하도록 Ansible task를 작성한다. 공통
playbook에서 tag로 role을 선택하거나 구성요소 전용 playbook을 연결할 수 있다.

- 점검 role은 `tasks/audit.yml`에 둔다.
- 설정 role은 `tasks/main.yml`과 handler에 둔다.
- 점검 action의 `safety`는 `safe`로 지정한다.
- service 재시작, package 교체와 cluster 변경 같은 영향은 설정 action의 안전
  수준에 반영한다.

### 4.2 구성요소 정의 추가

`server-state/components/<id>.yml`을 추가한다. 파일명과 `id`는 같아야 한다.

```yaml
id: example-component
desired_state: The host has the expected example service and configuration.
audit:
  kind: ansible-playbook
  playbook: server-state/ansible/playbooks/audit.yml
  tags: [example-component]
  safety: safe
converge:
  kind: ansible-playbook
  playbook: server-state/ansible/playbooks/converge.yml
  tags: [example-component]
  safety: gated
```

| 필드 | 작성 기준 |
| --- | --- |
| `id` | CLI에서 선택할 고유한 이름 |
| `desired_state` | 점검과 설정이 공통으로 사용하는 목표 상태 |
| `kind` | Ansible 실행은 `ansible-playbook`, 운영 절차 실행은 `manual` |
| `playbook` | 저장소 루트 기준 playbook 경로 |
| `tags` | playbook에서 이 구성요소의 task를 선택할 tag |
| `host_variable` | playbook이 대상 host를 받는 변수 이름. 기본값은 `server_state_hosts` |
| `reference` | `manual` 작업에서 표시할 운영 절차 |
| `safety` | `safe`, `gated`, `risky` 중 설정 영향에 맞는 수준 |

### 4.3 정책 순서에 추가

전체 서버가 사용하는 구성요소는
[`server-state/policy/standard-gpu-server.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fpolicy%2Fstandard-gpu-server.yml)의
`components`에 추가한다. 필요한 package, runtime, network와 인증 조건을 기준으로
선행 구성요소 뒤에 배치한다. `describe`, `audit`, `plan`과 `apply`는 이 순서를
사용한다.

### 4.4 기존 구성요소 수정

| 변경 내용 | 수정 위치 |
| --- | --- |
| 목표 상태 문구 | `components/<id>.yml`의 `desired_state` |
| 점검 기준 | audit role·playbook |
| 서버 설정 내용 | converge role·playbook과 handler |
| playbook·tag·실행 형태·안전 수준 | `components/<id>.yml`의 `audit`, `converge` |
| 구성요소 실행 순서 | `policy/standard-gpu-server.yml` |

변경 후에는 한 서버에서 `audit`, `plan`, `apply`, `audit` 순서로 결과를 확인한
뒤 domain 단위로 실행 범위를 넓힌다.

### 4.5 연결 확인

```bash
./server-state/bin/server-state describe \
  --component example-component

./server-state/bin/server-state audit \
  --hosts farm8 \
  --component example-component \
  --show-command

./server-state/bin/server-state plan \
  --hosts farm8 \
  --component example-component \
  --show-command
```

## 5. 실행 형태와 안전 수준 변경

설정 작업의 실행 제어는 `converge.kind`와 `converge.safety`로 나뉜다.

### 5.1 실행 형태

| `kind` | 동작 |
| --- | --- |
| `ansible-playbook` | `plan`에서 check/diff를 실행하고 `apply`에서 설정 playbook을 실행한다. |
| `manual` | CLI가 `reference`에 기록된 운영 절차를 표시한다. |

`manual` 구성요소도 작업 영향을 나타내는 `safety`를 기록한다. `apply`는 해당
구성요소를 `MANUAL`로 표시하며 관리자가 reference의 절차를 수행한다.

### 5.2 안전 수준

| `safety` | 설정 실행 조건 |
| --- | --- |
| `safe` | `apply --execute` |
| `gated` | `apply --execute --approve-gated` |
| `risky` | `apply --execute --approve-risky` |

`audit`은 읽기 전용 작업이므로 항상 `safe`를 사용한다. 기존 구성요소의 실행
형태나 안전 수준을 바꿀 때는 `components/<id>.yml`의 `converge`를 수정하고
`describe`, `plan`과 승인 동작을 확인한다.

### 5.3 새 실행 형태 추가

새 `kind`는 YAML 값과 해당 값을 처리하는 실행 코드를 함께 추가한다.

1. [`catalog.py`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fserver_state%2Fcatalog.py)의
   `ACTION_KINDS`, `Action` 필드와 로딩 검증을 확장한다.
2. [`planner.py`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fserver_state%2Fplanner.py)에서
   새 실행 형태에 필요한 `PlanItem`을 만든다.
3. [`commands.py`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server%2Fblob%2Fmain%2Fserver-state%2Fserver_state%2Fcommands.py)에서
   실행 결과와 오류를 표시한다.
4. catalog, planner와 command 단위 테스트에 로딩·계획·실행 사례를 추가한다.
5. 구성요소 하나에 새 값을 연결해 `describe`, `plan`, `apply`를 확인한다.

### 5.4 새 안전 수준 추가

새 `safety`는 승인 조건과 CLI 옵션을 함께 설계한다.

1. `catalog.py`의 `SAFETY_LEVELS`와 검증 사례를 확장한다.
2. `commands.py`의 `apply` option과 승인 판정을 추가한다.
3. 승인 전 `BLOCKED`, 승인 후 실행되는 command test를 추가한다.
4. 설계 문서와 운영 문서에 영향 범위와 실행 명령을 기록한다.
5. 한 서버에서 차단·승인·실행·재점검 흐름을 확인한다.

## 6. 대상과 정책 확인

관리 대상과 파생된 public health port를 확인한다.

```bash
./server-state/bin/server-state list-hosts --hosts all
./server-state/bin/server-state list-hosts --hosts farm
./server-state/bin/server-state list-hosts --hosts farm8,lab10
```

`--hosts`는 `all`, FARM/LAB domain, host 이름, server ID와 쉼표·공백으로 구분한
조합을 지원한다.

전체 정책이나 선택한 구성요소의 목표 상태, 점검·설정 실행 형태와 안전 수준을
확인한다.

```bash
./server-state/bin/server-state describe
./server-state/bin/server-state describe --component docker-engine
./server-state/bin/server-state describe \
  --component docker-engine,kerberos-nfs,monitoring
```

`--component`를 생략하면 전체 정책을 선택한다. 여러 번 사용하거나 쉼표로 묶을 수
있으며, 실행 순서는 정책의 구성요소 순서를 따른다.

## 7. 운영 서버 점검

### 7.1 실행 명령 확인

`--show-command`는 실제로 사용할 Ansible inventory, playbook, tag와 extra vars가
포함된 명령을 화면에 출력한다.

```bash
./server-state/bin/server-state audit \
  --hosts farm8 \
  --component docker-engine \
  --show-command
```

### 7.2 점검 실행

`--show-command`를 제외하면 선택한 서버에 접속해 읽기 전용 audit task를
실행한다.

```bash
# 한 서버의 전체 구성요소 점검
./server-state/bin/server-state audit --hosts farm8

# FARM 전체의 Docker와 NVIDIA runtime 점검
./server-state/bin/server-state audit \
  --hosts farm \
  --component docker-engine \
  --component nvidia-runtime
```

각 구성요소는 별도 Ansible 실행으로 처리된다. 결과에는 서버와 구성요소가 함께
표시되며 하나 이상의 실행이 실패하면 종료 코드는 1이다.

## 8. 서버 설정

### 8.1 예상 변경 확인

`plan`은 설정 playbook을 Ansible `--check --diff`로 실행한다. package, 파일과
service의 예상 변경을 확인하며, `manual` 구성요소는 운영 절차 reference를
표시한다.

```bash
./server-state/bin/server-state plan \
  --hosts farm8 \
  --component os-common \
  --component docker-engine \
  --component storage-network
```

명령 구성만 확인할 때는 `--show-command`를 추가한다.

### 8.2 `safe` 설정 실행

```bash
./server-state/bin/server-state apply \
  --hosts farm8 \
  --component os-common \
  --component storage-network \
  --execute
```

### 8.3 `gated` 설정 승인과 실행

예상 diff와 service 재시작, package·설정 변경 영향을 확인한 뒤 승인한다.

```bash
./server-state/bin/server-state apply \
  --hosts farm8 \
  --component docker-engine \
  --component nvidia-runtime \
  --component kubernetes-packages \
  --execute \
  --approve-gated
```

### 8.4 `risky` 설정 승인과 실행

GPU workload와 reboot 일정까지 확인한 뒤 승인한다.

```bash
./server-state/bin/server-state apply \
  --hosts farm8 \
  --component nvidia-driver \
  --execute \
  --approve-risky
```

`--approve-risky`는 `gated` 승인도 포함한다. 하나의 요청에 필요한 승인이 빠지거나
`manual` 구성요소가 포함되면 Ansible 실행 전에 종료 코드 2로 끝난다. 검토가
끝난 구성요소를 안전 수준별로 선택해 실행한다.

### 8.5 설정 후 점검

설정에 사용한 서버와 구성요소를 같은 조건으로 다시 점검한다.

```bash
./server-state/bin/server-state audit \
  --hosts farm8 \
  --component docker-engine \
  --component nvidia-runtime
```

## 9. 결과 해석

| 상태 | 의미 |
| --- | --- |
| `COMMAND` | `--show-command`로 실행 예정 명령을 출력했다. |
| `OK` | 해당 Ansible 실행이 종료 코드 0으로 끝났다. |
| `FAILED` | Ansible 실행이 실패했다. `detail`의 stdout·stderr를 확인한다. |
| `MANUAL` | 표시된 운영 절차 reference를 사용한다. |
| `BLOCKED` | 선택한 안전 수준에 필요한 승인을 추가한다. |

자동 처리용 JSON은 전역 옵션인 `--format`을 하위 명령 앞에 둔다.

```bash
./server-state/bin/server-state --format json audit \
  --hosts farm8 \
  --component docker-engine \
  --show-command
```

종료 코드는 전체 성공 0, Ansible 실행 실패 1, 설정 오류 또는 승인 차단 2다.

## 10. 변경 검증

Python 단위 테스트:

```bash
cd /home/jy/server_manage/server-state
python3 -m unittest discover -s tests -v
```

주요 Ansible 구문 검사:

```bash
cd /home/jy/server_manage
ANSIBLE_CONFIG="$PWD/monitoring/ansible_playbook/ansible.cfg" \
ANSIBLE_ROLES_PATH="$PWD/server-state/ansible/roles:$PWD/kerberos-nfs/ansible/roles" \
ansible-playbook --syntax-check \
  -i monitoring/ansible_playbook/inventory.ini \
  server-state/ansible/playbooks/audit.yml

ANSIBLE_CONFIG="$PWD/monitoring/ansible_playbook/ansible.cfg" \
ANSIBLE_ROLES_PATH="$PWD/server-state/ansible/roles:$PWD/kerberos-nfs/ansible/roles" \
ansible-playbook --syntax-check \
  -i monitoring/ansible_playbook/inventory.ini \
  server-state/ansible/playbooks/converge.yml
```

CLI 연결 확인:

```bash
./server-state/bin/server-state audit \
  --hosts farm8 \
  --component docker-engine \
  --show-command

./server-state/bin/server-state plan \
  --hosts lab10 \
  --component kerberos-nfs \
  --show-command
```

운영 반영은 한 서버에서 `audit`, `plan`, `apply`, `audit` 순서로 검증한 뒤 같은
domain의 서버로 범위를 넓힌다.
