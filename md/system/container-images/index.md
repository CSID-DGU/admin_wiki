# container-images

> 역할: DECS GPU 컨테이너 이미지의 빌드 입력, 시작 시 런타임 구성, 검증을 소유한다.

이 문서는 container-images 문서의 시작점이다. **설계**는 이미지 variant manifest,
Dockerfile, entrypoint 구성과 `user-lifecycle`과의 계약을 설명하고, **운영**은
빌드·배포에 사용하는 명령, 테스트 전략과 변경 절차를 설명한다.

## 문서 구성

| 문서 | 핵심 내용 |
| --- | --- |
| 현재 페이지 | 책임 범위와 문서 안내 |
| [설계](design.md) | 디렉터리 지도, manifest 기반 variant, Dockerfile/entrypoint 구성, user-lifecycle 계약 |
| [운영](operations.md) | 빌드/배포 흐름, 테스트 전략, 변경 가이드, 운영 안전 수칙 |

처음 보는 사람은 **설계 문서**에서 이미지가 무엇을 책임지고 무엇을 책임지지
않는지 먼저 확인하고, 실제로 빌드하거나 새 variant를 추가해야 할 때
**운영 문서**로 이동한다.
