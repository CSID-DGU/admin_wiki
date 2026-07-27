# FARM/LAB 설정 가이드

이 페이지는 Kerberos/NFS 설계에서 설명한 구성 요소를 실제 환경에 적용하는
FARM과 LAB별 설정 runbook을 제공한다. 두 문서는 wiki 본문을 요약한 내용이 아니라
각 환경의 AD, storage, host, 사용자 keytab과 검증 절차를 모두 담은 PDF 스냅샷이다.

환경의 endpoint, principal, mount option은 변경될 수 있다. 작업을 시작하기 전에는
PDF의 검증 명령을 다시 실행하고, 최신 기준은 아래 원본 Markdown runbook에서
확인한다.

## FARM 설정

FARM은 Synology NAS를 AD domain member와 NFS server로 사용한다. 이 문서에는
Samba AD DC, NAS join·RFC2307, NFS service keytab, FARM host mount, 사용자
ccache와 container 검증 절차가 들어 있다.

- [FARM NAS / AD / Kerberos NFS 설정 runbook PDF 열기](../../pdf/system/kerberos-nfs-farm-setup-guide.pdf)
- [FARM 원본 Markdown runbook](https://github.com/CSID-DGU/admin_infra_server/blob/main/kerberos-nfs/docs/farm.md)

## LAB 설정

LAB은 Linux storage를 AD domain member와 NFS server로 사용한다. 이 문서에는
LAB AD DC, Linux storage join·RFC2307, `test_krb` export, NFSv4.1 client mount,
사용자 ccache와 검증·rollback 절차가 들어 있다.

- [LAB storage / AD / Kerberos NFS 설정 runbook PDF 열기](../../pdf/system/kerberos-nfs-lab-setup-guide.pdf)
- [LAB 원본 Markdown runbook](https://github.com/CSID-DGU/admin_infra_server/blob/main/kerberos-nfs/docs/lab.md)

두 PDF는 배포 시점의 runbook 내용이다. 현재 적용값을 바꾸거나 복구 작업을 할
때에는 PDF보다 원본 runbook과 해당 playbook의 최신 설정을 우선한다.
