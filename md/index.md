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

| 영역 | 설명 | 바로가기 |
| --- | --- | --- |
| `backend` | 사용 신청과 승인, 인증, 알림 등 서비스 요청을 처리하는 Admin BE | [backend 개요](backend/개요.md) |
| `infra` | 승인된 사용자의 계정, 홈 디렉터리, Pod와 NodePort를 생성하는 Infra Server | [infra 개요](infra/개요.md) |
| `system` | GPU 서버의 공통 설정, 컨테이너 이미지, 모니터링, 원격 작업과 공유 스토리지 관리 | [system 개요](system/index.md) |
| `user` | 학생과 연구원이 GPU 서버 서비스를 사용하는 방법 | [사용자 매뉴얼](user/index.md) |
