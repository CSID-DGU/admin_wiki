# System

> DECS GPU 서버를 **같은 기준으로 준비하고**, **안전하게 기동하며**,
> **컨테이너 실행 환경과 공유 스토리지 접근을 제공하고**, 그 상태를
> **지속적으로 관측**하는 운영 영역이다.

System 영역은 하나의 애플리케이션이나 순차 실행 파이프라인이 아니다. 서로 다른
운영 책임을 가진 다섯 모듈이 각자의 기능을 담당한다. 어떤 모듈의 출력이 다음
모듈의 입력으로 반드시 이어지는 구조는 아니며, 필요한 운영 작업에 맞는 모듈을
선택해 사용한다.

## 전체 구조

`server-state`는 전체 서버 운영 기준을 확인하는 시작점이고, 나머지 네 모듈은
이미지, 관측, 원격 기동, 인증·스토리지라는 개별 기능을 소유한다. 아래 순서는
문서를 이해하기 위한 배치이며 모듈 간 실행 순서나 의존 순서를 뜻하지 않는다.
각 모듈의 역할과 경계는 다음과 같다.

| 구성요소 | 핵심 역할 | 담당 범위 | 담당하지 않는 범위 |
| --- | --- | --- | --- |
| [`server-state/`](server-state/index.md) | FARM/LAB 서버의 공통 상태와 구축·점검 기준 정의 | 서버 profile, Docker/NVIDIA/Kubernetes/network/NFS 전제조건, 신규 서버 bootstrap 순서, 기존 서버 drift 점검과 remediation 계획 | 상시 monitoring, 전원 제어, 개별 운영 모듈의 구현 대체 |
| [`container-images/`](container-images/index.md) | 사용자 GPU 컨테이너 이미지와 시작 환경 관리 | CUDA/TensorFlow image variant, Dockerfile, entrypoint, UID/GID·VNC·Kerberos ccache 런타임 계약, 이미지 테스트·배포 | GPU 서버 자체의 드라이버 설치, 서버 부팅 순서, 상시 상태 관측 |
| [`monitoring/`](monitoring/index.md) | 서버와 서비스의 현재 상태를 지속적으로 관측 | exporter, Prometheus, Grafana, Alertmanager, GPU/container/NFS 상태, 경보, forensics와 제한된 안전 복구 | 서버 구축 기준 정의, 전체 부팅 orchestration, AD/NFS의 위험한 상태 변경 |
| [`remote-operations/`](remote-operations/index.md) | 서버 원격 부팅과 부팅 시점의 일회성 준비 작업 수행 | Wake-on-LAN, 부팅 시 1회 health gate, 필수 mount·GPU·SSH 확인, 기존 stopped container 시작과 사후 점검 | 주기적 상태 수집, 서버의 목표 상태 정의, 새 컨테이너 생성 |
| [`kerberos-nfs/`](kerberos-nfs/index.md) | AD Kerberos 인증과 NFS 공유 스토리지 접근 기준 관리 | AD Kerberos, UID/GID 일치, keytab·ccache, RPCSEC_GSS, FARM/LAB NFS 기준 문서, 명시적 repair·rotation·mount 절차 | 공통 host 설정의 전체 적용, 지속 monitoring, 컨테이너 이미지 빌드 |

## 어디서 시작할까

| 상황 | 먼저 볼 문서 |
| --- | --- |
| 신규 GPU 서버 구축, 공통 설정 확인, 서버 간 drift 점검 | [`server-state`](server-state/index.md) |
| CUDA/TensorFlow 조합 추가, 이미지 빌드, entrypoint 변경 | [`container-images`](container-images/index.md) |
| metric 누락, dashboard·alert 확인, GPU/container/NFS 장애 진단 | [`monitoring`](monitoring/index.md) |
| 서버 원격 부팅, boot gate 실패, 부팅 후 컨테이너 시작 문제 | [`remote-operations`](remote-operations/index.md) |
| Kerberos ticket, keytab, UID/GID, NFS mount·권한 문제 | [`kerberos-nfs`](kerberos-nfs/index.md) |

## 문서와 PDF

| 문서 | 웹 문서 | PDF |
| --- | --- | --- |
| 전체 통합 매뉴얼 | - | [PDF 열기](../../pdf/system/server-manage-manual.pdf) |
| 전체 구조 | 현재 페이지 | [PDF 열기](../../pdf/system/server-manage-index.pdf) |
| `server-state/` | [문서 열기](server-state/index.md) | [PDF 열기](../../pdf/system/server-state-manual.pdf) |
| `container-images/` | [문서 열기](container-images/index.md) | [PDF 열기](../../pdf/system/container-images-manual.pdf) |
| `monitoring/` | [문서 열기](monitoring/index.md) | [PDF 열기](../../pdf/system/monitoring-manual.pdf) |
| `remote-operations/` | [문서 열기](remote-operations/index.md) | [PDF 열기](../../pdf/system/remote-operations-manual.pdf) |
| `kerberos-nfs/` | [문서 열기](kerberos-nfs/index.md) | [PDF 열기](../../pdf/system/kerberos-nfs-manual.pdf) |
