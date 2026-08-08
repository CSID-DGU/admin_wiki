# container-images 개요

`container-images`는 GPU container가 시작된 뒤 사용자가 바로 작업할 수 있도록
계정, 공유 홈, SSH, Jupyter, VNC와 Kerberos 환경을 구성하고 CUDA/TensorFlow
조합별 image를 제공한다. **설계**는 공통 entrypoint의 런타임 구성과 이미지
버전을 설명하고, **운영**은 빌드·배포에 사용하는 명령, 테스트 전략과 변경
절차를 설명한다.

## 문서 구성

| 문서 | 핵심 내용 |
| --- | --- |
| 현재 페이지 | 책임 범위와 문서 안내 |
| [설계](design.md) | 개요, 계정·홈·SSH·Jupyter·VNC·Kerberos 구성, CUDA/TensorFlow 조합별 이미지, 디렉터리 지도 |
| [운영](operations.md) | 빌드/배포 흐름, 테스트 전략, 변경 가이드, 운영 안전 수칙 |

처음 보는 사람은 **설계 문서**에서 이미지가 무엇을 책임지고 무엇을 책임지지
않는지 먼저 확인하고, 실제로 빌드하거나 새 이미지 버전을 추가해야 할 때
**운영 문서**로 이동한다.
