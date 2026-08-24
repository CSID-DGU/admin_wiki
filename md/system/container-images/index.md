# container-images 개요

> [설계](design.md) · [운영](operations.md) · [GitHub](https://github.com/CSID-DGU/admin_infra_server)

`container-images` 매뉴얼은 사용자가 GPU 서버에서 쓰는 container의 **내부 환경**을
설명한다. 사용자가 접속하자마자 자기 계정과 홈으로 작업할 수 있게 하는 부분과,
CUDA/TensorFlow 조합별로 나뉘는 이미지 버전을 다룬다.

처음 보는 사람은 이 페이지에서 "어떤 매뉴얼을 먼저 읽어야 하는지"를 잡고, 각 매뉴얼
안에서 세부 내용을 내려가면 된다.

## container-images가 무엇을 하나

`container-images`는 **GPU container가 시작될 때 그 안에 사용자 계정과 홈, SSH,
Jupyter, VNC, Kerberos 환경을 구성하고, CUDA/TensorFlow 조합별 이미지를 제공한다.**

container를 만들고 실행하는 일 자체는 이 모듈이 아니라 `infra`가 한다. 이 모듈이
담당하는 것은 그렇게 만들어진 container의 내부다. 그 경계와 관리 대상은
[설계](design.md) 1장에 있다.

## 상황별로 볼 곳

| 상황 | 확인할 매뉴얼 |
| --- | --- |
| 무엇을 바꾸려면 어느 파일을 고쳐야 하는지 찾고 싶다 | [운영](operations.md) 2장 목적별 수정 위치 |
| 새 CUDA/TensorFlow 조합을 추가해야 한다 | [운영](operations.md) 3장 새 이미지 버전 추가 |
| 계정·홈·SSH 같은 시작 동작을 바꿔야 한다 | [운영](operations.md) 4장 기존 구성 변경 |
| 이미지를 직접 빌드해 보고 싶다 | [운영](operations.md) 5장 로컬 build |
| 빌드한 이미지를 검증하고 배포해야 한다 | [운영](operations.md) 6~7장 |
| 운영 container를 교체하거나 되돌려야 한다 | [운영](operations.md) 8~9장 |
| container 안에서 계정과 홈이 어떻게 만들어지는지 알고 싶다 | [설계](design.md) 2장 사용자 실행 환경 |
| 이미지 버전이 어떻게 정의되는지 알고 싶다 | [설계](design.md) 3장 이미지 구성 |

## 매뉴얼 읽기 순서

### 1. 설계 매뉴얼에서 책임 범위부터 잡는다

- [설계](design.md) 1장이 `infra`와 이 모듈의 경계를 설명한다. 이 경계를 먼저 잡지
  않으면 "container가 안 뜬다"는 문제를 어느 모듈에서 봐야 하는지 판단하기 어렵다.
- 이어서 시작할 때 실행 환경을 구성하는 방식(2장)과 이미지 버전을 정의하는
  방식(3장)을 본다.

### 2. 운영 매뉴얼에서 변경 절차를 따라간다

- [운영](operations.md)은 파일을 고르는 것부터 빌드·검증·배포까지의 순서를 다룬다.
- 무엇을 바꾸든 2장(목적별 수정 위치)에서 시작해 해당 절차로 내려가면 된다.

`container-images`는 다른 모듈과 달리 Ansible을 쓰지 않는다. Docker 빌드와 registry
배포만 하므로 [Ansible 설정](../ansible/config.md)이 없어도 작업할 수 있다.

## 매뉴얼 지도

| 매뉴얼 | 역할 | 여기서 이해하는 내용 |
| --- | --- | --- |
| 개요 (현재 페이지) | 출발점 | container-images가 하는 일, 매뉴얼 읽는 순서 |
| [설계](design.md) | 개념·구조 | `infra`와의 경계, 계정·홈·SSH·Jupyter·VNC·Kerberos 구성 방식, 이미지 버전 정의, 디렉터리 지도 |
| [운영](operations.md) | 실행 절차 | 목적별 수정 위치, 새 이미지 버전 추가, 빌드·검증·배포, container 교체와 rollback |

## 이 매뉴얼이 다루는 범위

- GPU container **안에서** 벌어지는 일만 다룬다. 이미지를 정의하고, 시작할 때
  실행 환경을 구성하고, 그 이미지를 빌드해 배포하는 것까지다.
- container를 만들고 실행하며 UID/GID·홈 경로·포트 같은 값을 넘겨주는 쪽은 다루지
  않는다. [infra 개요](../../infra/개요.md) 참고.
- 서버 자체에 Docker나 NVIDIA driver가 기준대로 설치되어 있는지는 다루지 않는다.
  [server-state](../server-state/index.md) 참고.
- Kerberos 인증과 NFS 공유 스토리지 자체의 구조는 다루지 않는다.
  [Kerberos/NFS 설계](../kerberos-nfs/design.md) 참고.
- Docker Hub 계정과 secret 같은 실제 값은 적지 않는다. 어디에서 관리하는지만 적는다.
