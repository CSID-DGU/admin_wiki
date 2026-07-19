# kdc-setup 운영

> [개요](index.md) · [설계](design.md) · [설정](config.md)

## 1. 운영 원칙

1. 계정·Pod 수명주기는 config-server API로 수행한다.
2. keytab, 개인키, Secret `data`는 일반 운영 문서·로그·티켓에 출력하지 않는다.
3. 사용자 장애는 해당 사용자와 Pod가 배치된 노드 범위에서 먼저 확인한다.
4. `/tmp/krb5cc_0`에는 현재 노드의 머신 principal 이외의 ticket을 발급하지 않는다.
5. NFS 관련 D-state가 있으면 반복 restart, 강제 unmount, 연속 mount를 중단한다.

## 2. 정기 점검

### Kubernetes 제어면

```bash
kubectl -n ailab-infra get deploy,pod,cronjob
kubectl -n ailab-infra get events --sort-by=.lastTimestamp
kubectl -n ailab-infra logs deploy/containerssh-config-server --since=30m
```

config-server가 Ready이고 AD 생성·FARM 노드 배포 실패가 반복되지 않는지 확인한다.
사용자 keytab Secret은 값이 아니라 메타데이터만 확인한다.

```bash
target_user='<user>'
kubectl -n ailab-infra get secret "krb5-keytab-$target_user" \
  -o custom-columns=NAME:.metadata.name,CREATED:.metadata.creationTimestamp
```

### AD와 노드 자격 증명

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

### NFS와 머신 신원

```bash
systemctl is-active rpc-gssd
findmnt -T /home/tako2/share/user -o TARGET,SOURCE,FSTYPE,OPTIONS
sudo klist -c FILE:/tmp/krb5cc_0
ps -eo pid,stat,comm,args | awk '$2 ~ /^D/'
```

홈 루트 mount, rpc.gssd, 머신 principal과 D-state 유무를 함께 판단한다. Pod에서만
실패하면 Pod UID/GID·ccache 공유 경로를 먼저 보고, 노드 전체에서 실패하면 머신
ticket·rpc.gssd·NFS mount를 먼저 확인한다.

## 3. 생명주기 확인

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

### 계정 삭제 후

AD 사용자와 사용자 keytab Secret이 사라졌는지, 모든 FARM 노드의 사용자 timer·keytab·ccache가
정리됐는지 확인한다. 전용 AD 그룹은 자동 삭제 대상이 아니므로 임의로 지우지 않는다.

## 4. 장애 대응

| 증상 | 먼저 확인할 것 | 금지할 것 |
| --- | --- | --- |
| AD 생성·keytab 발급 실패 | config-server stage, 대상 DC, 동일 이름의 사용자·그룹 | DC wrapper의 반복 직접 실행 |
| 대상 노드 배포 실패 | 노드 목록, 제한된 SSH 채널, keytab 파일 모드, service journal | keytab을 복사해 우회 |
| ccache 갱신 실패 | DNS·시간·Realm·principal·keytab 모드 | keytab 내용을 출력 |
| Pod 홈 접근 실패 | Pod UID/GID, ccache, rpc.gssd, 머신 ticket, mount | NAS를 바로 재시작 |
| NFS D-state | stack·kernel log·NFS 응답·네트워크 | 반복 mount/unmount 또는 service restart |

머신 ccache의 principal이 잘못됐거나 ticket이 만료된 경우에만, 정확한 현재 노드
머신 principal을 확인한 후 별도 승인 절차에 따라 복구한다. 사용자 principal이나
다른 Realm을 지정하지 않는다.

## 5. 노드 추가·변경

신규 AD DC와 FARM 실행 노드는 먼저 제한된 관리 채널, 시간 동기화, rpc.gssd와
FARM 홈 mount를 준비한다. 한 대의 canary에서 시험 사용자로 keytab 권한, timer,
ccache, TGT, NFS 읽기·쓰기를 검증한 뒤 노드 목록에 추가한다.

공통 refresh 스크립트·systemd 템플릿의 변경은 사용자 배포 중에도 다시 설치될 수
있다. canary 검증 뒤 기존 노드의 버전·소유권을 비교하고 확대한다.
