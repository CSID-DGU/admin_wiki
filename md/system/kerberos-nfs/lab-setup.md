# LAB Kerberos 설정 가이드

> 대상: LAB AD DC, Linux storage, 일반 LAB client, Kerberos container
> 기본 정책: NFSv4.1, `sec=krb5`; 먼저 `test_krb` export에서 검증

[원본 PDF 다운로드](../../pdf/system/kerberos-nfs-lab-setup-guide.pdf){ .md-button .md-button--primary download="kerberos-nfs-lab-setup-guide.pdf" }
[GitHub에서 원본 Markdown 보기](https://github.com/CSID-DGU/admin_infra_server/blob/main/kerberos-nfs/docs/lab.md){ .md-button }

이 문서는 LAB Kerberos/NFS를 구성하는 한국어 가이드다. 기존 운영 경로를 바로
바꾸지 말고 `test_krb`에서 identity, Kerberos, group, container write를 모두
검증한다. 실제 endpoint와 최신 절차는 위 원본 Markdown을 우선한다.

## 1. 기준값과 사전 확인

| 항목 | 기준값 |
| --- | --- |
| realm / DNS domain | `LAB.DECS.INTERNAL` / `lab.decs.internal` |
| AD DC | `dc1.lab.decs.internal` / `100.100.100.102` |
| storage 관리 / NFS 주소 | `192.168.1.20:6953` / `100.100.100.100` |
| service principal | `nfs/lab-storage.lab.decs.internal@LAB.DECS.INTERNAL` |
| 검증 export | `/294t/dcloud/share/test_krb` |
| client 예 | LAB8, `/mnt/lab-test-krb` |

- LAB에서는 Linux storage server가 AD domain member이자 NFS server다. `test_krb`
  directory 자체가 AD에 join하는 것은 아니다.
- 오래된 기록에는 `/294t/share/test-krb`도 있다. 변경 전에 `exportfs -v`와
  `findmnt`로 현재 path를 확인하고 한 path만 사용한다.
- 기본값은 `sec=krb5`다. 실험에서 보인 `sec=krb5p`는 새 mount의 기본값이 아니다.
- DB UID/GID = AD RFC2307 UID/GID = storage owner = client owner = container
  UID/GID가 같아야 한다.

## 2. LAB AD DC와 사용자·그룹

`lab2`에서 Samba AD DC를 RFC2307 모드로 구성한다. 같은 realm에 독립 MIT KDC와
Samba AD DC를 동시에 운영하지 않는다.

```bash
sudo apt-get update
sudo apt-get install -y acl attr dnsutils krb5-user samba winbind
sudo systemctl disable --now smbd nmbd winbind 2>/dev/null || true
sudo samba-tool domain provision \
  --server-role=dc --use-rfc2307 --dns-backend=SAMBA_INTERNAL \
  --realm=LAB.DECS.INTERNAL --domain=LAB \
  --host-name=dc1 --host-ip=100.100.100.102
sudo systemctl enable --now samba-ad-dc
```

`/etc/krb5.conf`에는 `LAB.DECS.INTERNAL`, KDC `100.100.100.102`,
`default_domain = lab.decs.internal`을 설정한다. Samba DNS에 DC와 storage record를
등록한다.

```bash
sudo samba-tool dns add 127.0.0.1 lab.decs.internal dc1 A 100.100.100.102 -U Administrator
sudo samba-tool dns add 127.0.0.1 lab.decs.internal lab-storage A 100.100.100.100 -U Administrator
host -t SRV _kerberos._udp.lab.decs.internal 100.100.100.102
```

사용자와 group에는 DB 숫자를 기록하고, primary group도 실제 사용할 group으로 설정한다.

```bash
sudo samba-tool group add test0524_gid || true
sudo samba-tool group addunixattrs test0524_gid 10051 || true
sudo samba-tool user add test0524 '<initial-password>' || true
sudo samba-tool user addunixattrs test0524 10051 10051 || true
sudo samba-tool group addmembers test0524_gid test0524 || true
sudo samba-tool user setprimarygroup test0524 test0524_gid
```

## 3. Linux storage 구성

storage에는 Kerberos, NFS server, Samba winbind을 설치한다.

```bash
sudo apt-get update
sudo apt-get install -y \
  krb5-user nfs-kernel-server nfs-common \
  samba winbind libnss-winbind libpam-winbind
```

`/etc/samba/smb.conf`는 LAB AD의 RFC2307 값을 사용한다.

```ini
[global]
  workgroup = LAB
  realm = LAB.DECS.INTERNAL
  security = ADS
  kerberos method = secrets and keytab
  winbind nss info = rfc2307
  winbind use default domain = yes
  idmap config * : backend = tdb
  idmap config * : range = 300000-399999
  idmap config LAB : backend = ad
  idmap config LAB : schema_mode = rfc2307
  idmap config LAB : range = 1000-299999
```

```text
# /etc/nsswitch.conf
passwd: files systemd winbind
group:  files systemd winbind
shadow: files
```

```bash
sudo net ads join -U Administrator
sudo systemctl enable --now winbind
getent passwd test0524
getent group test0524_gid
id test0524
```

NFS service principal을 keytab에 넣고 service를 시작한다.

```bash
sudo net ads keytab add nfs/lab-storage.lab.decs.internal -U Administrator
sudo klist -k /etc/krb5.keytab | grep nfs/lab-storage.lab.decs.internal
sudo systemctl enable --now nfs-server
sudo systemctl enable --now rpc-svcgssd 2>/dev/null || true
ps -ef | grep -E 'svcgssd|rpc.svcgssd' | grep -v grep
```

배포판에 따라 `rpc-svcgssd`는 socket-activated이거나 `nfs-server`가 관리할 수 있다.
unit 이름 하나만으로 실패를 판정하지 말고 process, keytab, 실제 GSS mount를 함께
확인한다.

## 4. `test_krb` export 생성

처음에는 test export만 연다.

```bash
sudo install -d -o root -g root -m 0755 /294t/dcloud/share/test_krb
sudo install -d -o root -g root -m 0755 /294t/dcloud/share/test_krb/user-share
```

`/etc/exports`에는 LAB8만 허용하는 entry를 추가한다.

```text
/294t/dcloud/share/test_krb \
  100.100.100.108(rw,async,no_subtree_check,crossmnt,root_squash,sec=krb5)
```

```bash
sudo exportfs -ra
sudo exportfs -v | grep -A2 '/294t/dcloud/share/test_krb'
sudo nfsidmap -c 2>/dev/null || true
```

identity 또는 export를 바꾼 뒤에는 storage와 client의 NFS idmap/RPC cache를 비운다.

## 5. 일반 LAB client 구성

일반 client는 server 역할의 winbind 대신 SSSD/adcli로 AD RFC2307 값을 읽는다.

```bash
sudo apt-get install -y \
  keyutils krb5-user nfs-common \
  adcli libnss-sss libpam-sss realmd sssd-ad sssd-tools
sudo adcli testjoin --domain=lab.decs.internal \
  --domain-controller=dc1.lab.decs.internal
```

join이 실패한 경우에만 password를 표준 입력으로 전달해 join한다.

```bash
read -rsp 'LAB AD Administrator password: ' DECS_LAB_AD_PASSWORD; printf '\n'
printf '%s\n' "$DECS_LAB_AD_PASSWORD" | sudo adcli join lab.decs.internal \
  --domain-realm=LAB.DECS.INTERNAL \
  --domain-controller=dc1.lab.decs.internal \
  --login-user=Administrator --stdin-password \
  --host-fqdn="$(hostname -s | tr '[:upper:]' '[:lower:]').lab.decs.internal" \
  --computer-name="$(hostname -s | tr '[:lower:]' '[:upper:]')"
unset DECS_LAB_AD_PASSWORD
```

`/etc/sssd/sssd.conf`의 핵심은 `ldap_id_mapping = False`다. SID 기반 숫자 대신
AD RFC2307 UID/GID를 쓰기 위해 필요하다.

```ini
[sssd]
services = nss, pam, ssh
domains = lab.decs.internal

[domain/lab.decs.internal]
ad_domain = lab.decs.internal
krb5_realm = LAB.DECS.INTERNAL
id_provider = ad
ldap_id_mapping = False
use_fully_qualified_names = False
fallback_homedir = /home/%u
default_shell = /bin/bash
```

```bash
sudo chmod 0600 /etc/sssd/sssd.conf
sudo systemctl disable --now winbind 2>/dev/null || true
sudo systemctl enable --now sssd rpc-gssd
sudo sss_cache -E
getent passwd test0524
id test0524
```

`/etc/nsswitch.conf`의 `passwd`, `group`에는 `files systemd sss`를 사용한다.

## 6. NFS mount와 사용자 credential

```bash
sudo install -d -o root -g root -m 0755 /mnt/lab-test-krb
sudo mount -t nfs4 \
  -o vers=4.1,sec=krb5,hard,proto=tcp,_netdev \
  lab-storage.lab.decs.internal:/294t/dcloud/share/test_krb \
  /mnt/lab-test-krb
findmnt /mnt/lab-test-krb -o TARGET,SOURCE,FSTYPE,OPTIONS
```

결과에는 `vers=4.1`과 `sec=krb5`가 있어야 한다. source를 IP로 바꾸지 않는다.

사용자 keytab은 `/etc/decs-krb/keytabs/<username>.keytab`에 `root:root 0400`으로
보관한다. host timer가 `/run/user/<uid>/krb5cc`를 갱신하고, container에는 ccache
directory와 읽기 전용 `/etc/krb5.conf`만 전달한다.

```bash
sudo systemctl enable --now decs-krb-refresh@<username>.timer
sudo systemctl start decs-krb-refresh@<username>.service
sudo -u '#<uid>' klist -c FILE:/run/user/<uid>/krb5cc
```

## 7. 검증과 rollback

1. AD, storage, client에서 같은 UID/GID와 primary group을 확인한다.
2. storage keytab의 NFS principal, `exportfs -v`, client mount option을 확인한다.
3. 유효한 사용자 ccache로 `user-share/<username>`에 생성·읽기·삭제를 수행한다.
4. 같은 group 두 사용자와 group 밖 사용자로 공유 권한을 확인한다.
5. container에서 `id`, `klist`, home write, SSH/Jupyter/noVNC readiness를 확인한다.

test-only rollback은 client unmount 후 test export를 해제하는 순서로 한다.

```bash
sudo umount /mnt/lab-test-krb
sudo exportfs -u 100.100.100.108:/294t/dcloud/share/test_krb
sudo exportfs -ra
```

LAB NFSv4.1에서는 구형 storage kernel의 idmap deferral이 session slot을 고착시킨
사례가 있다. production으로 확대하기 전에는
[NFSv4.1 session slot 고착](debugging/nfs-v41-session-slot-stuck.md)의 kernel
조건을 확인한다. keytab은 필요할 때 다음 checker로 읽기 전용 점검한다.

```bash
<저장소>/monitoring/health-checks/kerberos-nfs-keytab/script/check-nfs-keytab.sh --profile lab
```
