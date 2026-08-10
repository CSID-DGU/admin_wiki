# Ansible 설정

> [개요](index.md) · [기초 개념](basic.md)

## 1. 개요

이 문서는 관리 데스크탑에서 admin_infra_server의 모듈들을 실행할 수 있도록 Ansible을
설정하는 방법을 설명한다. 개념 설명은 [기초 개념](basic.md)에 있다.

이 문서에서 `<저장소>`는 admin_infra_server를 clone한 경로를,
`<관리자계정>`은 FARM/LAB 서버에 접속할 본인의 계정 이름을 뜻한다. 관리자마다
값이 다르므로 자신의 값으로 바꿔서 사용한다.

### 설정 파일 구성

관리 서버는 여러 관리자가 함께 사용하고, 각 관리자는 자신의 계정과 SSH 키로 서버에
접속한다. 따라서 설정을 성격에 따라 두 파일로 나눈다.

| 파일 | 담는 내용 | 관리 방식 |
| --- | --- | --- |
| `<저장소>/ansible/inventory.ini` | 서버 목록 (host 이름, IP, SSH port) | 저장소에서 공유. 모든 관리자가 같은 값을 사용한다 |
| `~/.ansible.cfg` | 접속 계정, 임시 디렉터리 경로 | 관리자별로 각자 작성한다. 저장소에 넣지 않는다 |

기준은 "이 값이 관리자마다 다른가"이다. 서버 목록은 모두 같으므로 공유하고, 접속
계정은 각자 다르므로 개인 파일에 둔다.

**공유 파일에는 접속 계정을 기록하지 않는다.** inventory의 `ansible_user`는
`~/.ansible.cfg`의 `remote_user`보다 우선하므로, 공유 파일에 계정이 남아 있으면 개인
설정이 적용되지 않는다.

---

## 2. 준비 확인

### 2.1 Ansible 설치

```bash
ansible --version
```

관리 서버에 `ansible`이 설치되어 있지 않으면 설치한다.

```bash
sudo apt update && sudo apt install -y ansible
```

### 2.2 SSH 키 등록 {#22}

각 관리자는 자신의 SSH 키로 FARM/LAB 서버에 접속한다. 공용 계정은 사용하지 않는다.
키가 없으면 생성하고, 대상 서버의 `authorized_keys`에 공개키를 등록한다.

```bash
ls ~/.ssh/id_ed25519          # 키 확인
ssh-keygen -t ed25519         # 없을 경우 생성
```

접속이 되는지 먼저 확인한다.

```bash
ssh -p 8088 <관리자계정>@192.168.2.18
```

### 2.3 저장소 clone

```bash
git clone <저장소 URL>
```

clone 경로는 관리자마다 달라도 된다. 개인 설정 파일에 자신의 경로를 적으면 된다.

---

## 3. 공용 inventory {#3-inventory}

서버 목록은 저장소의 `<저장소>/ansible/inventory.ini` 하나로 관리한다. 관리자가
개인 사본을 만들지 않으며, 서버가 추가되면 이 파일만 갱신하고 나머지 관리자는
`git pull`로 받는다.

```ini
# 공용 Ansible inventory (관리자 전원이 공유)
#
# 접속 계정(ansible_user)은 여기에 쓰지 않는다.
# 계정은 각 관리자의 ~/.ansible.cfg 의 remote_user 가 담당한다.

[FARM]
farm1 ansible_host=192.168.2.11 ansible_port=8081
farm2 ansible_host=192.168.2.12 ansible_port=8082
farm6 ansible_host=192.168.2.16 ansible_port=8086
farm7 ansible_host=192.168.2.17 ansible_port=8087
farm8 ansible_host=192.168.2.18 ansible_port=8088
farm9 ansible_host=192.168.2.19 ansible_port=8089

[LAB]
lab1 ansible_host=192.168.1.11 ansible_port=8081
lab2 ansible_host=192.168.1.12 ansible_port=8082
lab3 ansible_host=192.168.1.13 ansible_port=8083
lab4 ansible_host=192.168.1.14 ansible_port=8084
lab5 ansible_host=192.168.1.15 ansible_port=8085
lab6 ansible_host=192.168.1.16 ansible_port=8086
lab7 ansible_host=192.168.1.17 ansible_port=8087
lab8 ansible_host=192.168.1.18 ansible_port=8088
lab9 ansible_host=192.168.1.19 ansible_port=8089
lab10 ansible_host=192.168.1.110 ansible_port=8090

[LAB_STORAGE]
lab-storage ansible_host=192.168.1.20 ansible_port=6953
```

서버를 추가할 때는 이 파일과
`user-lifecycle/server_info/servers.jsonl`을 함께 갱신한다. 두 파일은 같은 서버
집합을 나타내야 한다.

---

## 4. 개인 설정 파일 작성

홈 디렉터리에 `~/.ansible.cfg`를 만든다. 파일 이름이 반드시 `.ansible.cfg`여야
Ansible이 자동으로 찾는다. `~/ansible/ansible.cfg`처럼 폴더 안에 두면 무시된다.

```bash
cat > ~/.ansible.cfg <<'EOF'
[defaults]
inventory          = <저장소>/ansible/inventory.ini
remote_user        = <관리자계정>
local_tmp          = /tmp/ansible-local-<관리자계정>
remote_tmp         = /tmp/.ansible-<관리자계정>/tmp
interpreter_python = auto_silent
host_key_checking  = False
retry_files_enabled = False

[ssh_connection]
control_path_dir = /tmp/ansible-cp-<관리자계정>
pipelining = True
EOF
```

`<저장소>`와 `<관리자계정>`을 자신의 값으로 바꾼다. 작성 예시는 다음과 같다.

```ini
[defaults]
inventory          = /home/suhyeon/CSID-DGU/admin_infra_server/ansible/inventory.ini
remote_user        = suhyeon
local_tmp          = /tmp/ansible-local-suhyeon
remote_tmp         = /tmp/.ansible-suhyeon/tmp
interpreter_python = auto_silent
host_key_checking  = False
retry_files_enabled = False

[ssh_connection]
control_path_dir = /tmp/ansible-cp-suhyeon
pipelining = True
```

관리자마다 달라지는 값은 `inventory`의 clone 경로와 `remote_user`, 그리고 임시
디렉터리 경로에 들어가는 계정 이름뿐이다.

### 임시 디렉터리에 계정 이름을 넣는 이유

Ansible은 `local_tmp`와 `control_path_dir` 경로가 없으면 **소유자만 접근 가능한
권한(0700)으로 직접 생성한다.** 여러 관리자가 `/tmp/ansible-local` 같은 공용 경로를
함께 쓰면, 먼저 실행한 관리자가 소유자가 되고 나머지는 그 디렉터리에 접근하지 못해
실행이 실패한다. 경로에 계정 이름을 넣어 관리자별로 분리한다.

### 환경변수는 필요하지 않다

`~/.ansible.cfg`는 Ansible이 자동으로 찾으므로 `.bashrc`에 `ANSIBLE_CONFIG`나
`ANSIBLE_INVENTORY`를 설정할 필요가 없다. 과거 설정에서 이 환경변수들을 추가했다면
제거한다.

---

## 5. sudo 권한 준비 {#5-sudo}

모듈의 Ansible 작업은 대상 서버에서 root 권한을 사용한다. 점검만 하는 작업도
마찬가지다. 따라서 **명령을 실행하는 관리자 각자의 계정**에 대해 대상 서버에서
비밀번호 없이 sudo를 쓸 수 있어야 한다.

설정되어 있지 않으면 다음과 같이 실패한다.

```
TASK [Gathering Facts] *********************************************************
fatal: [farm8]: FAILED! => {"msg": "Missing sudo password"}
```

### 5.1 현재 상태 확인

```bash
ssh -p 8088 <관리자계정>@192.168.2.18 'sudo -n true && echo "설정됨" || echo "설정 안 됨"'
```

`sudo -n`은 비밀번호를 묻지 않고 sudo를 시도하는 옵션이다.

### 5.2 서버 한 대에 설정 {#52}

대상 서버에서 다음을 실행한다. 파일 이름은 계정 이름과 같게 한다.

```bash
echo "<관리자계정> ALL=(ALL) NOPASSWD:ALL" | sudo tee /etc/sudoers.d/<관리자계정> > /dev/null
sudo chmod 440 /etc/sudoers.d/<관리자계정>
sudo visudo -cf /etc/sudoers.d/<관리자계정>
```

마지막 `visudo -cf`는 문법 검사이며 **반드시 실행한다.** sudoers 파일에 문법 오류가
있으면 해당 서버에서 sudo 전체가 동작하지 않는다. `parsed OK`가 나오면 정상이고,
오류가 나오면 **로그아웃하지 말고** 같은 세션에서 다음을 실행해 되돌린다.

```bash
sudo rm /etc/sudoers.d/<관리자계정>
```

설정 후 확인한다.

```bash
sudo -n true && echo OK
```

### 5.3 전체 서버에 일괄 적용

한 대에서 정상 동작을 확인한 뒤 나머지 서버에 적용한다. 이 작업은 모듈 명령이 아닌
`ansible` 명령을 직접 사용하므로 `-K` 옵션으로 sudo 비밀번호를 한 번만 입력하면 된다.

```bash
ssh-add ~/.ssh/id_ed25519

ansible 'FARM:LAB' -b -K -m lineinfile \
  -a "path=/etc/sudoers.d/<관리자계정> \
      line='<관리자계정> ALL=(ALL) NOPASSWD:ALL' \
      create=yes owner=root group=root mode=0440 \
      validate='visudo -cf %s'"
```

| 옵션 | 역할 |
| --- | --- |
| `-b` | root 권한으로 실행한다 |
| `-K` | sudo 비밀번호를 한 번 입력받는다 |
| `validate` | 파일을 설치하기 **전에** 문법을 검사한다. 통과하지 못하면 설치하지 않는다 |

`ssh-add`는 SSH 키 암호를 한 번만 입력하도록 등록하는 명령이다. 실행하지 않으면
서버마다 암호를 다시 묻는다.

전체 결과를 확인한다.

```bash
ansible 'FARM:LAB' -m command -a 'sudo -n true' -o
```

각 서버의 sudo 비밀번호가 다르면 `-K` 한 번으로 처리되지 않는다. 실패한 서버는
[5.2](#52)의 방법으로 개별 적용한다.

---

## 6. 설정 확인

### 6.1 설정 파일이 인식되는지 {#61}

```bash
ansible --version | grep "config file"
```

`/home/<관리자계정>/.ansible.cfg`가 나와야 한다. `/etc/ansible/ansible.cfg`가 나오면
파일 이름이나 위치가 잘못된 것이다.

### 6.2 적용된 값 확인

```bash
ansible-config dump --only-changed
```

`DEFAULT_HOST_LIST`가 저장소의 inventory를, `DEFAULT_REMOTE_USER`가 본인 계정을
가리키는지 확인한다.

### 6.3 접속 확인

```bash
ansible farm8 -m ping
```

`SUCCESS`와 `"ping": "pong"`이 나오면 접속과 계정 설정이 정상이다.

### 6.4 host 해석 확인 {#64}

```bash
ansible-inventory --host farm8
```

`ansible_host`와 `ansible_port`만 나오고 `ansible_user`가 없어야 한다.
`ansible_user`가 보이면 inventory에 계정이 남아 있는 것이며, 이 경우 개인 설정의
`remote_user`가 적용되지 않는다.

---

## 7. 모듈별 적용 현황

모듈은 순서대로 이 구조로 전환한다. 전환이 끝나지 않은 모듈은 자체 설정을 사용하므로
해당 모듈 문서를 함께 확인한다.

| 모듈 | 상태 | 비고 |
| --- | --- | --- |
| [`server-state`](../server-state/index.md) | 적용 완료 | `~/.ansible.cfg`만으로 동작한다 |
| [`monitoring`](../monitoring/index.md) | 전환 예정 | `monitoring/ansible_playbook/`의 설정을 사용한다 |
| [`remote-operations`](../remote-operations/index.md) | 전환 예정 | `remote_boot.local.env`의 `REMOTE_BOOT_ANSIBLE_INVENTORY`를 사용한다 |
| [`kerberos-nfs`](../kerberos-nfs/index.md) | 해당 없음 | role만 제공하며 `server-state`를 통해 실행된다 |

---

## 8. 문제 해결

Ansible 실행은 [기초 개념](basic.md#run-order)의 실행 순서를 따른다. 오류 메시지로
어느 단계에서 멈췄는지 확인하면 원인을 좁힐 수 있다.

| 멈춘 단계 | 대표적인 오류 | 원인 | 확인할 곳 |
| --- | --- | --- | --- |
| 1. 설정 파일 찾기 | 설정을 바꿨는데 반영되지 않는다 | 설정 파일 위치나 이름이 잘못됐다 | [8.3](#83) |
| 2. 서버 목록 읽기 | `Could not match supplied host pattern` | 대상 서버가 inventory에 없다 | [3장](#3-inventory) |
| 3. 접속 계정 결정 | 의도하지 않은 계정으로 접속한다 | inventory에 `ansible_user`가 남아 있다 | [8.4](#84) |
| 4. SSH 접속 | `Permission denied`, `UNREACHABLE` | SSH 키가 등록되지 않았거나 계정이 맞지 않다 | [2.2](#22) |
| 5. 권한 상승 | `Missing sudo password` | 대상 서버에 NOPASSWD sudo가 없다 | [8.2](#82) |
| 6. 작업 실행 | `failed`, `fatal` | 서버 상태가 기준과 다르거나 작업이 오류를 냈다 | 해당 모듈 문서 |

관리 데스크탑에서 일어나는 1~3번은 설정 파일 문제이고, 4번부터는 대상 서버 문제다.

### 8.1 `Permission denied: '/tmp/ansible-local/...'`

```
PermissionError: [Errno 13] Permission denied: '/tmp/ansible-local/ansible-local-...'
ansible.errors.AnsibleError: Invalid settings supplied for DEFAULT_LOCAL_TMP
```

다른 관리자가 먼저 만든 임시 디렉터리에 접근하지 못해 발생한다. `~/.ansible.cfg`의
`local_tmp`가 계정별 경로로 되어 있는지, 그리고 해당 설정 파일이 실제로 인식되고
있는지([6.1](#61)) 확인한다.

### 8.2 `Missing sudo password` {#82}

대상 서버에 본인 계정의 NOPASSWD sudo가 없다. [5장](#5-sudo)의 절차로 설정한다.
다른 관리자에게 설정되어 있어도 본인 계정에는 별도로 필요하다.

### 8.3 설정을 바꿨는데 반영되지 않는다 {#83}

다음 순서로 확인한다.

1. `ansible --version | grep "config file"`로 어떤 파일이 실제로 사용되는지 확인한다.
2. 현재 디렉터리에 `ansible.cfg`가 있으면 그 파일이 `~/.ansible.cfg`보다 우선한다.
3. `ANSIBLE_CONFIG`나 `ANSIBLE_INVENTORY` 환경변수가 남아 있으면 개인 설정을 덮어쓴다.
   `env | grep ANSIBLE`로 확인하고 `.bashrc`에서 제거한다.

### 8.4 잘못된 계정으로 접속을 시도한다 {#84}

inventory에 `ansible_user`가 남아 있으면 `remote_user`보다 우선한다.
[6.4](#64)로 확인하고 공용 inventory에서 해당 줄을 제거한다.

### 8.5 SSH 키 암호를 반복해서 묻는다

작업이 여러 번의 Ansible 실행으로 나뉘면 실행마다 암호를 묻는다. `ssh-add`로 키를
등록하면 한 번만 입력하면 된다.

```bash
ssh-add ~/.ssh/id_ed25519
```

### 8.6 `CryptographyDeprecationWarning: TripleDES ...`

paramiko 라이브러리의 경고이며 작업 결과와 무관하다. 무시해도 된다.

---

## 9. 신규 관리자 체크리스트

| 순서 | 항목 | 확인 방법 |
| --- | --- | --- |
| 1 | Ansible 설치 | `ansible --version` |
| 2 | SSH 키로 서버 접속 | `ssh -p <port> <계정>@<IP>` |
| 3 | 저장소 clone | `ls <저장소>/ansible/inventory.ini` |
| 4 | `~/.ansible.cfg` 작성 | `ansible --version \| grep "config file"` |
| 5 | 전체 서버 NOPASSWD sudo 설정 | `ansible 'FARM:LAB' -m command -a 'sudo -n true' -o` |
| 6 | 접속 확인 | `ansible farm8 -m ping` |

여섯 단계를 마치면 모듈 문서의 절차를 수행할 수 있다.
