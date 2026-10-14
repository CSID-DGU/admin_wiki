# kdc-setup 운영

## 이 문서에서 다루는 내용

- AD, Secret, 노드 keytab, ccache, NFS 상태를 어떤 순서로 확인할지
- 계정과 Pod 생성·삭제 뒤에 어떤 흔적이 남아야 하고 무엇이 지워져야 하는지
- 사용자 단위 장애와 노드 전체 장애를 어떻게 구분할지

## 빠른 이동

| 필요할 때 | 문서 |
| --- | --- |
| 전체 구조와 역할 분담을 먼저 본다 | [개요](index.md) |
| 파일 위치와 보안 규칙을 본다 | [설계](design.md) |
| Helm, CI, Secret 값의 위치를 본다 | [설정](config.md) |

## 1. 작업할 때 지킬 것

1. 계정과 Pod 생성·삭제는 config-server 작업으로 수행한다. 노드나 AD에서 손으로 만들거나 지우지 않는다.
2. keytab, 개인키, Secret `data`는 일반 운영 문서·로그·티켓에 출력하지 않는다.
3. 사용자 장애는 해당 사용자와 Pod가 배치된 노드 범위에서 먼저 확인한다.
4. `/tmp/krb5cc_0`에는 현재 노드의 머신 principal 이외의 ticket을 발급하지 않는다.
5. NFS 관련 D-state가 있으면 반복 restart, 강제 unmount, 연속 mount를 중단한다.

## 2. 정기적으로 확인할 것

### Kubernetes

```bash
ns=ailab-operation
kubectl -n "$ns" get deploy,pod,cronjob
kubectl -n "$ns" get events --sort-by=.lastTimestamp
kubectl -n "$ns" logs deploy/config-server-operation-controller --since=30m
kubectl -n "$ns" get job | grep krb5-reconcile          # 최근 재조정 실행
kubectl -n "$ns" logs job/<최근_krb5-reconcile_job_이름>
```

config-server 제어기가 Ready인지, AD 계정 생성·복제 대기와 FARM 노드 배포가 반복해서 실패하지 않는지, 30분 재조정이 고아 후보를 남기지 않았는지 확인한다.
사용자 keytab Secret은 값이 아니라 메타데이터만 확인한다.

```bash
target_user='<user>'
kubectl -n "$ns" get secret "krb5-keytab-$target_user" \
  -o custom-columns=NAME:.metadata.name,CREATED:.metadata.creationTimestamp
```

### AD와 노드 인증 파일

AD DC에서 사용자·전용 그룹·RFC2307 번호를 확인하고, 선택 노드에서는 timer와
ccache의 권한·유효성을 확인한다.

```bash
target_user='<user>'
target_uid='<uid>'

sudo samba-tool user show "$target_user"
sudo samba-tool group show "${target_user}_gid"
sudo systemctl is-enabled "decs-krb-refresh@$target_user.timer"
sudo systemctl is-active "decs-krb-refresh@$target_user.timer"
sudo stat -c '%U %G %a %n' \
  "/etc/decs-krb/keytabs/$target_user.keytab" \
  "/etc/decs-krb/refresh.d/$target_user.env" \
  "/run/user/$target_uid/krb5cc_ailab"
sudo env KRB5CCNAME="FILE:/run/user/$target_uid/krb5cc_ailab" klist
```

keytab·환경 파일은 root 소유 `0400`, ccache는 대상 UID/GID 소유 `0600`이어야
한다. `klist -k`로 keytab 내용을 출력하지 않는다.

### NFS와 노드 Kerberos ticket

```bash
systemctl is-active rpc-gssd
findmnt -T /home/tako2/share/user -o TARGET,SOURCE,FSTYPE,OPTIONS
sudo klist -c FILE:/tmp/krb5cc_0
ps -eo pid,stat,comm,args | awk '$2 ~ /^D/'
```

홈 경로 mount, rpc.gssd, 머신 principal, D-state를 함께 확인한다. Pod에서만 문제가 나면 Pod UID/GID와 ccache 공유 경로를 먼저 본다. 노드 전체에서 문제가 나면 머신 ticket, rpc.gssd, NFS mount를 먼저 본다.

## 3. 계정과 Pod를 만든 뒤 확인할 것

### 계정 생성 후

1. config-server 계정 파일과 AD RFC2307 UID/GID를 대조한다.
2. Secret 메타데이터, NAS 홈의 숫자 소유권·모드를 확인한다.
3. Pod 생성 뒤 대상 노드의 timer·ccache와 Pod 내부 홈 읽기·쓰기를 확인한다.

### Pod 삭제 후

대상 노드에서 timer, keytab, 환경 파일이 제거됐는지 확인한다. AD 사용자와
Secret은 다음 Pod 실행을 위해 남아야 한다.

```bash
target_user='<user>'
sudo systemctl status "decs-krb-refresh@$target_user.timer" --no-pager
sudo test ! -e "/etc/decs-krb/keytabs/$target_user.keytab"
sudo test ! -e "/etc/decs-krb/refresh.d/$target_user.env"
```

같은 노드에 같은 사용자의 다른 Pod가 남아 있으면 keytab과 timer는 **남아 있어야 정상이다**. 지우면 살아 있는 Pod의 티켓이 갱신되지 않아 홈이 `nobody`로 보인다.

### 계정 삭제 후

AD 사용자와 사용자 keytab Secret이 사라졌는지, 작업이 받은 노드(`node_name`)의 사용자 timer·keytab·ccache가 정리됐는지 확인한다. 계정 회수는 컨테이너를 썼던 노드마다 따로 등록된다. 정리에 실패한 노드는 `krb5_cleanup_pending`에 남고 30분 재조정이 다시 시도한다. 전용 AD 그룹은 자동 삭제 대상이 아니므로 임의로 지우지 않는다.

## 4. 문제별 확인 순서

| 증상 | 먼저 확인할 것 | 금지할 것 |
| --- | --- | --- |
| AD 생성·keytab 발급 실패(`KDC_FAILED`) | 단계 기록, 대상 DC, 동일 이름의 사용자·그룹 | DC wrapper의 반복 직접 실행 |
| AD 복제 대기 초과(`AD_REPLICATION_TIMEOUT`) | 모든 DC가 그 사용자를 같은 UID로 돌려주는지, DC 사이 복제 상태 | 한 DC에만 있는 상태로 Pod를 수동 생성 |
| 노드 신원 확인 대기 초과 | 그 노드에서 `id <user>`, winbind·idmap 캐시, NAS 홈 소유자 | 노드 캐시를 확인 없이 반복 초기화 |
| 대상 노드 배포 실패 | 노드 목록, 제한된 SSH 채널, keytab 파일 모드, service journal | keytab을 복사해 우회 |
| ccache 갱신 실패 | DNS·시간·Realm·principal·keytab 모드 | keytab 내용을 출력 |
| Pod 홈 접근 실패 | Pod UID/GID, ccache, rpc.gssd, 머신 ticket, mount | NAS를 바로 재시작 |
| NFS D-state | stack·kernel log·NFS 응답·네트워크 | 반복 mount/unmount 또는 service restart |

머신 ccache의 principal이 잘못됐거나 ticket이 만료된 경우에만, 정확한 현재 노드
머신 principal을 확인한 후 별도 승인 절차에 따라 복구한다. 사용자 principal이나
다른 Realm을 지정하지 않는다.

## 5. 노드 추가·변경

신규 AD DC와 FARM 실행 노드는 먼저 제한된 관리 채널, 시간 동기화, rpc.gssd와
FARM 홈 mount를 준비한다. 시험 노드 한 대에서 시험 사용자로 keytab 권한, timer,
ccache, TGT, NFS 읽기·쓰기를 검증한 뒤 노드 목록에 추가한다.

공통 refresh 스크립트·systemd 템플릿의 변경은 사용자 배포 중에도 다시 설치될 수
있다. 시험 노드에서 확인한 뒤 기존 노드의 버전·소유권을 비교하고 확대한다.
