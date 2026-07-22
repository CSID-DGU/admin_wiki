# NFSv4.1 session slot 고착 해결 및 운영 적용

> 상태: 2026-07-21~22 LAB storage의 OS와 kernel을 교체하고 Kerberos/NFS
> 구성을 복원했다. 2026-07-23 LAB8 운영 mount에서 `rpc.idmapd`를 15초
> 지연한 직접 시험에서도 session slot이 영구 고착되지 않았다.

이 문서는 [NFSv4.1 session slot 고착](nfs-v41-session-slot-stuck.md)에서 확인한
server-side kernel 문제를 실제 LAB storage에서 어떻게 제거하고 운영 구성을
복원했는지 기록한다. 원인 재현 과정과 fault-injection 명령은 기존 문서에 두고,
여기에는 해결 조치와 안전한 사후 검증만 정리한다.

## 1. 해결 결론

이 장애의 근본 조치는 **NFS server인 `lab-storage`의 kernel을 idmap deferral
수정이 포함된 kernel 계열로 교체하는 것**이다. client 재부팅, NFS remount 또는
`rpc-gssd` 재시작은 이미 고착된 상태를 지울 수는 있지만 server-side slot leak
경로를 없애지 못한다.

| 항목 | 변경 전 | 변경 후 |
| --- | --- | --- |
| 작업 서버 | `lab-storage.lab.decs.internal` | 동일 |
| OS | CentOS Linux 7 | CentOS Stream 10 |
| kernel | `3.10.0-862.el7.x86_64` | `6.12.0-250.el10.x86_64` |
| 데이터 | `/294t` XFS | 기존 `/dev/sda1`을 포맷하지 않고 `/294t`에 재연결 |
| AD/KDC | LAB2 Samba AD | 동일, storage keytab은 LAB2에서 재생성 |
| NFS 보안 | Kerberos NFS | SSSD·gssproxy·NFS export를 복원 |

격리 VM 비교에서는 upstream `6.12.74`까지 slot 고착이 발생했고 `6.12.75`에서
자동 복구했다. CentOS Stream 10의 signed kernel `6.12.0-248.el10`도 같은 시험을
통과했다. 현재 운영 kernel `6.12.0-250.el10`은 그보다 뒤에 설치한 같은 배포판
kernel이다.

여기서 `250.el10`은 upstream Linux `6.12.250`을 뜻하지 않고 CentOS/RHEL 계열의
package release 번호다. 초기 운영 적용은 격리 VM 회귀 결과와 교체 후 실제
서비스 상태를 근거로 판정했고, 2026-07-23에는 승인된 15초 지연 시험을 LAB8
운영 mount에서 한 번 추가해 현재 kernel에서도 영구 slot 고착이 없음을 확인했다.

## 2. 서버별 역할

| 서버 | 이번 조치에서의 역할 |
| --- | --- |
| `lab-storage.lab.decs.internal` (`100.100.100.100`) | kernel 문제를 제거한 NFS server. OS, network, data mount, SSSD, keytab, gssproxy와 export를 복원한 대상 |
| LAB2 / `100.100.100.102` | 운영 Samba AD DC, DNS/KDC. storage machine account와 NFS service principal의 원본 |
| LAB1~LAB10 | NFS client. 각 서버의 기존 `/etc/fstab`으로 `/home/takoN/share`를 다시 mount |
| LAB8 host | `/home/tako8/share` 운영 mount에서 15초 idmap 지연을 직접 검증한 client |
| LAB8의 격리 VM | kernel matrix와 장시간 지연 회귀 시험 전용 |

keytab은 예전 파일을 backup해서 되돌리지 않았다. LAB2 AD에 등록된 storage
machine account와 SPN을 기준으로 새 keytab을 만든 뒤 `lab-storage`의
`/etc/krb5.keytab`에 설치했다. 따라서 keytab 생성 작업은 LAB2에서, 설치와
검증은 `lab-storage`에서 수행한다.

## 3. 실제 적용 내용

### 3.1 `lab-storage`: OS와 kernel 교체

2026-07-21 22:38 KST에 `kernel-core-6.12.0-250.el10.x86_64`를 설치했고
22:49 KST부터 이 kernel로 부팅해 운영 중이다. hostname과 두 network를 다음
상태로 복원했다.

| 용도 | interface | 주소 |
| --- | --- | --- |
| 관리망 | `enp24s0f1` | `192.168.1.20/24` |
| storage망 | `enp101s0f0` | `100.100.100.100/24` |

hostname은 `lab-storage.lab.decs.internal`, timezone은 `Asia/Seoul`이며 NTP
동기화 상태는 `yes`다.

### 3.2 `lab-storage`: 기존 데이터 디스크 재연결

#### RAID volume이 처음 보이지 않은 이유

OS 설치 직후에는 294TB 데이터 RAID가 정상적인 `/dev/sda`로 나타나지 않았다.
이 장비의 controller는 다음 Areca ARC-1284다.

```text
17:00.0 RAID bus controller: Areca Technology Corp. ARC-12x4
Subsystem: Areca Technology Corp. ARC-1284 24 Port
PCI ID: 17d3:1214
```

CentOS Stream 10의 운영 kernel 설정을 확인하면 ARC-1284용 `arcmsr`가 빠져 있다.

```bash
grep CONFIG_SCSI_ARCMSR /boot/config-"$(uname -r)"
```

당시 결과는 다음과 같았다.

```text
# CONFIG_SCSI_ARCMSR is not set
```

먼저 `kernel-modules-extra`를 설치했지만 이 kernel용 `arcmsr.ko`는 들어 있지
않았다.

```bash
sudo dnf install -y kernel-modules-extra
modinfo arcmsr
```

ELRepo의 `kmod-arcmsr`도 확인했지만 EL10용 package가 없었다. 최종 해결은
ELRepo package 설치가 아니라 **현재 실행 kernel에 맞춰 `arcmsr`를 외부 module로
직접 빌드하는 것**이었다.

#### `arcmsr` 외부 module 빌드와 설치

2026-07-21에 실제로 설치한 build dependency는 다음과 같다. `kernel-devel`의
version은 반드시 module을 사용할 kernel과 정확히 같아야 한다.

```bash
KVER=$(uname -r)

sudo dnf install -y \
  "kernel-devel-$KVER" \
  gcc make elfutils-libelf-devel xz
```

Linux 6.12의
[`drivers/scsi/arcmsr`](https://github.com/torvalds/linux/tree/v6.12/drivers/scsi/arcmsr)에서
`Makefile`, `arcmsr.h`, `arcmsr_attr.c`, `arcmsr_hba.c`를 임시 build directory로
가져왔다. Stream 10 kernel에 backport된 API에 맞게 다음 호환 조정을 적용한 뒤
외부 module로 빌드했다.

- `slave_configure`를 `sdev_configure`와 `struct queue_limits` signature로 변경
- `bios_param`의 `struct block_device`를 `struct gendisk`로 변경
- `del_timer_sync()`를 `timer_delete_sync()`로 변경
- `from_timer()`를 `timer_container_of()`로 변경
- sysfs `bin_attribute` 인자를 `const`로 변경
- PCI device ID table을 `const`로 변경

실제 build 형태는 다음과 같다. upstream 6.12 source를 수정하지 않고 그대로
빌드하면 Stream 10 kernel API와 맞지 않으므로 위 호환 조정이 필요하다.

```bash
KVER=$(uname -r)
BUILD_DIR=$(mktemp -d /tmp/arcmsr-build.XXXXXX)

# BUILD_DIR에 호환 조정을 마친 다음 파일을 준비한다.
# Makefile  arcmsr.h  arcmsr_attr.c  arcmsr_hba.c

make -C "/usr/src/kernels/$KVER" \
  M="$BUILD_DIR" \
  CONFIG_SCSI_ARCMSR=m \
  modules

modinfo "$BUILD_DIR/arcmsr.ko"
```

먼저 `insmod`로 현재 boot에서 controller와 RAID volume이 정상적으로 인식되는지
확인했다.

```bash
sudo insmod "$BUILD_DIR/arcmsr.ko"

lspci -nnk -s 17:00.0
lsblk -e7 -o NAME,SIZE,TYPE,FSTYPE,UUID,MOUNTPOINTS,MODEL
```

`ARC-1284-VOL#000`과 partition UUID가 확인된 후 module을 영구 경로에 설치하고
boot 때 자동으로 load되도록 등록했다.

```bash
KVER=$(uname -r)

sudo install -D -m 0644 "$BUILD_DIR/arcmsr.ko" \
  "/lib/modules/$KVER/extra/arcmsr.ko"
sudo depmod -a "$KVER"

printf 'arcmsr\n' | sudo tee /etc/modules-load.d/arcmsr.conf >/dev/null
```

현재 설치된 module은 다음 상태다.

```text
path=/lib/modules/6.12.0-250.el10.x86_64/extra/arcmsr.ko
version=v1.51.00.14-20230915
sha256=8c78e3bb666abc49a17419904ab5911e0fed0c9cb885f0e2c18333b118d7865e
driver=arcmsr
volume=ARC-1284-VOL#000
```

이 module은 RPM 소유 파일이 아니며 서명되지 않은 외부 module이다. 현재 server는
Secure Boot가 disabled라 load됐고 kernel log에는 out-of-tree module taint가
기록된다.

> **kernel 업데이트 주의:** 새 kernel을 설치하면 그 version에 맞는
> `kernel-devel`로 `arcmsr.ko`를 다시 빌드해 새 kernel의
> `/lib/modules/<새-version>/extra/`에 설치하고 `depmod`를 실행해야 한다. 이를
> 준비하지 않고 새 kernel로 reboot하면 ARC-1284 volume이 나타나지 않아 `/294t`
> mount가 실패할 수 있다.

#### XFS mount 복원

driver load 후 RAID volume은 `/dev/sda`, 기존 XFS partition은 `/dev/sda1`로
나타났다. 데이터 디스크를 포맷하지 않고 다음 fstab 항목으로 다시 연결했다.

```fstab
UUID=2a417935-7537-4301-bbcf-5ab2ca836af5 /294t xfs defaults 1 2
```

2026-07-22 확인 결과는 `/dev/sda1` → `/294t`, XFS, `rw`다. 이 조치에서는
`/294t`를 다시 포맷하지 않았다.

```bash
lsblk -e7 -o NAME,SIZE,FSTYPE,UUID,MOUNTPOINTS,MODEL
findmnt -rn -o TARGET,SOURCE,FSTYPE,OPTIONS /294t
lspci -nnk -s 17:00.0
lsmod | grep '^arcmsr'
```

2026-07-22 이후 kernel log에는 일부 allocation group의 AGFL을 reset했고 block이
leak됐다는 XFS warning도 기록됐다. 이는 `arcmsr` load와 `/294t` mount 성공 여부와
별개인 filesystem metadata 점검 항목이다. 운영 export가 연결된 상태에서
`xfs_repair`를 실행하지 말고, 별도 유지보수 창에 NFS를 중단하고 `/294t`를
unmount한 뒤 offline 점검·복구해야 한다.

### 3.3 LAB2와 `lab-storage`: AD 설정과 SSSD·keytab 복원

#### LAB2: AD server와 storage principal 준비

LAB2는 `LAB.DECS.INTERNAL` realm의 Samba AD DC와 KDC 역할을 한다. storage망
주소는 `100.100.100.102`이며, `lab-storage`의 Kerberos 설정에서 KDC와 admin
server로 사용한다.

LAB2 AD에서 `lab-storage` machine account와 NFS service principal을 확인한 뒤
keytab을 새로 생성했다. OS 재설치 전 keytab을 backup해서 복원하지 않고 AD를
원본으로 재발급한 것이다.

```text
LAB-STORAGE$@LAB.DECS.INTERNAL
nfs/lab-storage.lab.decs.internal@LAB.DECS.INTERNAL
```

생성된 keytab의 machine principal과 NFS service principal KVNO는 모두 2였다.

#### `lab-storage`: SSSD와 keytab 설치·검증

`lab-storage`는 Kerberos realm을 `LAB.DECS.INTERNAL`, KDC와 admin server를
LAB2의 `100.100.100.102`로 설정했다. SSSD는 다음 정책으로 AD의 RFC2307
UID/GID를 그대로 조회한다.

```ini
[domain/lab.decs.internal]
ad_domain = lab.decs.internal
krb5_realm = LAB.DECS.INTERNAL
id_provider = ad
access_provider = permit
ldap_id_mapping = False
use_fully_qualified_names = False
```

LAB2에서 재생성한 keytab은 `lab-storage`의 `/etc/krb5.keytab`에 root 전용
권한으로 설치했다.

`lab-storage`에서 machine principal로 TGT를 받은 뒤 NFS principal을 keytab과
대조한 결과는 다음과 같다.

```text
nfs/lab-storage.lab.decs.internal@LAB.DECS.INTERNAL: kvno = 2, keytab entry valid
```

NFS service principal 자체를 client principal처럼 `kinit -k`하는 것은 이 구성의
검증 방법이 아니다. 아래 5.1절처럼 machine principal로 먼저 `kinit`한 뒤
`kvno -k`를 사용한다.

### 3.4 `lab-storage`: NFS service와 export 복원

`nfs-server`, `sssd`, `gssproxy`를 활성화하고 NFSv4 port `2049/tcp`와 관련
firewall service를 복원했다. 2026-07-22 확인 시 nfsd thread는 16개였고
`nfs-server`, `sssd`, `gssproxy`가 모두 active였다.

Kerberos 대상 export는 다음 상태다.

| 경로 | client | security flavor |
| --- | --- | --- |
| `/294t/dcloud/share` | `100.100.100.101`~`110` | `krb5p:krb5i:krb5` |
| `/294t/share/test-krb` | 지정 시험 client | `krb5p` |
| `/294t/health/nfs-gss-canary` | `100.100.100.101`~`110` | `krb5`, read-only |

기존 `sec=sys` 전용 경로는 별도 호환 export로 유지했다. Kerberos export가
정상이라는 이유로 기존 `sec=sys` export를 임의로 삭제하지 않는다.

### 3.5 LAB1~LAB10: 기존 fstab mount 복원

client별 mount 설정을 새로 생성하지 않고 각 서버에 이미 있던 `/etc/fstab`을
사용했다. mount가 없는 client에서만 `sudo mount -a`를 실행해
`/home/takoN/share`를 다시 연결했다.

2026-07-22 재점검에서 LAB1~LAB10 모두 다음 공통 상태를 보였다.

```text
source=lab-storage.lab.decs.internal:/294t/dcloud/share
fstype=nfs4
vers=4.1
hard
sec=krb5
addr=100.100.100.100
```

최초 병렬 점검 중 LAB7에서 짧은 D-state process 1개가 관측됐지만 즉시 수행한
local 상태 재확인에서는 사라졌다. 같은 시점에 NFS RPC task, transport pending,
ForeChannel waiter와 NFS D-state가 모두 0이었고 recovery 상태도 `healthy`였다.
이를 지속된 session slot 고착으로 판정하지 않았다.

### 3.6 LAB8 운영 mount: 15초 `rpc.idmapd` 지연 시험

> **과거 실행 기록:** 아래 내용은 안전장치를 준비한 뒤 한 번 수행한 운영 검증
> 결과다. 일반 점검 절차가 아니며 이 문서만 보고 운영 storage에서 반복 실행하지
> 않는다.

격리 VM 결과와 별도로 현재 운영 중인 storage kernel에서 같은 idmap 지연 경로가
영구 slot 고착을 만들지 않는지 직접 확인했다.

| 항목 | 시험 조건 |
| --- | --- |
| NFS client | LAB8 host의 운영 mount `/home/tako8/share` |
| mount | NFSv4.1, `sec=krb5`, `hard` |
| NFS server | `lab-storage.lab.decs.internal` |
| storage kernel | `6.12.0-250.el10.x86_64` |
| workload | 시험 container 내부에서 새 GID `424242`로 test file에 `chown` |
| idmap fault | storage의 `rpc.idmapd` 응답을 15초 지연 |
| 안전장치 | 15초 자동 재개 timer와 독립적인 30초 이중 자동 재개 timer |

지연 중에는 `chown`이 `rpc_wait_bit_killable` 경로에서 일시적으로 D-state에
들어갔다. 15초 자동 재개 후 worker는 더 이상 D-state에 남지 않고 종료됐다.
원래 `chown`의 application 결과는 `EINVAL`이었다.

```text
/bin/chown: changing group of '.../chown-target': Invalid argument
```

이 `EINVAL`은 “`chown` 성공”을 의미하지 않는다. 하지만 취약 kernel에서처럼
동일 요청이 `INUSE` slot에 계속 걸려 영구 D-state로 남지도 않았다. 이후 test
file 삭제 RPC가 성공했고 client reboot, unmount, NFS service restart 없이
정상 상태로 돌아왔다. 후속 확인 결과는 다음과 같았다.

| 판정 항목 | 결과 |
| --- | --- |
| 지속 NFS D-state | 0 |
| NFS RPC task | 0 |
| transport pending | 0 |
| ForeChannel waiter | 0 |
| `lease_expired` | 0 |
| 후속 NFS 작업 | test file 삭제 성공 |

따라서 이 시험은 **운영 kernel `6.12.0-250.el10`에서 15초 idmap 지연이 일시적인
RPC 대기를 만들 수는 있지만 NFSv4.1 session slot을 영구 고착시키지는 않았음**을
보여준다. 원래 operation의 application 결과와 session recovery 판정은 분리해야
한다.

## 4. 해결 판정 기준

이번 조치는 다음을 모두 만족해 운영 적용 완료로 판정했다.

1. `lab-storage`가 취약한 `3.10.0-862.el7`이 아니라
   `6.12.0-250.el10`으로 부팅돼 있다.
2. `/294t`가 기존 XFS data disk에서 `rw`로 mount돼 있다.
3. LAB2 machine principal의 TGT 발급과 NFS service principal의 keytab 검증이
   성공한다.
4. SSSD에서 AD 사용자의 RFC2307 UID/GID가 조회된다.
5. `nfs-server`, `sssd`, `gssproxy`가 active이고 NFSv4 port가 listen한다.
6. Kerberos NFS export가 LAB1~LAB10 storage망 주소에 열려 있다.
7. LAB1~LAB10에서 기존 fstab의 NFSv4.1 `sec=krb5` mount가 확인된다.
8. 지속되는 NFS D-state, RPC task, ForeChannel waiter 또는 lease expiry가 없다.
9. LAB8 운영 mount의 15초 idmap 지연 후에도 workload가 영구 D-state에 남지 않고
   후속 NFS RPC가 성공한다.

이 판정은 “2026-06-29 LAB5 장애의 최초 원인이 반드시 이 bug였다”는 뜻은
아니다. 당시 시작 시점의 storage trace가 없어 과거 장애 원인은 여전히 강한
후보로 남는다. 이번에 확정한 것은 구형 storage kernel에 실제 slot leak 경로가
있었고, 그 kernel을 운영에서 제거했다는 사실이다.

## 5. 안전한 사후 검증

### 5.1 작업 서버: `lab-storage`

```bash
hostname -f
uname -r
findmnt -rn -o TARGET,SOURCE,FSTYPE,OPTIONS /294t

systemctl is-active nfs-server sssd gssproxy
sudo exportfs -v
sudo ss -lnt | grep ':2049 '

DECS_KRB5CC_DIR=$(mktemp -d /tmp/decs-storage-kvno.XXXXXX)
DECS_KRB5CC="FILE:$DECS_KRB5CC_DIR/ccache"

sudo env KRB5CCNAME="$DECS_KRB5CC" \
  kinit -k -t /etc/krb5.keytab 'LAB-STORAGE$@LAB.DECS.INTERNAL'
sudo env KRB5CCNAME="$DECS_KRB5CC" \
  kvno -k /etc/krb5.keytab \
  nfs/lab-storage.lab.decs.internal@LAB.DECS.INTERNAL
sudo env KRB5CCNAME="$DECS_KRB5CC" kdestroy
rmdir "$DECS_KRB5CC_DIR"
```

기대 kernel은 `6.12.0-250.el10.x86_64` 이상이며, `kvno` 결과에는
`keytab entry valid`가 나와야 한다.

### 5.2 작업 서버: 각 NFS client LAB1~LAB10

아래의 `N`은 현재 접속한 LAB 서버 번호로 바꾼다. 이미 mount돼 있으면 반복
remount하지 않는다. mount가 없고 D-state도 없을 때만 기존 fstab으로 mount한다.

```bash
ps -e -o state=,pid=,etimes=,comm=,wchan:48=,args= \
  | awk '$1 ~ /^D/ {print}'

findmnt -T /home/takoN/share -o TARGET,SOURCE,FSTYPE,OPTIONS

# findmnt에 결과가 없고 D-state process도 없을 때만 실행
sudo mount -a
findmnt -T /home/takoN/share -o TARGET,SOURCE,FSTYPE,OPTIONS
```

container의 실제 사용자 권한까지 확인할 때는 container 안에서 해당 사용자로
실행한다. 다른 사용자의 홈이나 파일에 임의로 `chown`하지 않는다.

```bash
id
ls -al "$HOME/share" | sed -n '1,40p'

probe="$HOME/share/.nfs-post-upgrade-check.$(hostname -s).$$"
printf 'nfs post-upgrade check\n' >"$probe"
grep -Fx 'nfs post-upgrade check' "$probe"
ls -ln "$probe"
rm -f "$probe"
```

`ls -al`의 소유자·그룹이 `nobody`가 아니라 AD의 사용자·그룹 이름으로 보이고,
생성·읽기·삭제가 모두 성공해야 한다.

## 6. 같은 증상이 다시 보일 때

NFS `hard` mount의 process가 D-state에 들어가면 NFS 경로를 읽는 `find`, `du`,
`stat`, 반복 canary를 추가 실행하지 않는다. 새로운 NFS request와 D-state
process를 더 만들 수 있다.

1. 먼저 client에서 `uname -r`, D-state stack, `/proc/net/rpc/nfs`, forensics와
   recovery state를 local filesystem에서 수집한다.
2. `lab-storage`가 실수로 구형 kernel로 부팅되지 않았는지 확인한다.
3. 자동 remount, 강제 unmount, `rpc-gssd` 반복 restart를 중단한다.
4. storage의 network, nfsd, gssproxy와 session trace를 함께 확인한다.
5. 2026-07-23의 승인된 단일 시험을 일반 점검처럼 반복하지 않는다. 추가 재실험은
   LAB8의 격리 VM harness에서 수행한다.
6. client reboot는 고착된 client state를 지우는 복구 수단일 뿐 근본 해결로
   기록하지 않는다.

운영 mount를 `soft`로 바꾸는 것도 해결책으로 사용하지 않는다. timeout을
application error로 노출하고 data integrity 위험을 만들 수 있다.

## 7. 증거와 관련 문서

- [원인 재현과 kernel matrix](nfs-v41-session-slot-stuck.md)
- [실제 LAB8 재현 결과](https://github.com/CSID-DGU/admin_infra_server/blob/fd2cb554176089793ea43e0599001f76acc872a5/kerberos-nfs/labs/lab-kerberos-poc/results/2026-07-16-lab8-idmap-slot-repro/README.md)
- [격리 VM 회귀 시험 절차](https://github.com/CSID-DGU/admin_infra_server/blob/fd2cb554176089793ea43e0599001f76acc872a5/kerberos-nfs/labs/lab-kerberos-poc/vm-slot-regression/README.md)
- [LAB storage OS 재설치 후 복원 절차](https://github.com/CSID-DGU/admin_infra_server/blob/fd2cb554176089793ea43e0599001f76acc872a5/kerberos-nfs/docs/lab-storage-os-reinstall.md)
