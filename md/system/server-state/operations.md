# server-state 운영

> [개요](index.md) · [설계](design.md)

## 1. 실행 위치와 기본 확인

명령은 `admin_infra_server` 저장소 루트에서 실행한다.

```bash
cd /home/jy/server_manage
./server-state/bin/server-state --help
```

관리 대상과 파생된 public health port를 확인한다.

```bash
./server-state/bin/server-state list-hosts --hosts all
./server-state/bin/server-state list-hosts --hosts farm
./server-state/bin/server-state list-hosts --hosts farm8,lab10
```

`--hosts`는 `all`, FARM/LAB domain, host 이름, server ID와 쉼표·공백으로 구분한
조합을 지원한다. 등록된 대상만 실행하며 다른 값은 selector 오류로 표시한다.

전체 정책이나 선택한 구성요소의 목표 상태, audit·converge 종류와 승인 수준을
확인한다.

```bash
./server-state/bin/server-state describe
./server-state/bin/server-state describe --component docker-engine
./server-state/bin/server-state describe \
  --component docker-engine,kerberos-nfs,monitoring
```

`--component`를 생략하면 전체 정책을 선택한다. 여러 번 사용하거나 쉼표로 묶을 수
있으며, 실행 순서는 항상 정책의 선행 조건 순서를 따른다.

## 2. 운영 서버 점검

### 2.1 명령만 확인

`--show-command`는 실제로 사용할 Ansible 명령, inventory, playbook, tag와 extra
vars를 로컬 화면에 출력한다.

```bash
./server-state/bin/server-state audit \
  --hosts farm8 \
  --component docker-engine \
  --show-command
```

여러 구성요소나 전체 정책도 같은 방식으로 확인할 수 있다.

```bash
./server-state/bin/server-state audit \
  --hosts farm8 \
  --component docker-engine \
  --component nvidia-runtime \
  --show-command

./server-state/bin/server-state audit --hosts farm8 --show-command
```

### 2.2 점검 실행

`--show-command`를 제거하면 선택한 서버에 접속하여 읽기 전용 audit task를
실행한다.

```bash
# 한 서버의 전체 정책 점검
./server-state/bin/server-state audit --hosts farm8

# FARM 전체의 Docker와 NVIDIA runtime만 점검
./server-state/bin/server-state audit \
  --hosts farm \
  --component docker-engine \
  --component nvidia-runtime
```

각 구성요소는 별도 Ansible 실행으로 처리되므로 결과에서 어느 서버의 어느
구성요소가 실패했는지 구분할 수 있다. 하나라도 실패하면 명령 종료 코드는 1이다.
audit은 구성 role의 `tasks/audit.yml`만 실행한다.

## 3. 신규 서버 구성

다음 조건은 먼저 준비되어 있어야 한다.

- 지원 Ubuntu가 설치되어 있다.
- IP와 hostname이 확정되어 SSH로 접속할 수 있다.
- 관리 계정이 비대화형 sudo를 사용할 수 있다.
- 공용 `servers.jsonl`과 Ansible inventory에 서버가 등록되어 있다.

### 3.1 예상 변경 확인

`plan`은 선택한 구성요소의 구성 진입점을 Ansible `--check --diff`로 실행한다.
대상 서버에 접속하는 Ansible check mode에서 예상 변경을 확인한다.
먼저 명령만 보고 싶으면 `--show-command`를 추가한다.

```bash
./server-state/bin/server-state plan \
  --hosts farm8 \
  --component os-common \
  --component docker-engine \
  --component storage-network \
  --show-command

./server-state/bin/server-state plan \
  --hosts farm8 \
  --component os-common \
  --component docker-engine \
  --component storage-network
```

전체 정책을 계획하면 자동 구성 가능한 항목은 check mode로 실행되고,
`baseline-access`, `kubernetes-membership`처럼 수동인 항목은
`MANUAL`과 reference로 표시된다.

### 3.2 안전한 구성 적용

`safe` 구성요소는 `--execute`를 명시해야 실행된다.

```bash
./server-state/bin/server-state apply \
  --hosts farm8 \
  --component os-common \
  --component storage-network \
  --execute
```

`gated` 구성요소는 예상 diff와 운영 영향을 검토한 뒤 `--approve-gated`를
추가한다.

```bash
./server-state/bin/server-state apply \
  --hosts farm8 \
  --component docker-engine \
  --component nvidia-runtime \
  --component kubernetes-packages \
  --execute \
  --approve-gated
```

NVIDIA driver는 package 변경과 reboot·GPU workload 조정 가능성이 있으므로
`--approve-risky`가 필요하다.

```bash
./server-state/bin/server-state apply \
  --hosts farm8 \
  --component nvidia-driver \
  --execute \
  --approve-risky
```

`--approve-risky`는 `gated` 승인도 포함한다. 하나의 apply 요청에 추가 승인이
필요한 항목이나 수동 항목이 있으면 Ansible 실행 전 단계에서 종료 코드 2로
중단한다. 전체 정책을 한 번에 apply하기보다 검토가 끝난 구성요소 그룹을
명시해서 실행한다.

### 3.3 수동 구성요소

다음 항목은 CLI가 수동 절차 reference를 표시한다.

| 구성요소 | 수동인 이유 |
| --- | --- |
| `baseline-access` | SSH, sudo, hostname과 inventory는 Ansible 구성 실행 전에 이미 사용할 수 있어야 한다. |
| `kubernetes-membership` | cluster 선택과 짧은 수명의 join token, controller 승인이 필요하다. |

Kerberos/NFS는 playbook으로 구성할 수 있지만 keytab 준비와 즉시 mount 여부에는
별도 운영 판단이 필요하다. 상세 절차는 [Kerberos/NFS 운영](../kerberos-nfs/operations.md)을
함께 확인한다.

## 4. 결과 해석

| 상태 | 의미 |
| --- | --- |
| `COMMAND` | `--show-command`로 실행 예정 명령만 출력했다. |
| `OK` | 해당 Ansible 실행이 종료 코드 0으로 끝났다. |
| `FAILED` | Ansible 실행이 실패했다. `detail`의 stdout·stderr를 확인한다. |
| `MANUAL` | 표시된 수동 운영 절차 reference를 사용한다. |
| `BLOCKED` | `--approve-gated` 또는 `--approve-risky` 추가가 필요하다. |

자동 처리용 JSON은 전역 옵션인 `--format`을 하위 명령 앞에 둔다.

```bash
./server-state/bin/server-state --format json audit \
  --hosts farm8 \
  --component docker-engine \
  --show-command
```

종료 코드는 전체 성공 0, Ansible 실행 실패 1, 입력·설정 오류 또는 안전 gate 차단
2다.

## 5. inventory와 환경 설정

기본 `servers.jsonl`은 host, server ID, domain, SSH와 network 정보를 제공한다.
FARM/LAB별 realm, Kerberos config, NFS source·option, Kubernetes context는
`server-state/config/environments.yml`에서 읽는다.

다른 파일로 검증할 때는 전역 옵션을 하위 명령 앞에 둔다.

```bash
./server-state/bin/server-state \
  --inventory /path/to/servers.jsonl \
  --environments /path/to/environments.yml \
  audit --hosts farm8 --show-command
```

서버 접속·network 정보는 inventory에서, 여러 서버가 공유하는 FARM/LAB 운영값은
environment 설정에서 수정한다.

## 6. 구성요소 추가·수정

1. 읽기 전용 audit과 idempotent한 설정 role 또는 playbook을 구현한다.
2. `server-state/components/<id>.yml`에 목표 상태, 진입점과 승인 수준을 기록한다.
3. 전체 서버에 필요한 항목이면 `policy/standard-gpu-server.yml`의 적절한
   선행 조건 위치에 ID를 추가한다.
4. catalog 로딩, 정책 순서, playbook 존재 여부와 계획 생성 test를 추가한다.
5. Ansible syntax check와 `audit/plan --show-command`로 연결을 확인한다.

점검은 구성요소 role의 `tasks/audit.yml`, 설정은 `tasks/main.yml` 또는 연결된
playbook에 둔다.

## 7. 테스트

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

CLI 연결을 로컬 명령 출력으로 확인:

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
