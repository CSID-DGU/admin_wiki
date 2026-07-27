# FARM Kerberos 설정 가이드

> 대상: FARM AD DC, Synology NAS, FARM 계산 host, Kerberos container
> 운영 기준: NFSv4.0, `sec=krb5`, `hard,timeo=600,retrans=2`

[원본 PDF 다운로드](../../pdf/system/kerberos-nfs-farm-setup-guide.pdf){ .md-button .md-button--primary download="kerberos-nfs-farm-setup-guide.pdf" }
[GitHub에서 원본 Markdown 보기](https://github.com/CSID-DGU/admin_infra_server/blob/main/kerberos-nfs/docs/farm.md){ .md-button }

이 문서는 FARM Kerberos/NFS의 현재 구성을 한국어로 정리한 가이드다. 실제 endpoint와
최신 절차는 위 원본 Markdown을 우선한다. NAS keytab 교체, export 변경, legacy
mount remount는 유지보수 시간에만 수행한다.

## 1. 기준값과 원칙

| 항목 | 기준값 |
| --- | --- |
| realm / DNS domain | `FARM.DECS.INTERNAL` / `farm.decs.internal` |
| AD DC | `dc1.farm.decs.internal` (`100.100.100.102`), 보조 DC `100.100.100.106`, `100.100.100.107` |
| NAS 관리 / NFS 주소 | `192.168.2.30:6954` / `100.100.100.120` |
| NFS source | `nas.farm.decs.internal:/volume1/share` |
| NFS service principal | `nfs/nas.farm.decs.internal@FARM.DECS.INTERNAL` |

- NFS source에 관리 IP나 storage IP를 직접 쓰지 않는다. IP는 `addr=100.100.100.120`에만 쓴다.
- DB UID/GID = AD RFC2307 UID/GID = NAS owner = host owner = container UID/GID가 같아야 한다.
- 사용자 keytab은 host root만 읽고, container에는 ccache만 전달한다.
- NAS `svcgssd`와 host `rpc.gssd`에 임의의 `-n` 또는 `-p` option을 추가하지 않는다.

## 2. AD DC와 사용자·그룹

주 DC는 `farm2`다. AD replication을 확인하기 전까지 쓰기 작업은 `farm2`에서 한다.

```bash
sudo apt-get update
sudo apt-get install -y acl attr dnsutils krb5-user samba winbind
sudo samba-tool domain provision \
  --server-role=dc --use-rfc2307 --dns-backend=SAMBA_INTERNAL \
  --realm=FARM.DECS.INTERNAL --domain=FARM
sudo systemctl enable --now samba-ad-dc
sudo samba-tool drs showrepl
```

`/etc/krb5.conf`의 `FARM.DECS.INTERNAL` realm에는 세 DC를 모두 등록한다.

```ini
[realms]
  FARM.DECS.INTERNAL = {
    kdc = 100.100.100.102
    kdc = 100.100.100.106
    kdc = 100.100.100.107
    admin_server = 100.100.100.102
    default_domain = farm.decs.internal
  }
```

사용자와 group에는 DB 숫자를 RFC2307 속성으로 기록하고, primary group도 실제 사용할
private/shared group으로 바꾼다.

```bash
sudo samba-tool group add ASCP || true
sudo samba-tool group addunixattrs ASCP 10070 || true
sudo samba-tool user add zio_ascp '<initial-password>' || true
sudo samba-tool user addunixattrs zio_ascp 10073 10070 || true
sudo samba-tool group addmembers ASCP zio_ascp || true
sudo samba-tool user setprimarygroup zio_ascp ASCP
sudo samba-tool user show zio_ascp | \
  grep -E '^(sAMAccountName|uidNumber|gidNumber|primaryGroupID):'
```

`primaryGroupID`가 `Domain Users`(`513`)에 남아 있으면 새 파일이 의도하지 않은
group으로 만들어질 수 있다.

## 3. Synology NAS

### AD join과 RFC2307

DSM 또는 CLI로 NAS를 FARM AD에 join한다. 비밀번호는 command line이나 history에
남기지 않는다.

```bash
read -rsp 'AD Administrator password: ' AD_PASS; echo
sudo /usr/syno/sbin/synowin -joinDomain FARM Administrator "$AD_PASS" \
  -d 100.100.100.102 -i 100.100.100.102 -n FARM -f farm.decs.internal
unset AD_PASS
/usr/syno/sbin/synowin -getWorkgroup
```

NAS의 resolver, Kerberos, Samba에는 `farm2`, `farm6`, `farm7`을 모두 등록한다.
`/etc/samba/smb.conf`에는 다음 RFC2307 설정이 필요하다.

```ini
workgroup = FARM
realm = FARM.DECS.INTERNAL
security = ads
winbind:syno allow domains = FARM
idmap config FARM : backend = ad
idmap config FARM : schema_mode = rfc2307
idmap config FARM : range = 1000-299999
winbind nss info = rfc2307
winbind use default domain = yes
```

`/etc/nsswitch.conf`의 `passwd`, `group`, `shadow`, `initgroups`에는
`files winbind syno`를 사용한다. 적용 후 cache를 비우고 winbind를 재시작한다.

```bash
SMB=/usr/local/packages/@appstore/SMBService/usr/bin
sudo "$SMB/net" cache flush || true
sudo systemctl restart pkg-synosamba-winbindd.service
id 'FARM\zio_ascp'
sudo "$SMB/wbinfo" -i 'FARM\zio_ascp'
```

`id`가 `96470xxx` 같은 내부 ID를 반환하면 numeric ownership을 바꾸지 않는다.
먼저 RFC2307을 고친 뒤 DB/AD의 숫자로 ownership을 복구한다.

### NFS export와 keytab

`/volume1/share`에는 FARM storage IP별로 `root_squash`와
`sec=krb5:krb5i:krb5p`를 설정한다. client의 실제 mount는 `sec=krb5`다.

```bash
sudo exportfs -ra
sudo exportfs -v | sed -n '/\/volume1\/share/,+8p'
sudo klist -kte /etc/nfs/krb5.keytab | \
  grep -F 'nfs/nas.farm.decs.internal@FARM.DECS.INTERNAL'
ps -ef | grep -E 'svcgssd|idmapd' | grep -v grep
```

NAS service keytab은 `/etc/nfs/krb5.keytab`을 기준으로 한다. FARM과 AILAB
principal을 모두 보존해야 하므로 `svcgssd`를 FARM principal 하나로 제한하지 않는다.
keytab drift는 먼저 읽기 전용 checker로 점검한다.

```bash
/home/jy/server_manage/monitoring/health-checks/kerberos-nfs-keytab/script/check-nfs-keytab.sh --profile farm
```

## 4. FARM 계산 host

host kernel이 NFS client이므로 mount host마다 Kerberos와 RFC2307 NSS가 필요하다.

```bash
sudo apt-get install -y krb5-user nfs-common samba winbind libnss-winbind libpam-winbind
short=$(hostname -s | tr '[:lower:]' '[:upper:]')
sudo kinit -k -t /etc/krb5.keytab "${short}\$@FARM.DECS.INTERNAL"
klist
kdestroy
sudo systemctl enable --now rpc-gssd
pgrep -a rpc.gssd
```

`/etc/krb5.keytab`에는 host machine principal이 있어야 한다. `rpc.gssd`에는
`-n`이 없어야 한다. domain member host의 NSS는 다음과 같이 구성한다.

```text
# /etc/nsswitch.conf
passwd: files systemd winbind
group:  files systemd winbind
```

```bash
getent passwd 'FARM\zio_ascp'
getent group 'FARM\ASCP'
```

## 5. NFS mount

fstab은 `server-state` playbook에서 관리한다. FARM2 기준 entry는 다음과 같다.

```fstab
nas.farm.decs.internal:/volume1/share /home/tako2/share nfs4 defaults,vers=4.0,rsize=1048576,wsize=1048576,sec=krb5,proto=tcp,hard,timeo=600,retrans=2,addr=100.100.100.120,_netdev,exec,nouser 0 0
```

```bash
findmnt -T /home/tako2/share -o TARGET,SOURCE,FSTYPE,OPTIONS
nfsstat -m | sed -n '/\/home\/tako2\/share/,+4p'
```

결과에서 FQDN source, `vers=4.0`, `sec=krb5`, `addr=100.100.100.120`을
확인한다. Synology가 실제 `rsize/wsize`를 128 KiB로 협상할 수 있다. D-state가
있을 때 강제 unmount를 반복하지 않는다.

## 6. 사용자 keytab·ccache·container

```text
/etc/decs-krb/keytabs/<username>.keytab  root:root 0400
/etc/decs-krb/refresh.d/<username>.env   root:root 0600
/run/user/<uid>/krb5cc                   <uid>:<gid> 0600
```

```bash
DECS_KRB_PRINCIPAL=<username>@FARM.DECS.INTERNAL
DECS_KRB_KEYTAB=/etc/decs-krb/keytabs/<username>.keytab
DECS_KRB_CCACHE=FILE:/run/user/<uid>/krb5cc
DECS_KRB_UID=<uid>
DECS_KRB_GID=<gid>
```

```bash
sudo systemctl enable --now decs-krb-refresh@<username>.timer
sudo systemctl start decs-krb-refresh@<username>.service
sudo -u '#<uid>' klist -c FILE:/run/user/<uid>/krb5cc
```

container에는 keytab을 넣지 않는다. `/run/user/<uid>`와 읽기 전용
`/etc/krb5.conf`만 bind mount하고 `KRB5CCNAME=FILE:/run/user/<uid>/krb5cc`를
전달한다. AD group을 바꿨다면 ccache를 지운 뒤 fresh ticket을 발급한다.

## 7. 최종 점검

1. AD user/group의 UID/GID와 primary group을 확인한다.
2. NAS의 `id`, `wbinfo`, home numeric owner를 확인한다.
3. host의 `getent`, machine `kinit`, `rpc.gssd`, `findmnt`를 확인한다.
4. 사용자 ccache의 `klist`와 refresh timer를 확인한다.
5. container에서 `id`, `klist`, home 생성·읽기·삭제를 검증한다.

상세 장애 대응은 [Kerberos/NFS 운영](operations.md)과
[디버깅 로그](debugging/index.md)에서 확인한다.
