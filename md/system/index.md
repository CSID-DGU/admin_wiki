# System

System 영역은 FARM/LAB GPU 서버를 일관된 기준으로 운영하기 위한 관리
기능을 제공한다. 서버의 공통 상태와 구축 기준, 사용자 GPU 컨테이너 이미지,
상태 관측, 원격 부팅, AD Kerberos 기반 NFS 접근을 다섯 모듈로 나누어 관리한다. 이 페이지에서 필요한 기능의 담당 모듈과 세부 문서를 확인할 수 있다.

처음 보는 사람은 이 페이지에서 "어떤 문서를 먼저 읽어야 하는지"를 잡고, 각 문서
안에서 세부 내용을 내려가면 된다.

## 어디부터 보면 되나

| 상황 | 확인할 문서 |
| --- | --- |
| 관리용 데스크탑에서 ansible을 사용해 서버에 접속해 본 적이 없다 | [ansible 개요](ansible/index.md)부터 시작한다 |
| 서버가 운영 기준(패키지, GPU, Kubernetes, NFS 등)에 맞게 구성됐는지 확인해야 한다 | [server-state](server-state/index.md) |
| 사용자 GPU 컨테이너 이미지를 만들거나 고쳐야 한다 | [container-images](container-images/index.md) |
| 서버·서비스 상태를 관측하거나 경보 원인을 확인해야 한다 | [monitoring](monitoring/index.md) |
| 서버를 원격으로 켜거나 부팅 직후 자동 점검을 봐야 한다 | [remote-operations](remote-operations/index.md) |
| AD Kerberos 인증이나 NFS 접근 문제를 봐야 한다 | [kerberos-nfs](kerberos-nfs/index.md) |
| 신규 관리자로 System 영역 전체를 처음 파악해야 한다 | 아래 [전체 구조](#전체-구조)부터 훑고 [ansible 개요](ansible/index.md)로 간다 |

## 사전 준비

아래 모듈의 명령은 대부분 Ansible을 통해 FARM/LAB 서버에 접속해 수행된다. **어떤 모듈을
쓰든 상관없이, [ansible 설정](ansible/index.md)을 먼저
마쳐야 명령이 정상적으로 실행된다.** Ansible은 다섯 모듈과 나란히 있는 여섯 번째 모듈이 아니며, 다섯
모듈을 쓰기 전에 공통으로 먼저 준비해야 하는 설정이다. 그래서 아래 "전체 구조" 표에도
모듈이 아닌 별도 행으로 표시했다.

## 전체 구조

`server-state`는 전체 서버 운영 기준을 확인하는 시작점이고, 나머지 네 모듈은
이미지, 관측, 원격 기동, 인증·스토리지라는 개별 기능을 소유한다. 아래 순서는
문서를 이해하기 위한 배치이며 모듈 간 실행 순서나 의존 순서를 뜻하지 않는다.
각 모듈의 역할과 담당 범위는 다음과 같다.

| 구성요소 | 핵심 역할 | 담당 범위 |
| --- | --- | --- |
| [`ansible`](ansible/index.md) (모듈 아님, 사전 준비 단계) | 모든 모듈이 FARM/LAB 서버에 접속하는 방식 제공 | SSH 공개키, 관리자별 `~/.ansible.cfg`, 공용 inventory, NOPASSWD sudo 준비 |
| [`server-state`](server-state/index.md) | FARM/LAB 서버의 공통 상태와 구축·점검 기준 정의 | 서버 profile, Docker/NVIDIA/Kubernetes/network/NFS 전제조건, 신규 서버 bootstrap 순서, 기존 서버 drift 점검과 remediation 계획 |
| [`container-images`](container-images/index.md) | 사용자 GPU 컨테이너 이미지와 시작 환경 관리 | CUDA/TensorFlow image variant, Dockerfile, entrypoint, UID/GID·VNC·Kerberos ccache 런타임 계약, 이미지 테스트·배포 |
| [`monitoring`](monitoring/index.md) | 서버와 서비스의 현재 상태를 지속적으로 관측 | exporter, Prometheus, Grafana, Alertmanager, GPU/container/NFS 상태, 경보, forensics와 제한된 안전 복구 |
| [`remote-operations`](remote-operations/index.md) | 서버 원격 부팅과 부팅 시점의 일회성 준비 작업 수행 | Wake-on-LAN, 부팅 시 1회 health gate, 필수 mount·GPU·SSH 확인, 기존 stopped container 시작과 사후 점검 |
| [`kerberos-nfs`](kerberos-nfs/index.md) | AD Kerberos 인증과 NFS 공유 스토리지 접근 기준 관리 | AD Kerberos, UID/GID 일치, keytab·ccache, RPCSEC_GSS, FARM/LAB NFS 기준 문서, 명시적 repair·rotation·mount 절차 |

## PDF와 세부 문서

| 문서 | 상세 문서 | PDF |
| --- | --- | --- |
| 전체 통합 매뉴얼 | - | [PDF 열기](../../pdf/system/server-manage-manual.pdf) |
| 전체 구조 | 현재 페이지 | [PDF 열기](../../pdf/system/server-manage-index.pdf) |
| `ansible/` | [문서 열기](ansible/index.md) | [PDF 열기](../../pdf/system/ansible-manual.pdf) |
| `server-state/` | [문서 열기](server-state/index.md) | [PDF 열기](../../pdf/system/server-state-manual.pdf) |
| `container-images/` | [문서 열기](container-images/index.md) | [PDF 열기](../../pdf/system/container-images-manual.pdf) |
| `monitoring/` | [문서 열기](monitoring/index.md) | [PDF 열기](../../pdf/system/monitoring-manual.pdf) |
| `remote-operations/` | [문서 열기](remote-operations/index.md) | [PDF 열기](../../pdf/system/remote-operations-manual.pdf) |
| `kerberos-nfs/` | [문서 열기](kerberos-nfs/index.md) | [PDF 열기](../../pdf/system/kerberos-nfs-manual.pdf) |
