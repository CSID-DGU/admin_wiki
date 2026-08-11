# 관리자용 자동화 시스템 매뉴얼

이 위키는 DGU AI LAB의 GPU 서버 서비스를 운영하는 관리자를 위한 자동화 시스템
매뉴얼이다.

자동화 시스템은 `backend`, `infra`, `system` 세 영역으로 구성된다. `backend`는
GPU 서버 사용 신청과 승인 등의 서비스 요청을 처리하고, `infra`는 승인된 사용자의
계정과 홈 디렉터리, Pod, NodePort를 생성한다. `system`은 자동화 시스템이 동작하는
GPU 서버와 컨테이너 실행 환경, 모니터링, 원격 작업, Kerberos/NFS 공유 스토리지를
관리한다.

`user`는 GPU 서버 서비스를 사용하는 학생과 연구원을 위한 사용자 매뉴얼이다.

## 문서 목차

모든 영역의 문서를 한 파일로 보려면 [전체 매뉴얼 PDF를 다운로드](pdf/system/server-manage-manual.pdf)한다.

| 영역 | 설명 | PDF 다운로드 |
| --- | --- | --- |
| [backend](backend/개요.md) | 신청·승인을 처리하고 Infra Server에 자원 생성과 회수를 요청하는 Admin BE 서버 | [PDF 다운로드](pdf/backend/admin-be-manual.pdf) |
| [infra](infra/개요.md) | Backend 요청을 받아 계정, 홈 디렉터리, Pod와 NodePort를 구성하는 config-server | [PDF 다운로드](pdf/infra/infra-all-manual.pdf) |
| [system](system/index.md) | FARM/LAB GPU 서버의 공통 설정과 운영 환경을 관리하는 도구와 절차 | [PDF 다운로드](pdf/system/system-manual.pdf) |
| [user](user/index.md) | 학생과 연구원이 GPU 서버 서비스를 사용하는 방법 | [PDF 다운로드](pdf/user/user-manual.pdf) |

`backend`와 `infra`는 서로 분리되어 배포되는 서버 애플리케이션이다. `backend`의
Admin BE는 웹 화면(Admin FE)에서 전달된 사용자·관리자 요청을 받아 신청과 승인 상태를
MySQL에 저장하고, 인증, 알림과 만료 처리를 담당한다. 관리자가 신청을 승인하면
별도로 배포된 `infra`의 config-server에 계정과 컨테이너 생성 또는 회수를 요청한다.

`infra`의 config-server는 Backend 요청에 따라 Kubernetes, NAS, KDC와 infra-mysql에
접근하여 Linux 계정과 홈 디렉터리, GPU Pod, NodePort를 실제로 구성한다. `system`은
FARM/LAB GPU 서버의 공통 설정, 컨테이너 이미지, 모니터링, 원격 작업과
Kerberos/NFS 공유 스토리지를 관리하는 운영 도구와 절차를 다룬다. `user`는 서비스
신청부터 서버 접속과 이용, 데이터 백업까지 학생과 연구원에게 제공되는 절차를
설명한다.

처음 보는 사람에게는 `backend` → `infra` → `system` → `user` 순서로 읽는 것을
권장한다.
