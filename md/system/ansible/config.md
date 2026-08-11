# Ansible 설정

> [개요](index.md) · [기초 개념](basic.md)

## 1. 개요

이 문서는 관리 서버에서 admin_infra_server의 모듈들을 실행할 수 있도록 Ansible을
설정하는 방법을 설명한다. 개념 설명은 [기초 개념](basic.md)에 있다.

이 문서에서 `<저장소>`는 github에서 <u>admin_infra_server를 clone한 경로</u>를,
`<관리자계정>`은 관리 서버에서 FARM/LAB 서버에 접속할 본인의 계정 이름을 뜻한다. 관리자마다 값이 다르므로 자신의 값으로 바꿔서 사용한다.

### 설정 파일 구성

관리 서버는 여러 관리자가 함께 사용하고, 각 관리자는 자신의 계정과 SSH 키로 서버에
접속한다. 따라서 설정을 성격에 따라 두 파일로 나눈다.

| 파일 | 담는 내용 | 관리 방식 |
| --- | --- | --- |
| `<저장소>/ansible/inventory.ini` | 서버 목록 (host 이름, IP, SSH port) | 저장소에서 공유. 모든 관리자가 같은 값을 사용한다 |
| `~/.ansible.cfg` | 접속 계정, 임시 디렉터리 경로 | 관리자별로 각자 작성한다. 저장소에 넣지 않는다 |

기준은 "이 값이 관리자마다 다른가"이다. 서버 목록은 모두 같으므로 공유하고, 접속
계정은 각자 다르므로 개인 파일에 둔다.

> **기존에 이 저장소를 쓰던 관리자에게**: 예전에는 admin_infra_server의 모듈 안에 공유 `ansible.cfg`가
> 있었고 명령마다 `ANSIBLE_CONFIG=...`를 지정했다. 그 파일은 삭제됐다. 저장소를
> 최신으로 받은 뒤에는 **`~/.ansible.cfg`가 없으면 모듈 명령이 동작하지 않는다.**
> [4장(개인 설정 파일 작성)]()의 파일을 먼저 만든다.

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

### 2.2 SSH 키 등록

#### 왜 키가 필요한가

Ansible은 대상 서버(LAB/FARM)에 SSH로 접속해서 작업한다. 그런데 **사람이 지켜보지 않는 상태로
실행되기 때문에 비밀번호를 물어보면 입력해 줄 사람이 없다.** 서버 16대에 명령을
내리면 비밀번호를 16번 물어보게 되고, 그 자리에서 멈춘다.

그래서 비밀번호 대신 **SSH 공개키 인증**을 사용한다. 내 컴퓨터에 있는 개인키와 서버에
등록해 둔 공개키가 짝을 이루면 비밀번호 없이 접속된다. 이 준비가 되어 있어야 Ansible이
멈추지 않고 끝까지 실행된다.

또한 각 관리자는 대상 서버에 **자신의 계정과 자신의 키**로 접속한다. 공용 계정은 사용하지 않는다.
누가 무엇을 실행했는지 서버 로그에 남아야 하기 때문이다.

#### ① 관리 서버에서 키 확인·생성

**아래 두 명령은 관리 서버(관리용 데스크탑)에서 실행한다.** 대상 서버가 아니다.
키는 관리자당 하나만 있으면 되고, 그 하나를 모든 서버에 등록해서 쓴다.

```bash
ls ~/.ssh/id_ed25519
```

파일 경로가 출력되면 이미 키가 있는 것이므로 ②로 넘어간다.
`No such file or directory`가 나오면 키를 만든다.

```bash
ssh-keygen -t ed25519
```

passphrase를 사용해서 키를 생성한다. 두 파일이 만들어진다.

| 파일 | 성격 | 다루는 방법 |
| --- | --- | --- |
| `~/.ssh/id_ed25519` | **개인키** | 관리 데스크탑에만 둔다. 절대 밖으로 내보내지 않는다 |
| `~/.ssh/id_ed25519.pub` | **공개키** | 대상 서버에 등록하는 값이다 |

#### ② 모든 FARM/LAB 서버에 공개키 등록

**공개키는 접속할 서버마다 등록해야 한다.** 한 대에 등록했다고 다른 서버에 적용되지
않는다. `ssh-copy-id`가 공개키를 대상 서버의 `~/.ssh/authorized_keys`에 넣어 준다.

이 명령도 **관리 데스크탑에서** 실행하며, 서버마다 한 번씩 반복한다. 이때는 아직
키가 없으므로 **그 서버의 비밀번호를 묻는다.** 등록에 성공하면 다음부터 묻지 않는다.

```bash
# FARM (port는 서버마다 다르다)
ssh-copy-id -p 8081 <관리자계정>@192.168.2.11    # farm1
ssh-copy-id -p 8082 <관리자계정>@192.168.2.12    # farm2
ssh-copy-id -p 8086 <관리자계정>@192.168.2.16    # farm6
ssh-copy-id -p 8087 <관리자계정>@192.168.2.17    # farm7
ssh-copy-id -p 8088 <관리자계정>@192.168.2.18    # farm8
ssh-copy-id -p 8089 <관리자계정>@192.168.2.19    # farm9

# LAB
ssh-copy-id -p 8081 <관리자계정>@192.168.1.11    # lab1
ssh-copy-id -p 8082 <관리자계정>@192.168.1.12    # lab2
# ... lab10까지 같은 방식
```

IP와 port는 [3장(공용 inventory)](#3-공용-inventory)의 목록과 같다.

#### ③ 접속 확인

**관리용 데스크탑에서 모든 서버를 대상으로 확인한다.** 한 대만 되고 나머지가 안 되면 그 서버에서 Ansible이 멈추게 된다. 우선 한 서버에 대해서 접속 가능 여부를 먼저 확인한다.

```bash
ssh -p 8088 <관리자계정>@192.168.2.18
```

**비밀번호를 묻지 않고 바로 로그인되면 성공이다.** 비밀번호를 물어보면 그 서버는 아직
공개키가 등록되지 않은 것이므로 ②를 다시 실행한다. 확인 후 `exit`으로 빠져나온다.

전체 서버를 한 번에 확인하는 방법은 [6.3 접속 확인](#63-접속-확인)에 있다. 다만 그
명령은 `~/.ansible.cfg`와 inventory가 준비된 뒤에야 쓸 수 있으므로, 설정을 마친 뒤에
확인해도 된다.

### 2.3 저장소 clone

```bash
git clone <저장소 URL>
```

clone 경로는 관리자마다 달라도 된다. 다만 **자신이 어디에 clone했는지 정확히 알고
있어야 한다.** 앞으로 직접 작성할 설정 파일들에 이 경로를 적어 넣어야 하기 때문이다.

clone한 위치를 확인해 둔다.

```bash
cd <clone한 폴더>/admin_infra_server
pwd
```

출력된 값이 앞으로 `<저장소>`라고 표기되는 값이다.

```bash
# 출력 예시
$ pwd
/home/suhyeon/CSID-DGU/admin_infra_server

# <저장소>는 '/home/suhyeon/CSID-DGU/admin_infra_server'가 된다
```

#### clone 경로가 바뀌면 함께 바뀌는 값

같은 저장소라도 clone 위치가 다르면 **아래 값들을 각자 자기 경로로 고쳐 적어야 한다.**
문서의 예시를 그대로 복사하면 동작하지 않는다.

| 고쳐 적을 곳 | 설정 이름 | 참고 |
| --- | --- | --- |
| `~/.ansible.cfg` | `inventory` | [4장](#4-개인-설정-파일-작성) |
| `remote-operations/config/remote_boot.local.env` | `REMOTE_BOOT_ANSIBLE_INVENTORY` | [7장](#7-모듈별-적용-현황) |
| `user-lifecycle/config/db_config.local.env` | `ANSIBLE_INVENTORY` | [7장](#7-모듈별-적용-현황) |
| `user-lifecycle/ad_backup/config.local.env` | `AD_BACKUP_INVENTORY` | [7장](#7-모듈별-적용-현황) |

예를 들어 관리자 `suhyeon`이 홈 아래 `CSID-DGU/`에 clone했고, 관리자 `minji`가 홈에
바로 clone했다면 `~/.ansible.cfg`의 같은 줄이 이렇게 달라진다.

```ini
# suhyeon:  clone 위치가 /home/suhyeon/CSID-DGU/admin_infra_server
inventory = /home/suhyeon/CSID-DGU/admin_infra_server/ansible/inventory.ini
```

```ini
# minji:  clone 위치가 /home/minji/admin_infra_server
inventory = /home/minji/admin_infra_server/ansible/inventory.ini
```

바뀌는 것은 **`/ansible/inventory.ini` 앞의 경로뿐**이고, 뒷부분은 저장소 안의 고정된
위치이므로 그대로 둔다.

---

## 3. 공용 inventory
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

### 서버를 추가·변경할 때

이 파일은 **저장소에 커밋해서 관리한다.** 관리자가 각자 자기 홈에 사본을 만들어
쓰면 서버가 추가됐을 때 누구는 반영하고 누구는 못 해서 값이 어긋난다.

같은 서버 집합을 나타내는 파일이 하나 더 있다.
`user-lifecycle/server_info/servers.jsonl`은 `inventory.ini`를 **입력으로 받아
생성**되므로, 순서대로 갱신해야 한다.

```bash
# 1. 공용 inventory를 고친다 (서버 추가·IP 변경·port 변경)
nano <저장소>/ansible/inventory.ini

# 2. servers.jsonl을 다시 생성한다
cd <저장소>/user-lifecycle/server_info
python3 generate_servers_jsonl.py

# 3. 두 파일을 함께 커밋한다
cd <저장소>
git add ansible/inventory.ini user-lifecycle/server_info/servers.jsonl
git commit -m "inventory: <무엇을 바꿨는지>"
git push
```

**두 파일은 반드시 같은 커밋에 넣는다.** 한쪽만 올라가면 모듈마다 인식하는 서버
목록이 달라진다.

나머지 관리자는 `git pull`로 받는다. 개인이 고칠 것은 없다.

```bash
cd <저장소> && git pull
```

두 파일이 어긋나지 않았는지는 다음으로 확인한다. 두 숫자가 같아야 한다.

```bash
grep -cE "^(farm|lab)[0-9]+ " ansible/inventory.ini
wc -l < user-lifecycle/server_info/servers.jsonl
```

`farm`·`lab` **뒤에 번호가 붙은 계산 서버만** 센다. `servers.jsonl` 생성기가
`farm<번호>`/`lab<번호>` 형식만 인식하므로, `lab-storage`처럼 번호가 없는 호스트는
`inventory.ini`에만 있고 `servers.jsonl`에는 들어가지 않는 것이 정상이다.

---

## 4. 개인 설정 파일 작성
홈 디렉터리에 `~/.ansible.cfg`를 만든다. 파일 이름이 반드시 `.ansible.cfg`여야
Ansible이 자동으로 찾는다. `~/ansible/ansible.cfg`처럼 폴더 안에 두면 무시된다.

편집기로 파일을 연다.

```bash
nano ~/.ansible.cfg
```

아래 내용을 **복사해서 붙여넣는다.**

```ini
[defaults]
inventory          = <저장소>/ansible/inventory.ini
remote_user        = <관리자계정>
local_tmp          = /tmp/ansible-local-<관리자계정>
remote_tmp         = ~/.ansible/tmp
interpreter_python = auto_silent
host_key_checking  = False
retry_files_enabled = False

[ssh_connection]
control_path_dir = /tmp/ansible-cp-<관리자계정>
pipelining = True
```

붙여넣은 뒤 `<저장소>`와 `<관리자계정>` 자리를 자신의 값으로 바꾼다. 고칠 곳은 네
군데다.

| 줄 | 바꿀 것 |
| --- | --- |
| `inventory` | `<저장소>` → [2.3](#23-저장소-clone)에서 확인한 clone 경로 |
| `remote_user` | `<관리자계정>` → 서버 접속 계정 |
| `local_tmp` | `<관리자계정>` → 서버 접속 계정 |
| `control_path_dir` | `<관리자계정>` → 서버 접속 계정 |

계정이 `suhyeon`이고 `/home/suhyeon/CSID-DGU/admin_infra_server`에 clone했다면
완성된 파일은 다음과 같다.

```ini
[defaults]
inventory          = /home/suhyeon/CSID-DGU/admin_infra_server/ansible/inventory.ini
remote_user        = suhyeon
local_tmp          = /tmp/ansible-local-suhyeon
remote_tmp         = ~/.ansible/tmp
interpreter_python = auto_silent
host_key_checking  = False
retry_files_enabled = False

[ssh_connection]
control_path_dir = /tmp/ansible-cp-suhyeon
pipelining = True
```

`remote_tmp`만 `~`로 시작하는데, 이는 **대상 서버에서** 접속한 계정의 홈을 뜻하므로
바꾸지 않는다. 이유는 아래 "임시 디렉터리 설정이 세 개인 이유"에 있다.

작성한 내용이 실제로 적용됐는지는 [6장(설정 확인)](#6-설정-확인)에서 확인한다.

### 임시 디렉터리 설정이 세 개인 이유

임시 디렉터리는 **관리 데스크탑에 만들어지는 것**과 **대상 서버에 만들어지는 것**으로
나뉘며, 다루는 방법이 다르다.

| 설정 | 만들어지는 곳 | 값 |
| --- | --- | --- |
| `local_tmp` | 관리 데스크탑 | 계정 이름을 넣어 분리한다 |
| `control_path_dir` | 관리 데스크탑 | 계정 이름을 넣어 분리한다 |
| `remote_tmp` | 대상 서버 | `~/.ansible/tmp` (Ansible 기본값) |

**관리 데스크탑 쪽**: Ansible은 이 경로가 없으면 **소유자만 접근 가능한 권한(0700)으로
직접 생성한다.** 여러 관리자가 `/tmp/ansible-local` 같은 공용 경로를 함께 쓰면 먼저
실행한 관리자가 소유자가 되고, 나머지는 접근하지 못해 다음처럼 실패한다.

```
PermissionError: [Errno 13] Permission denied: '/tmp/ansible-local/ansible-local-...'
```

그래서 경로에 계정 이름을 넣어 분리한다.

**대상 서버 쪽**: 여기서는 `/tmp/...` 같은 절대 경로를 쓰면 안 된다. `become`으로 root
작업을 하면 그 디렉터리가 **root 소유 0700으로 만들어져**, 이후 root가 아닌 작업이
같은 경로를 쓰지 못한다. `~/.ansible/tmp`는 접속한 사용자의 홈 아래라 root와 관리자
계정이 자연히 분리된다. 이 값이 Ansible 기본값이기도 하므로
`ansible-config dump --only-changed`에는 나타나지 않는다.

### 환경변수는 필요하지 않다

`~/.ansible.cfg`는 Ansible이 자동으로 찾으므로 `.bashrc`에 `ANSIBLE_CONFIG`나
`ANSIBLE_INVENTORY`를 설정할 필요가 없다. 과거 설정에서 이 환경변수들을 추가했다면
제거한다.

---

## 5. sudo 권한 준비
`admin_infra_server` 모듈의 Ansible 작업은 대상 서버에서 root 권한을 사용한다. 점검만 하는 작업도
마찬가지다. 따라서 **명령을 실행하는 관리자 각자의 계정**에 대해 대상 서버에서
비밀번호 없이 sudo를 쓸 수 있어야 한다.

설정되어 있지 않으면 다음과 같이 실패한다.

```
TASK [Gathering Facts] *********************************************************
fatal: [farm8]: FAILED! => {"msg": "Missing sudo password"}
```

### 5.1 현재 상태 확인

**최종적으로는 FARM/LAB 전체 서버에 설정되어 있어야 한다.** 다만 여기서는 먼저
**한 대만** 확인한다. 설정 방법이 맞는지 검증한 뒤 나머지에 일괄 적용하는 순서이기
때문이다.

아래 명령은 **관리 데스크탑에서** 실행한다. farm8 한 대에 접속해서 sudo가 비밀번호
없이 되는지만 본다.

```bash
ssh -p 8088 <관리자계정>@192.168.2.18 'sudo -n true && echo "설정됨" || echo "설정 안 됨"'
```

`sudo -n`은 비밀번호를 묻지 않고 sudo를 시도하는 옵션이다. 비밀번호가 필요하면 묻지
않고 그냥 실패하므로, 설정 여부를 확인하는 용도로 쓴다.

| 출력 | 의미 | 다음 단계 |
| --- | --- | --- |
| `설정됨` | 이 서버는 준비됐다 | [5.3](#53-전체-서버에-일괄-적용)으로 가서 전체에 적용한다 |
| `설정 안 됨` | NOPASSWD sudo가 없다 | [5.2](#52-서버-한-대에-설정)로 이 서버부터 설정한다 |

전체 서버의 상태를 한 번에 보는 방법은 [5.3](#53-전체-서버에-일괄-적용) 끝에 있다.
그 명령은 `~/.ansible.cfg`와 inventory가 준비된 뒤에 쓸 수 있다.

### 5.2 서버 한 대에 설정
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

**NOPASSWD sudo는 FARM/LAB 전체 서버에 설정되어 있어야 한다.** 서버 한 대라도 빠져
있으면 그 서버에서 모듈 명령이 실패한다.

5.2를 서버마다 반복할 필요는 없다. 한 대에서 정상 동작을 확인했다면 아래 명령으로
나머지 전체에 한 번에 적용한다. 이 작업은 모듈 명령이 아닌 `ansible` 명령을 직접
사용하므로 `-K` 옵션으로 sudo 비밀번호를 한 번만 입력하면 된다.

```bash
ansible 'FARM:LAB' -b -K -f 1 -m lineinfile \
  -a "path=/etc/sudoers.d/<관리자계정> \
      line='<관리자계정> ALL=(ALL) NOPASSWD:ALL' \
      create=yes owner=root group=root mode=0440 \
      validate='visudo -cf %s'"
```

| 옵션 | 역할 |
| --- | --- |
| `-b` | root 권한으로 실행한다 |
| `-K` | sudo 비밀번호를 한 번 입력받는다 |
| `-f 1` | 한 번에 서버 한 대씩 처리한다. 출력이 섞이지 않아 결과를 확인하기 쉽다 |
| `validate` | 파일을 설치하기 **전에** 문법을 검사한다. 통과하지 못하면 설치하지 않는다 |

`validate`가 안전장치다. Ansible이 임시 파일에 내용을 쓴 뒤 `visudo -cf`로 검사하고
**통과한 경우에만** 설치하므로, 문법 오류로 그 서버의 sudo가 잠기는 일이 없다.
이미 적용된 서버는 `ok`로 표시되고 다시 쓰지 않는다.

전체 결과를 확인한다.

```bash
ansible 'FARM:LAB' -m command -a 'sudo -n true' -o
```

각 서버의 sudo 비밀번호가 다르면 `-K` 한 번으로 처리되지 않는다. 실패한 서버는
5.2(서버 한 대에 설정)의 방법으로 개별 적용한다.

---

## 6. 설정 확인

### 6.1 설정 파일이 인식되는지
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

먼저 한 대로 확인한다.

```bash
ansible farm8 -m ping
```

`SUCCESS`와 `"ping": "pong"`이 나오면 접속과 계정 설정이 정상이다.

이어서 **전체 서버**를 한 번에 확인한다. [2.2](#22-ssh-키-등록)에서 공개키를 빠뜨린
서버가 있는지 여기서 드러난다.

```bash
ansible 'FARM:LAB' -m ping -o
```

`-o`는 서버당 한 줄로 출력하는 옵션이라 결과를 훑어보기 좋다. 모든 줄이 `SUCCESS`여야
한다. `UNREACHABLE`이 나온 서버는 공개키가 등록되지 않았거나 계정이 맞지 않은 것이므로
[2.2](#22-ssh-키-등록)의 `ssh-copy-id`를 그 서버에 다시 실행한다.

### 6.4 sudoers 파일 검증
```bash
ansible 'FARM:LAB' -b -f 1 -m command -a 'visudo -c' -o
```

`/etc/sudoers.d/` 전체를 검사한다. 각 파일마다 `parsed OK`가 나오면 정상이다.

**`rc=1`이 나와도 본인 파일 문제가 아닐 수 있다.** `visudo -c`는 디렉터리 안의 파일을
하나라도 문제가 있으면 실패로 처리한다. `stderr`를 보면 어느 파일인지 나온다.

```
stderr: /etc/sudoers.d/jy: bad permissions, should be mode 0440
stdout: /etc/sudoers: parsed OK
        /etc/sudoers.d/<관리자계정>: parsed OK      ← 본인 파일은 정상
```

이 경우 본인 설정은 문제가 없다. **권한이 잘못된 파일은 sudo가 통째로 무시하므로,
그 파일의 소유자에게 알려야 한다.** 해당 관리자의 NOPASSWD가 실제로는 적용되지 않고
있는 상태다.

### 6.5 host 해석 확인
```bash
ansible-inventory --host farm8
```

`ansible_host`와 `ansible_port`만 나오고 `ansible_user`가 없어야 한다.
`ansible_user`가 보이면 inventory에 계정이 남아 있는 것이며, 이 경우 개인 설정의
`remote_user`가 적용되지 않는다.

---

## 7. 모듈별 적용 현황
모든 모듈이 이 구조를 사용한다. 모듈마다 inventory 경로를 지정하는 위치가 다르므로,
저장소를 다른 곳에 clone했다면 아래 파일들의 경로도 함께 맞춘다.

| 모듈 | inventory 지정 위치 | 비고 |
| --- | --- | --- |
| [`server-state`](../server-state/index.md) | 없음 | `~/.ansible.cfg`만으로 동작한다 |
| [`remote-operations`](../remote-operations/index.md) | `config/remote_boot.local.env`의 `REMOTE_BOOT_ANSIBLE_INVENTORY` | **설정 파일이 환경변수를 덮어쓴다.** 셸에서 export해도 이 값이 이긴다 |
| `user-lifecycle` | `config/db_config.local.env`의 `ANSIBLE_INVENTORY` | `legacy/` 스크립트도 같은 파일을 읽는다 |
| `user-lifecycle/ad_backup` | `ad_backup/config.local.env`의 `AD_BACKUP_INVENTORY` | **별도 파일이다.** `config.example.env`를 복사해 만든다 |
| [`monitoring`](../monitoring/index.md) | 지정하지 않으면 저장소의 `ansible/inventory.ini` | 필요하면 `CLUSTER_MONITOR_ANSIBLE_INVENTORY`로 덮어쓴다 |
| [`kerberos-nfs`](../kerberos-nfs/index.md) | 해당 없음 | role만 제공하며 `server-state`를 통해 실행된다 |

`*.local.env` 파일은 모두 Git에서 제외된다. 각 모듈의 `*.example.env`를 복사해 자신의
값으로 고쳐 쓴다.

### 실행 병렬도 조절

여러 서버를 다루는 명령의 출력이 섞여 읽기 어려우면 동시 실행 수를 낮춘다.

```bash
ansible 'FARM:LAB' -f 1 -m command -a 'sudo -n true' -o     # ansible 직접 실행

ANSIBLE_FORKS=1 ./server-state/bin/server-state audit --hosts farm   # 모듈 명령
```

`server-state`에는 `-f` 옵션이 없지만 환경변수를 그대로 넘기므로 `ANSIBLE_FORKS`가
적용된다. 출력을 읽기 편하게 하려는 것일 뿐이므로, 결과 확인에 문제가 없다면 굳이
낮출 필요는 없다.

---

## 8. 문제 해결

Ansible 실행은 [기초 개념](basic.md#overall-flow)의 실행 순서를 따른다. 오류 메시지로
어느 단계에서 멈췄는지 확인하면 원인을 좁힐 수 있다.

"확인할 곳"을 누르면 해당 절로 이동한다.

| 멈춘 단계 | 대표적인 오류 | 원인 | 확인할 곳 |
| --- | --- | --- | --- |
| 1. 설정 파일 찾기 | 설정을 바꿨는데 반영되지 않는다 | 설정 파일 위치나 이름이 잘못됐다 | [8.3](#83-설정을-바꿨는데-반영되지-않는다) |
| 2. 서버 목록 읽기 | `Could not match supplied host pattern` | 대상 서버가 inventory에 없다 | [3장](#3-공용-inventory) |
| 3. 접속 계정 결정 | 의도하지 않은 계정으로 접속한다 | inventory에 `ansible_user`가 남아 있다 | [8.4](#84-잘못된-계정으로-접속을-시도한다) |
| 4. SSH 접속 | `Permission denied`, `UNREACHABLE` | SSH 키가 등록되지 않았거나 계정이 맞지 않다 | [2.2](#22-ssh-키-등록) |
| 5. 권한 상승 | `Missing sudo password` | 대상 서버에 NOPASSWD sudo가 없다 | [8.2](#82-missing-sudo-password) |
| 6. 작업 실행 | `failed`, `fatal` | 서버 상태가 기준과 다르거나 작업이 오류를 냈다 | 해당 모듈 문서 |

관리 데스크탑에서 일어나는 1~3번은 설정 파일 문제이고, 4번부터는 대상 서버 문제다.

### 8.1 `Permission denied: '/tmp/ansible-local/...'`

```
PermissionError: [Errno 13] Permission denied: '/tmp/ansible-local/ansible-local-...'
ansible.errors.AnsibleError: Invalid settings supplied for DEFAULT_LOCAL_TMP
```

다른 관리자가 먼저 만든 임시 디렉터리에 접근하지 못해 발생한다. `~/.ansible.cfg`의
`local_tmp`가 계정별 경로로 되어 있는지, 그리고 해당 설정 파일이 실제로 인식되고
있는지 6.1에서 확인한다.

### 8.2 `Missing sudo password`
대상 서버에 본인 계정의 NOPASSWD sudo가 없다. 5장의 절차로 설정한다.
다른 관리자에게 설정되어 있어도 본인 계정에는 별도로 필요하다.

### 8.3 설정을 바꿨는데 반영되지 않는다
다음 순서로 확인한다.

1. `ansible --version | grep "config file"`로 어떤 파일이 실제로 사용되는지 확인한다.
2. 현재 디렉터리에 `ansible.cfg`가 있으면 그 파일이 `~/.ansible.cfg`보다 우선한다.
3. `ANSIBLE_CONFIG`나 `ANSIBLE_INVENTORY` 환경변수가 남아 있으면 개인 설정을 덮어쓴다.
   `env | grep ANSIBLE`로 확인하고 `.bashrc`에서 제거한다.

### 8.4 잘못된 계정으로 접속을 시도한다
inventory에 `ansible_user`가 남아 있으면 `remote_user`보다 우선한다.
6.5(host 해석 확인)로 점검하고 공용 inventory에서 해당 줄을 제거한다.

### 8.5 `Timeout waiting for privilege escalation prompt`

```
farm1 | FAILED! => {"msg": "Timeout (12s) waiting for privilege escalation prompt: "}
```

`-K`로 입력한 sudo 비밀번호가 전달되지 않았다. 여러 서버를 병렬로 처리하면서
프롬프트가 뒤엉킨 경우가 대부분이다. `-f 1`을 붙여 한 대씩 실행하면 대개
해결된다.

```bash
ansible 'FARM:LAB' -b -K -f 1 -m command -a 'sudo -n true' -o
```

### 8.6 `/usr/bin/python: not found`

```
farm8 | FAILED! => {"module_stderr": "/bin/sh: 1: /usr/bin/python: not found",
                    "ansible_facts": {"discovered_interpreter_python": "/usr/bin/python"}}
```

대상 서버의 Python 경로 자동 탐색이 실패해 옛 기본값으로 넘어간 것이다. 정상일 때는
`/usr/bin/python3`으로 탐색된다. 프롬프트가 엉킨 실행에서 함께 나타나는 경우가 많으니
`-f 1`로 그 서버만 다시 실행해 본다. 반복된다면 그 서버에 Python 3가 설치되어 있는지
확인한다.

### 8.7 `CryptographyDeprecationWarning: TripleDES ...`

paramiko 라이브러리의 경고이며 작업 결과와 무관하다. 무시해도 된다.

---

## 9. 신규 관리자 체크리스트

| 순서 | 항목 | 확인 방법 |
| --- | --- | --- |
| 1 | [Ansible 설치](#21-ansible-설치) | `ansible --version` |
| 2 | [전체 서버에 SSH 키 등록](#22-ssh-키-등록) | `ssh -p <port> <계정>@<IP>` (비밀번호를 묻지 않아야 한다) |
| 3 | [저장소 clone](#23-저장소-clone) | `ls <저장소>/ansible/inventory.ini` |
| 4 | [`~/.ansible.cfg` 작성](#4-개인-설정-파일-작성) | `ansible --version \| grep "config file"` |
| 5 | [전체 서버 NOPASSWD sudo 설정](#5-sudo-권한-준비) | `ansible 'FARM:LAB' -f 1 -m command -a 'sudo -n true' -o` |
| 6 | [sudoers 파일 검증](#64-sudoers-파일-검증) | `ansible 'FARM:LAB' -f 1 -b -m command -a 'visudo -c' -o` |
| 7 | [접속 확인](#63-접속-확인) | `ansible farm8 -m ping` |
| 8 | 모듈에서 최종 확인 | `server-state audit --hosts farm --component baseline-access` |

8단계가 모두 통과하면 모듈 문서의 절차를 수행할 수 있다. 마지막 단계는 접속·계정·sudo
세 가지를 한 번에 확인하므로, 여기서 모든 서버가 `OK`면 설정이 끝난 것이다.

모듈별로 `*.local.env`를 쓰는 경우에는 [7장(모듈별 적용 현황)](#7-모듈별-적용-현황)의
표에 따라 그 파일의 inventory 경로도 자신의 clone 위치로 맞춘다.
