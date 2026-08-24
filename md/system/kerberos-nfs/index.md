# Kerberos/NFS 개요

> [설계](design.md) · [운영](operations.md) · [FARM 설정](farm-setup.md) · [LAB 설정](lab-setup.md) · [디버깅 로그](debugging/index.md) · [GitHub](https://github.com/CSID-DGU/admin_infra_server)

`kerberos-nfs` 매뉴얼은 FARM/LAB 서버에서 사용자가 공유 스토리지를 쓸 때 **누구인지
확인하고(Kerberos), 그 신원에 맞는 파일 권한을 적용하는(NFS)** 구성을 설명한다.

처음 보는 사람은 이 페이지에서 "어떤 매뉴얼을 먼저 읽어야 하는지"를 잡고, 각 매뉴얼
안에서 세부 내용을 내려가면 된다.

## Kerberos/NFS가 무엇을 하나

`kerberos-nfs`는 **사용자가 비밀번호 대신 Kerberos 티켓으로 NFS 서버에 신원을
증명하게 하고, AD에 기록된 UID/GID를 기준으로 공유 경로의 파일 권한을 적용한다.**

Kerberos는 신원을 확인하는 쪽을, NFS는 그 결과로 파일 접근 권한을 정하는 쪽을
담당한다. 두 가지가 어떻게 이어지는지는 [설계](design.md) 2~3장에 있다.

FARM과 LAB은 스토리지와 protocol이 서로 다르다. 현재 기준값은 다음과 같고, 자세한
설정은 각 가이드에 있다.

| 환경 | 스토리지 | 설정 가이드 |
| --- | --- | --- |
| FARM | Synology NAS, NFSv4.0 | [FARM Kerberos 설정 가이드](farm-setup.md) |
| LAB | Linux storage, NFSv4.1 | [LAB Kerberos 설정 가이드](lab-setup.md) |

## 상황별로 볼 곳

| 상황 | 확인할 매뉴얼 |
| --- | --- |
| Kerberos가 처음이고 티켓·keytab 같은 용어를 모르겠다 | [설계](design.md) 2장 핵심 개념 |
| 인증이 NFS 접근으로 이어지는 과정을 알고 싶다 | [설계](design.md) 3장 |
| FARM/LAB에 어떤 값이 적용되어 있는지 확인하고 싶다 | [설계](design.md) 4장, 8장 설정 확인 위치 |
| 환경을 처음부터 구성해야 한다 | [FARM 설정](farm-setup.md) 또는 [LAB 설정](lab-setup.md) |
| 사용자 keytab이나 ccache를 확인해야 한다 | [운영](operations.md) 3~4장 |
| mount가 안 되거나 권한이 이상하다 | [운영](operations.md) 5장 mount source 확인 |
| NAS 계정과 KVNO 문제를 봐야 한다 | [운영](operations.md) 8장 |
| 장애가 났는데 무엇부터 봐야 할지 모르겠다 | [운영](operations.md) 10장 장애 진단 순서 |
| 과거에 있었던 장애의 원인과 재현 조건을 알고 싶다 | [디버깅 로그](debugging/index.md) |
| 설정을 바꾸기 전후에 확인할 것을 알고 싶다 | [운영](operations.md) 11장 체크리스트 |

## 매뉴얼 읽기 순서

### 1. 설계 매뉴얼에서 개념과 흐름을 본다

- [설계](design.md)가 매뉴얼의 핵심 내용을 담고 있다. Kerberos 용어(2장)를 먼저 정리하고, 그
  티켓이 NFS 인증으로 이어지는 과정(3장)을 본다.
- FARM과 LAB에 실제로 적용한 값과 그렇게 정한 이유는 4장부터 나온다.

### 2. 환경을 구성할 때만 설정 가이드로 간다

- [FARM 설정](farm-setup.md)과 [LAB 설정](lab-setup.md)은 AD, 스토리지, 클라이언트를
  처음부터 구성하는 순서를 다룬다.
- 이미 구성된 환경을 운영하는 중이라면 건너뛰고 운영 매뉴얼로 가도 된다.

### 3. 운영 매뉴얼에서 확인과 장애 대응 절차를 따라간다

- [운영](operations.md)은 credential 확인, mount 점검, KVNO와 NFS 장애 대응을 다룬다.
- 진단 중에 같은 증상이 과거에 있었는지 확인하려면 [디버깅 로그](debugging/index.md)를
  본다. 재현 조건과 검증 결과가 날짜순으로 쌓여 있다.

## 매뉴얼 지도

| 매뉴얼 | 역할 | 여기서 이해하는 내용 |
| --- | --- | --- |
| 개요 (현재 페이지) | 출발점 | Kerberos/NFS가 하는 일, FARM/LAB 차이, 매뉴얼 읽는 순서 |
| [설계](design.md) | 개념·구조 | principal·ticket·keytab·ccache, RPCSEC_GSS 인증 흐름, FARM/LAB 설정과 선택 이유 |
| [FARM 설정](farm-setup.md) | 구축 절차 | Samba AD, Synology NAS, NFSv4.0 기준의 FARM 구성 순서 |
| [LAB 설정](lab-setup.md) | 구축 절차 | Samba AD, Linux storage, NFSv4.1 기준의 LAB 구성 순서 |
| [운영](operations.md) | 실행 절차 | credential 확인, mount 점검, KVNO 운영, 장애 진단 순서 |
| [디버깅 로그](debugging/index.md) | 장애 기록 | 재현된 장애의 증상, 실험 조건, 증거와 조치 결과 |

## 이 매뉴얼이 다루는 범위

- 사용자와 service의 **신원 확인**, 그리고 그 결과로 정해지는 **공유 스토리지 접근
  권한**을 다룬다.
- 서버에 Kerberos/NFS 관련 패키지와 mount가 기준대로 되어 있는지 점검하는 일은
  다루지 않는다. [server-state](../server-state/index.md) 참고.
- mount 상태를 지속적으로 관측하고 알림을 보내는 일은 다루지 않는다.
  [monitoring](../monitoring/index.md) 참고.
- container 안에서 Kerberos ccache를 쓰는 방식은 다루지 않는다.
  [container-images 설계](../container-images/design.md) 참고.
- keytab, 비밀번호, principal의 실제 값은 적지 않는다. 확인 절차와 위치만 적는다.
