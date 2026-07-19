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
