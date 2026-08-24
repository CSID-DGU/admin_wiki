# System 개요

> [ansible](ansible/index.md) · [server-state](server-state/index.md) · [container-images](container-images/index.md) · [monitoring](monitoring/index.md) · [remote-operations](remote-operations/index.md) · [kerberos-nfs](kerberos-nfs/index.md) · [GitHub](https://github.com/CSID-DGU/admin_infra_server)

System 영역은 FARM/LAB GPU 서버를 일관된 기준으로 운영하기 위한 관리 기능을
다섯 모듈로 나누어 제공한다.

처음 보는 사람은 이 페이지에서 "어떤 매뉴얼을 먼저 읽어야 하는지"를 잡고, 각 매뉴얼
안에서 세부 내용을 내려가면 된다.

## 상황별로 볼 곳

| 상황 | 확인할 매뉴얼 |
| --- | --- |
| 관리용 데스크탑에서 Ansible로 서버에 접속해 본 적이 없다 | [ansible](ansible/index.md)부터 시작한다 |
| 서버가 운영 기준(패키지, GPU, Kubernetes, NFS 등)에 맞는지 확인해야 한다 | [server-state](server-state/index.md) |
| 사용자 GPU 컨테이너 이미지를 만들거나 고쳐야 한다 | [container-images](container-images/index.md) |
| 서버 상태를 그래프로 보거나 알림 원인을 확인해야 한다 | [monitoring](monitoring/index.md) |
| 서버를 원격으로 켜거나 부팅 직후 점검 결과를 봐야 한다 | [remote-operations](remote-operations/index.md) |
| Kerberos 인증이나 NFS 접근 문제를 봐야 한다 | [kerberos-nfs](kerberos-nfs/index.md) |
| System 영역 전체를 처음 파악해야 한다 | 아래 [전체 구조](#전체-구조)를 훑고 [ansible](ansible/index.md)로 간다 |

## 사전 준비

모듈 명령은 대부분 Ansible로 FARM/LAB 서버에 접속해 수행된다. **어떤 모듈을 쓰든
[ansible 설정](ansible/index.md)을 먼저 마쳐야 명령이 정상적으로 실행된다.**

Ansible은 다섯 모듈과 나란히 있는 여섯 번째 모듈이 아니라, 다섯 모듈을 쓰기 전에
공통으로 준비해 두는 설정이다. 그래서 아래 표에도 모듈이 아닌 별도 행으로 적었다.

## 전체 구조

`server-state`가 서버 운영 기준을 확인하는 시작점이고, 나머지 네 모듈은 이미지,
관측, 원격 기동, 인증·스토리지를 각각 맡는다. 아래 순서는 매뉴얼을 이해하기 위한
배치이며, 모듈 사이의 실행 순서나 의존 순서를 뜻하지 않는다.

| 구성요소 | 하는 일 |
| --- | --- |
| [`ansible`](ansible/index.md) (모듈 아님, 사전 준비) | 모든 모듈이 FARM/LAB 서버에 접속하는 방식을 제공한다 |
| [`server-state`](server-state/index.md) | 서버가 공통 운영 기준과 어긋났는지 점검하고 기준에 맞게 고친다 |
| [`container-images`](container-images/index.md) | GPU 컨테이너 안의 사용자 환경을 구성하고 CUDA/TensorFlow 조합별 이미지를 제공한다 |
| [`monitoring`](monitoring/index.md) | 서버와 service 상태를 계속 수집해 그래프로 보여주고 이상 상태면 알린다 |
| [`remote-operations`](remote-operations/index.md) | 서버를 원격으로 켜고, 쓸 수 있는 상태인지 확인한 뒤 사용자 컨테이너를 시작한다 |
| [`kerberos-nfs`](kerberos-nfs/index.md) | Kerberos로 사용자를 인증하고 그 신원에 맞는 NFS 공유 스토리지 권한을 적용한다 |

세 모듈은 다루는 시점이 서로 비슷해 보이지만 역할이 다르다. `server-state`는
**기준에 맞게 고치고**, `remote-operations`는 **부팅 시점에 한 번 확인하고**,
`monitoring`은 **계속 지켜본다.**

## PDF와 세부 매뉴얼

| 매뉴얼 | 상세 매뉴얼 | PDF |
| --- | --- | --- |
| 전체 통합 매뉴얼 | - | [PDF 열기](../../pdf/system/server-manage-manual.pdf) |
| 전체 구조 | 현재 페이지 | [PDF 열기](../../pdf/system/server-manage-index.pdf) |
| `ansible/` | [매뉴얼 열기](ansible/index.md) | [PDF 열기](../../pdf/system/ansible-manual.pdf) |
| `server-state/` | [매뉴얼 열기](server-state/index.md) | [PDF 열기](../../pdf/system/server-state-manual.pdf) |
| `container-images/` | [매뉴얼 열기](container-images/index.md) | [PDF 열기](../../pdf/system/container-images-manual.pdf) |
| `monitoring/` | [매뉴얼 열기](monitoring/index.md) | [PDF 열기](../../pdf/system/monitoring-manual.pdf) |
| `remote-operations/` | [매뉴얼 열기](remote-operations/index.md) | [PDF 열기](../../pdf/system/remote-operations-manual.pdf) |
| `kerberos-nfs/` | [매뉴얼 열기](kerberos-nfs/index.md) | [PDF 열기](../../pdf/system/kerberos-nfs-manual.pdf) |
