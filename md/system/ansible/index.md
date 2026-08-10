# ansible 개요

`ansible`은 별도의 모듈이 아니라, admin_infra_server의 모듈들(`container-images`,
`kerberos-nfs`, `monitoring`, `remote-operations`, `server-state`)을 사용하기 위해
Ansible을 어떻게 설정하는지를 다룬다.

관리 데스크탑에서 실행하는 명령은 대부분 Ansible을 통해 FARM/LAB 서버에
접속한다. 따라서 각 모듈 문서의 절차를 수행하기 전에 이 문서의 설정을 먼저
마쳐야 한다. 설정이 없으면 모듈 명령은 서버에 접속하지 못하고 실패한다.

## 설정 구조

관리 서버는 여러 관리자가 함께 사용하고, 각 관리자는 자신의 계정과 SSH 키로
서버에 접속한다. 따라서 설정을 두 가지로 나눈다.

| 구분 | 내용 | 위치 | 공유 여부 |
| --- | --- | --- | --- |
| 서버 목록 | host 이름, IP, SSH port | `admin_infra_server/ansible/inventory.ini` | 저장소에서 공유 |
| 접속 계정과 실행 환경 | 접속 계정, 임시 디렉터리 경로 | `~/.ansible.cfg` | 관리자별로 각자 보유 |

서버 목록은 모든 관리자가 동일하므로 저장소에서 공유하고, 접속 계정은 관리자마다
다르므로 각자의 홈 디렉터리에 둔다. 공유 파일에는 접속 계정을 기록하지 않는다.

## 문서

| 문서 | 내용 |
| --- | --- |
| [기초 개념](basic.md) | Ansible의 동작 방식, inventory·playbook·role, 설정 파일 탐색 순서와 우선순위, 권한 상승 |
| [설정](config.md) | `~/.ansible.cfg` 작성, 공용 inventory, sudo 권한 준비, 확인 절차와 문제 해결 |

Ansible을 처음 다루는 경우 [기초 개념](basic.md)을 먼저 읽고 [설정](config.md)으로
넘어간다. 이미 Ansible에 익숙하다면 [설정](config.md)만 확인해도 된다.
