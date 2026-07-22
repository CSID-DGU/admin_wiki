# Kerberos/NFS 운영

이 문서는 현재 Docker 기반 FARM/LAB 환경의 일상 점검과 장애 대응 절차를
설명한다. 환경별 endpoint와 적용 상태는 반드시 canonical runbook에서 다시
확인한다.

## 1. 운영 원칙

1. 관측과 변경을 분리한다. 5분 keytab checker는 자동 repair/rotation을 하지 않는다.
2. 사용자 keytab은 host root-only로 두고 container에는 ccache만 전달한다.
3. 컨테이너를 시작하기 전에 refresh timer와 최초 ccache 발급을 완료한다.
4. mount source는 FQDN을 사용하고 IP는 `addr=` transport 값으로만 사용한다.
5. `findmnt`, `klist`, `kvno`, readiness 순서로 원인을 좁힌 뒤 service restart나
   remount를 마지막 수단으로 사용한다.
6. UID/GID 불일치는 AD·DB·NFS 숫자를 비교한 뒤 고친다. 먼저 `chown`하지 않는다.

## 2. Kerberos container 생성 (추후 자동화 시스템으로 대체될 예정)

대표 CLI 형태는 다음과 같다. 실제 image/version, 사용자 정보와 대상 server는
요청에 맞게 지정한다.

```bash
cd /home/jy/server_manage/user-lifecycle/script

python3 -B -m uid_manager.cli create-container \
  --server-id FARM8 \
  --name "사용자 이름" \
  --username <username> \
  --group <groupname> \
  --image <image> \
  --version <version> \
  --created-by <operator> \
  --email <email> \
  --phone <phone> \
  --enable-kerberos
```

먼저 `--dry-run`으로 UID/GID, target host, mount source, container command를
확인하는 것을 권장한다. 기존 사용자 password/key를 의도적으로 바꿀 때만
`--rotate-kerberos-keytab`을 추가한다. 이 옵션은 AD user password와 KVNO를
바꾸므로 단순 재배포 옵션으로 사용하지 않는다.

생성 transaction은 다음 조건을 모두 통과한 후 Docker/DB를 확정해야 한다.

- AD `uidNumber/gidNumber`가 선택한 DB UID/GID와 일치한다.
- target host keytab이 `root:root 0400`이다.
- ccache timer가 enabled/active이고 최초 ccache가 유효하다.
- NAS/storage home의 numeric owner가 기대한 UID/GID다.
- 새로 만든 사용자 credential로 host NFS write/delete가 성공한다.
- Docker에는 ccache directory와 읽기 전용 `krb5.conf`만 전달된다.

구현은 [create_container.py](https://github.com/CSID-DGU/admin_infra_server/blob/main/user-lifecycle/script/uid_manager/services/create_container.py)와
[Kerberos command builder](https://github.com/CSID-DGU/admin_infra_server/blob/main/user-lifecycle/script/uid_manager/kerberos/commands.py)에서 확인한다.

## 3. Host keytab과 ccache 확인

### 파일 권한

```bash
sudo stat -c '%U:%G %a %n' \
  /etc/decs-krb/keytabs/<username>.keytab \
  /etc/decs-krb/refresh.d/<username>.env

sudo stat -c '%U:%G %a %n' /run/user/<uid> /run/user/<uid>/krb5cc
```

기대값은 다음과 같다.

```text
keytab:     root:root 400
refresh env: root:root 600
ccache dir: <uid>:<gid> 700
ccache:     <uid>:<gid> 600
```

### timer와 ticket

```bash
systemctl list-timers 'decs-krb-refresh@*.timer'
systemctl status 'decs-krb-refresh@<username>.timer' --no-pager
sudo systemctl start 'decs-krb-refresh@<username>.service'
sudo journalctl -u 'decs-krb-refresh@<username>.service' -n 100 --no-pager

sudo -u '#<uid>' env KRB5CCNAME=FILE:/run/user/<uid>/krb5cc \
  klist -c FILE:/run/user/<uid>/krb5cc
```

컨테이너 생성 때 timer unit을 설치·enable/start하고, 기존 ccache가 유효하지
않으면 oneshot service를 즉시 실행하도록 구현되어 있다. timer만 존재하고
최초 ccache가 없는 상태에서 컨테이너를 먼저 시작하면 Kerberized home 접근이
실패할 수 있다.

AD group을 변경했다면 renew만 기다리지 말고 fresh ticket을 발급한다.

```bash
sudo rm -f /run/user/<uid>/krb5cc
sudo systemctl start 'decs-krb-refresh@<username>.service'
sudo -u '#<uid>' klist -c FILE:/run/user/<uid>/krb5cc
```

## 4. 컨테이너 credential 확인

```bash
docker inspect <container> --format '{{range .Config.Env}}{{println .}}{{end}}' |
  grep -E '^(KRB5CCNAME|DECS_KRB5_PRINCIPAL|DECS_KERBEROS_ENABLED)='

docker exec --user <username> <container> \
  sh -lc 'klist -c "$KRB5CCNAME" && touch ~/.__krb_test && rm ~/.__krb_test'
```

다음은 잘못된 상태다.

- container mount나 image 안에 `*.keytab`이 있음
- `KRB5CCNAME`이 host와 공유되지 않은 임시 경로를 가리킴
- container UID가 DB/AD UID와 다름
- Kerberos mode인데 unrestricted sudo와 광범위한 host mount를 함께 허용함

현재 저장소에는 Kubernetes Pod용 credential controller가 구현되어 있지 않다.
Pod 운영을 추가한다면 Pod 생성 시 “어느 node에서 누가 keytab을 보관하고 ccache를
갱신할지”부터 구현해야 하며, Docker용 systemd timer 명령을 그대로 복사해
완료로 간주하면 안 된다.

## 5. NFS mount source 확인

환경마다 source, NFS version과 service principal이 다르다.

FARM의 올바른 형태는 다음과 같다.

```fstab
nas.farm.decs.internal:/volume1/share /home/tako8/share nfs4 defaults,vers=4.0,rsize=1048576,wsize=1048576,sec=krb5,proto=tcp,hard,timeo=600,retrans=2,addr=100.100.100.120,_netdev,exec,nouser 0 0
```

LAB의 올바른 형태는 다음과 같다. 실제 fstab에는 `rpc-gssd`와
`decs-kerberos-nfs-ready.service`에 대한 `x-systemd.requires/after` option도
playbook이 함께 추가한다.

```fstab
lab-storage.lab.decs.internal:/294t/dcloud/share /home/tako9/share nfs4 defaults,vers=4.1,sec=krb5,proto=tcp,hard,_netdev,exec,nouser 0 0
```

핵심은 source가 각 realm의 NFS service principal과 일치하는 FQDN이라는 점이다.

```text
FARM 올바름: nas.farm.decs.internal:/volume1/share
FARM 잘못됨: 100.100.100.120:/volume1/share 또는 192.168.2.30:/volume1/share
FARM 정상:   runtime option의 addr=100.100.100.120

LAB 올바름: lab-storage.lab.decs.internal:/294t/dcloud/share
LAB 잘못됨: 100.100.100.100:/294t/dcloud/share 또는 192.168.1.20:/294t/dcloud/share
LAB 정상:   FQDN을 해석한 실제 transport 주소 100.100.100.100
```

IP source를 쓰면 `nfs/nas.farm.decs.internal@FARM.DECS.INTERNAL` service
principal 또는 `nfs/lab-storage.lab.decs.internal@LAB.DECS.INTERNAL`과 이름이
맞지 않는다. `192.168.2.30`과 `192.168.1.20`은 관리 SSH 주소이며 운영 NFS data
path가 아니다.

점검 명령:

```bash
MOUNT_TARGET=/home/tako9/share
STORAGE_FQDN=lab-storage.lab.decs.internal

findmnt -T "$MOUNT_TARGET" -o TARGET,SOURCE,FSTYPE,OPTIONS
nfsstat -m | sed -n "\\|$MOUNT_TARGET|,+4p"
getent hosts "$STORAGE_FQDN"
```

FARM host에서는 값을 `/home/tako<번호>/share`와 `nas.farm.decs.internal`로
바꾼다. `findmnt`의 `vers=4.0`은 FARM, `vers=4.1`은 LAB이어야 하고 두 환경 모두
`sec=krb5`여야 한다.

fstab 설정은 [server-state playbook](https://github.com/CSID-DGU/admin_infra_server/blob/main/server-state/ansible_playbook/kerberos_nfs_client_recovery.yml)에서
관리한다. 이미 mount된 legacy superblock은 유지보수 창에 clean unmount/remount한다.
NFS caller가 D-state이면 강제 unmount를 반복하지 말고 포렌식 보존과 host reboot
판단으로 전환한다.

## 6. Machine credential과 NFS service ticket 확인

계산 호스트의 root mount에는 host machine keytab과 `rpc.gssd`가 필요하다.
realm과 NFS principal을 host 이름에 맞춰 선택한다.

```bash
short=$(hostname -s | tr '[:lower:]' '[:upper:]')

case "$short" in
  FARM*) KRB_REALM=FARM.DECS.INTERNAL
         KRB_NFS_PRINCIPAL=nfs/nas.farm.decs.internal@FARM.DECS.INTERNAL ;;
  LAB*)  KRB_REALM=LAB.DECS.INTERNAL
         KRB_NFS_PRINCIPAL=nfs/lab-storage.lab.decs.internal@LAB.DECS.INTERNAL ;;
  *)     printf '지원하지 않는 host: %s\n' "$short" >&2; exit 1 ;;
esac
KRB_MACHINE_PRINCIPAL="${short}\$@${KRB_REALM}"

sudo klist -kte /etc/krb5.keytab
sudo KRB5CCNAME=FILE:/run/decs-host-check.ccache \
  kinit -k -t /etc/krb5.keytab "$KRB_MACHINE_PRINCIPAL"
sudo KRB5CCNAME=FILE:/run/decs-host-check.ccache \
  kvno "$KRB_NFS_PRINCIPAL"
sudo rm -f /run/decs-host-check.ccache

systemctl status rpc-gssd --no-pager
systemctl cat rpc-gssd
pgrep -a rpc.gssd
```

`rpc.gssd`를 `-n`으로 시작하지 않는다. root mount는 host machine credential을
사용해야 하며, `-n`은 UID 0 사용자 credential을 찾게 하여 ticket이 없을 때
mount를 잃게 만들 수 있다.

## 7. Synology NAS와 Linux storage 운영 차이

FARM의 Synology NAS와 LAB의 Linux storage는 같은 NFS/Kerberos 개념을 사용하지만
설정을 관리하는 방식, service 이름과 keytab lifecycle이 다르다. client에서
확인하는 `findmnt`, `klist`, `kvno` 절차는 비슷해도 server 변경 명령은 서로
바꿔 실행하면 안 된다.

### 7.1 운영 경계 비교

| 항목 | FARM Synology NAS | LAB Linux storage |
| --- | --- | --- |
| 관리 접속 | `jy@192.168.2.30:6954` | `jy@192.168.1.20:6953` |
| AD join 도구 | DSM UI 또는 `/usr/syno/sbin/synowin` | 표준 Samba `net ads join` |
| Samba/winbind | Synology SMB package 경로와 `pkg-synosamba-*` unit | `/etc/samba/smb.conf`, 표준 `winbind.service` |
| RFC2307 NSS | `files winbind syno` 순서와 Synology idmap 설정을 함께 확인 | `files systemd winbind`와 Samba `idmap config LAB : backend = ad` 확인 |
| NFS export root | `/volume1/share` | `/294t/dcloud/share`; PoC는 별도 `test_krb` export |
| production export | storage IP별 `root_squash`, `sec=krb5:krb5i:krb5p`; Synology `anonuid/anongid`, `insecure` option 포함 | Linux `/etc/exports`에서 `root_squash`, `sec=krb5`, `no_subtree_check`를 명시 |
| NFS service | Synology `/usr/sbin/svcgssd`와 `/usr/sbin/idmapd` | `nfs-server`와 `rpc-svcgssd` 또는 배포판의 socket-activated GSS service |
| NFS keytab | `/etc/nfs/krb5.keytab`이 ticket 검증 기준; `/etc/krb5.keytab`도 동기화 검사 | `/etc/krb5.keytab` 한 경로 |
| NFS SPN 등록 계정 | 전용 user `svc-nfs-farm`; `NAS$`와 분리 | computer account `LAB-STORAGE$` |
| 추가 acceptor | 같은 keytab의 AILAB `nfs/nas.ailab.dgu@AILAB.DGU`를 반드시 보존 | 현재 없음 |
| 운영 NFS version | v4.0 | v4.1 |
| keytab checker | `--profile farm`, 5분 user timer 운영 | `--profile lab`; profile은 준비됐지만 PoC 단계에서는 timer를 기본 활성화하지 않음 |

Synology에서 `getent`, `id` 또는 `wbinfo`가 DECS UID/GID 대신 `96470xxx` 같은
내부 ID를 반환하면 RFC2307 경로가 정상인 상태가 아니다. 이때 symbolic
`chown -R 'FARM\user':'FARM\group'`을 실행하면 잘못 해석된 숫자가 filesystem에
저장된다. 먼저 DB·AD와 NAS의 numeric UID/GID가 일치하는지 확인하고, ownership
복구도 검증된 숫자로 수행한다.

FARM NAS에는 관리·호환성 목적으로 남은 `192.168.2.0/24 sec=sys,no_root_squash`
export가 있을 수 있다. 이것은 production Kerberos data path가 아니며 FARM host나
container가 이 `sec=sys` export를 사용하도록 변경하면 안 된다.

### 7.2 읽기 전용 점검

FARM Synology NAS에서는 vendor 경로와 service 이름을 사용한다.

```bash
ssh -p 6954 jy@192.168.2.30

/usr/syno/sbin/synowin -getWorkgroup
SMB=/usr/local/packages/@appstore/SMBService/usr/bin
sudo "$SMB/net" ads testjoin
sudo "$SMB/wbinfo" --online-status

sudo klist -kte /etc/nfs/krb5.keytab
sudo klist -kte /etc/krb5.keytab
sudo exportfs -v | sed -n '/\/volume1\/share/,+8p'
ps -ef | grep -E 'svcgssd|idmapd' | grep -v grep
```

LAB Linux storage에서는 표준 Samba/NFS systemd unit과 keytab을 확인한다.

```bash
ssh -p 6953 jy@192.168.1.20

sudo net ads testjoin
wbinfo --online-status
getent passwd '<username>'

sudo klist -kte /etc/krb5.keytab \
  | grep -F 'nfs/lab-storage.lab.decs.internal@LAB.DECS.INTERNAL'
systemctl is-active winbind nfs-server
systemctl --no-pager --full status rpc-svcgssd.service 2>/dev/null || true
sudo exportfs -v | sed -n '/\/294t\/dcloud\/share/,+8p'
```

LAB 배포판에서는 `rpc-svcgssd`가 독립 unit이 아니라 socket 또는 `nfs-server`의
일부로 관리될 수 있다. unit 이름 하나만으로 실패를 판정하지 말고 process,
service keytab과 실제 `kvno`/canary 결과를 함께 본다.

### 7.3 변경 작업에서 지킬 차이

- Synology 설정을 바꾸기 전에는 DSM/Samba/NFS 설정과 두 keytab을 먼저
  backup한다. DSM 또는 SMB package가 관리하는 파일·unit을 일반 Ubuntu와 같다고
  가정하지 않는다.
- FARM keytab repair는 AILAB principal과 이전 FARM KVNO를 보존하는 전용
  `repair-farm-nas-nfs-keytab.sh`을 사용한다. `svcgssd`를 FARM principal 하나로
  제한하는 `-p`나 nameless acceptor `-n`으로 시작하지 않는다.
- LAB storage는 표준 Samba join, `/etc/krb5.keytab`, `nfs-server`/`rpc-svcgssd`와
  Ansible desired state를 기준으로 한다. FARM repair/rotation script를 LAB에
  실행하지 않는다.
- 두 환경 모두 identity/export 변경 후 `exportfs -ra`와 필요한 NFS/RPC cache
  flush를 수행할 수 있지만, 먼저 활성 client와 D-state를 확인하고 유지보수
  시간에만 실행한다.
- Synology 관리 IP와 LAB storage 관리 IP는 NFS source가 아니다. 변경 후 client
  `findmnt`에서 각각 `nas.farm.decs.internal`과
  `lab-storage.lab.decs.internal`이 유지되는지 확인한다.

환경별 keytab 상태는 같은 checker를 profile만 바꿔 읽기 전용으로 확인한다.

```bash
cd /home/jy/server_manage/monitoring
health-checks/kerberos-nfs-keytab/script/check-nfs-keytab.sh --profile farm
health-checks/kerberos-nfs-keytab/script/check-nfs-keytab.sh --profile lab
```

server-side 전체 설정 절차는
[FARM canonical runbook](https://github.com/CSID-DGU/admin_infra_server/blob/main/kerberos-nfs/docs/farm.md)과
[LAB canonical runbook](https://github.com/CSID-DGU/admin_infra_server/blob/main/kerberos-nfs/docs/lab.md)을
각각 따른다.

## 8. FARM NAS service account와 KVNO 운영

### 현재 정책

- NFS SPN 등록 계정: `svc-nfs-farm`
- `NAS$`: domain membership용 `HOST/*`, `RestrictedKrbHost/*`만 유지
- 자동 password expiration/rotation: 없음
- keytab drift 관측: 5분마다 읽기 전용
- repair/rotation: 관리자 명시 실행만 허용

과거 `NAS$` machine password의 주기적 변경으로 KVNO와 NAS NFS keytab이
어긋났기 때문에 전용 service account를 만들었다. 운영 문서에는 “KVNO가
주기적으로 바뀌어서 매번 새 계정을 만든다”가 아니라, **한 번 만든 전용
계정으로 자동 machine-account rotation에서 NFS SPN을 분리했다**고 기록한다.

### 읽기 전용 점검

```bash
cd /home/jy/server_manage/monitoring
health-checks/kerberos-nfs-keytab/script/check-nfs-keytab.sh --profile farm

systemctl --user status check-nfs-keytab@farm.timer --no-pager
systemctl --user list-timers 'check-nfs-keytab@farm.timer'
```

checker가 확인하는 항목:

- AD `svc-nfs-farm`의 현재 `msDS-KeyVersionNumber`
- NAS `/etc/krb5.keytab`, `/etc/nfs/krb5.keytab`에 현재 KVNO와 NFS principal 존재
- 공유 keytab에 AILAB acceptor가 보존되어 있는지
- 실제 `kvno -k` service-ticket 복호화 성공 여부
- `svcgssd` 실행 여부와 잘못된 `-p` 제한 여부

코드는 [공용 checker](https://github.com/CSID-DGU/admin_infra_server/blob/main/monitoring/health-checks/kerberos-nfs-keytab/script/check-nfs-keytab.sh),
profile 값은 [FARM config](https://github.com/CSID-DGU/admin_infra_server/blob/main/monitoring/health-checks/kerberos-nfs-keytab/config/farm.env)에서 확인한다.

### Drift 수동 복구

```bash
cd /home/jy/server_manage/kerberos-nfs

./script/keytab/repair-farm-nas-nfs-keytab.sh --check
./script/keytab/repair-farm-nas-nfs-keytab.sh --repair
```

`--repair`는 새 key를 export·검증하고 기존 AILAB principal과 이전 FARM KVNO를
보존하면서 NAS keytab을 원자 교체한다. 필요하면 `svcgssd`를 `-p` 없이
재시작하므로 활성 client 영향과 되돌릴 backup을 먼저 확인한다. 구현은
[repair script](https://github.com/CSID-DGU/admin_infra_server/blob/main/kerberos-nfs/script/keytab/repair-farm-nas-nfs-keytab.sh)에 있다.

### 계획된 rotation

```bash
./script/keytab/rotate-farm-nfs-service-key.sh --check

# 유지보수 창, AD replication, NAS/client 상태를 확인한 뒤에만 실행
./script/keytab/rotate-farm-nfs-service-key.sh --rotate --apply
```

rotation은 random password 설정, AD KVNO 변경, 새 key export, NAS keytab merge,
`svcgssd` 반영, replica sync를 한 작업으로 수행한다. 이전 KVNO는 설정된 24시간
ticket lifetime보다 긴 최소 48시간 보존한다. 구현은
[rotation script](https://github.com/CSID-DGU/admin_infra_server/blob/main/kerberos-nfs/script/keytab/rotate-farm-nfs-service-key.sh)에 있다.

## 9. 모니터링에서 확인할 항목

| 무엇을 확인하는가 | 대표 상태/지표 | 코드 |
| --- | --- | --- |
| AD KVNO와 NAS keytab 일치 | profile status JSON, checker exit 0/1/2 | [keytab health check](https://github.com/CSID-DGU/admin_infra_server/tree/main/monitoring/health-checks/kerberos-nfs-keytab) |
| host keytab→kinit→kvno→rpc-gssd | `cluster_monitor_nfs_gss_ready`와 stage | [readiness script](https://github.com/CSID-DGU/admin_infra_server/blob/main/monitoring/prometheus/exporters/cluster-monitor-exporter/script/decs_nfs_gss_ready.sh) |
| 실제 service path | `cluster_monitor_nfs_gss_canary_success` | [canary probe](https://github.com/CSID-DGU/admin_infra_server/blob/main/monitoring/prometheus/exporters/cluster-monitor-exporter/script/decs_nfs_gss_canary_probe.sh) |
| 운영 mount | `cluster_monitor_host_mount_up`, `..._responsive`, probe seconds | [cluster collector](https://github.com/CSID-DGU/admin_infra_server/blob/main/monitoring/prometheus/exporters/cluster-monitor-exporter/cmd/cluster-monitor-exporter/main.go) |
| missing mount 복구 | `cluster_monitor_nfs_gss_recovery_*` | [guarded recovery](https://github.com/CSID-DGU/admin_infra_server/blob/main/monitoring/prometheus/exporters/cluster-monitor-exporter/script/decs_nfs_gss_mount_recovery.sh) |
| D-state/lease/hung task | `cluster_monitor_host_dstate_*`, `cluster_monitor_nfs_*` | [NFS forensics collector](https://github.com/CSID-DGU/admin_infra_server/blob/main/monitoring/prometheus/exporters/cluster-monitor-exporter/cmd/cluster-monitor-exporter/nfs_forensics.go) |
| 경보 조건 | `ClusterMonitorNFSGSS*`, `ClusterMonitorNFS*`, mount alerts | [FARM Prometheus values](https://github.com/CSID-DGU/admin_infra_server/blob/main/monitoring/prometheus/config/prometheus-farm-values.yaml) |

상세한 Prometheus/Grafana 운영은 [monitoring 운영 문서](../monitoring/operations.md)를
참고한다.

## 10. 장애 진단 순서

### 사용자 한 명만 실패

1. DB UID/GID와 AD `uidNumber/gidNumber`를 비교한다.
2. user keytab permission과 principal을 확인한다.
3. refresh service journal과 ccache `klist`를 확인한다.
4. 동일 UID로 host NFS write를 시험한다.
5. container UID, `KRB5CCNAME`, ccache bind mount를 확인한다.
6. AD group 변경 직후라면 fresh ticket을 발급한다.

### 여러 host/user가 동시에 실패

1. `getent hosts <storage-fqdn>`과 storage RPC 연결을 확인한다.
2. keytab checker에서 AD KVNO/NAS keytab drift를 확인한다.
3. `kvno nfs/<storage-fqdn>@<REALM>`을 확인한다.
4. NAS `svcgssd`와 service keytab을 확인한다.
5. mount source가 IP나 관리망 주소로 바뀌지 않았는지 확인한다.
6. AD replication 실패 시 실제 쓰기 대상 DC와 NAS가 조회하는 DC를 확인한다.

### Mount가 없거나 응답하지 않음

1. `findmnt`로 존재/source/security를 확인한다.
2. readiness 상태에서 처음 실패한 stage를 확인한다.
3. D-state, lease expiry, hung-task와 forensics snapshot을 확인한다.
4. mount가 **없는 경우에만** guarded recovery timer 상태를 확인한다.
5. 이미 healthy한 mount를 자동/수동으로 재마운트하지 않는다.
6. D-state caller가 남아 있으면 forced unmount 반복 대신 증거 보존 후 reboot를
   검토한다.

## 11. 변경 전후 체크리스트

### 변경 전

- 대상 realm, DC, storage FQDN과 NFS principal 확인
- 활성 client와 유지보수 창 확인
- AD replication health 확인
- NAS keytab backup과 AILAB principal 확인
- 현재 `findmnt`, `klist`, checker status 보존

### 변경 후

- AD current KVNO와 NAS keytab KVNO 일치
- `kvno -k` 복호화 성공
- `svcgssd`가 `-p` 없이 실행
- host readiness와 실제 사용자 NFS write 성공
- refresh timer enabled/active, ccache 유효
- Prometheus target/rules와 Grafana dashboard 정상
- 이전 KVNO를 최소 48시간 보존

## 12. 문서에 추가로 유지할 내용

설계와 운영이 다시 섞이지 않도록 다음 내용을 계속 분리해 기록한다.

- 설계 문서: trust boundary, principal naming, UID/GID invariant, ticket lifetime,
  FQDN 선택 근거, failure domain, Docker와 향후 Pod의 credential 모델
- 운영 문서: 현재 endpoint/KVNO가 아니라 확인 명령, timer/SLO, rotation 승인
  조건, rollback, incident 진단 순서, 마지막 검증 날짜
- canonical runbook: 실제 host별 mount, 현재 적용 상태, 예외와 잔여 위험
- 실험 결과: 당시 kernel/NFS/security flavor와 재현 조건; 현재 default와 분리

keytab, password, local environment, incident 개인정보와 packet capture는 위키와
Git에 넣지 않는다.
