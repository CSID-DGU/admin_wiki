# remote-operations 설정

> [개요](index.md) · [설계](design.md) · [운영](operations.md)

## 설정 모델

설정은 `remote_boot.example.env`를 복사하여 local 파일에서 관리한다.

```bash
cd /home/jy/server_manage/remote-operations
cp config/remote_boot.example.env config/remote_boot.local.env
```

주요 설정 그룹:

| 그룹 | 예 |
| --- | --- |
| target | FARM/LAB 목록, 기본/priority target |
| 순서/gate | pre-delay, gate timeout/poll, secondary delay |
| container | restart enable, timeout, post-check poll |
| network | Ansible inventory, broadcast IP, MAC address |
| health | 필수 mount와 host share template |
| test container | image, UID/GID, mount, memory, runtime |
| logging/alert | log path, rotate count, notify API와 webhook |

실제 MAC, password와 webhook은 `remote_boot.local.env`에만 둔다. example에는
변수 이름과 안전한 placeholder만 유지한다.

## 개인 Ansible inventory 준비

관리 데스크탑은 여러 관리자가 공유한다. Ansible inventory는 host 그룹당
`ansible_user`를 하나만 가질 수 있어서, `/etc/ansible/inventory.ini`(특정
관리자 계정으로 고정)를 그대로 쓰면 다른 관리자는 그 계정으로 원격 서버에
접속을 시도하다가 SSH 인증에 실패한다.
그래서 관리자마다 자신의 계정으로 접속하는 개인 inventory가 필요하다.
([UID_GID_Management_System](https://app.notion.com/p/UID-GID-Management-System-32bc7692a2638085a14ff1f9690601b7) 5.2.4 내용을 보고 inventory.ini 파일을 ~/uid_gid/inventory.ini에
위치시킨 경우 지금 설명하는 단계를 진행해야 한다.)

- 위치: `~/ansible/inventory.ini`. 특정 프로젝트에 속하지 않는 개인 경로다.
  remote-operations와 `uid_gid` 등 이 데스크탑의 여러 도구가 각자의 설정에서
  이 경로를 가리키기만 하고, 어느 한쪽도 이 파일을 소유하지 않는다.
- 준비: `/etc/ansible/inventory.ini`를 복사해서 `ansible_user`만 자신의
  계정으로 바꾼다.
- 원격 서버의 `~/.ssh/authorized_keys`에 자신의 공개키를 등록해야 실제 SSH
  인증이 된다. inventory 파일만으로는 접속 권한이 생기지 않는다.
- (선택) `~/ansible/ansible.cfg`를 만들어두면 `-i` 없이 `ansible <host> ...`
  명령이 기본으로 이 inventory를 사용한다.

```ini
[defaults]
inventory = /home/<본인계정>/ansible/inventory.ini
interpreter_python = auto_silent
host_key_checking = False
retry_files_enabled = False
```

Ansigle 설정이 완료되면 `remote_boot.local.env`에서 
REMOTE_BOOT_ANSIBLE_INVENTORY를 다음과 같이 수정한다.

```bash
REMOTE_BOOT_ANSIBLE_INVENTORY="/home/<본인계정>/ansible/inventory.ini"
```

이 개인 설정은 dry-run 검증과 수동 운영에 쓰인다. 실제 자동 부팅을 담당하는
`remote-boot.service`(systemd)는 별도 관리자 계정 소유로 이미 배포되어 있으며
이 개인 설정과 무관하게 동작한다.

## MAC 주소

`REMOTE_BOOT_MAC_*`는 물리 서버 하드웨어의 실제 MAC 주소로 장비통합관리문서에서 값을
가져온다.

## 첫 설정 체크리스트

신규 관리자가 이 저장소를 처음 pull한 뒤 dry-run 검증까지 마치는 순서:

1. 개인 SSH 공개키를 각 FARM/LAB 서버의 `~/.ssh/authorized_keys`에 등록
2. `~/ansible/inventory.ini` 준비 (`ansible_user`를 자신의 계정으로)
3. `remote_boot.example.env` → `remote_boot.local.env` 복사
4. `REMOTE_BOOT_ANSIBLE_INVENTORY`를 자신의 inventory 경로로 설정
5. `REMOTE_BOOT_MAC_*` 값을 실제 MAC으로 채움
6. [운영 문서](operations.md)의 dry-run 명령으로 검증
