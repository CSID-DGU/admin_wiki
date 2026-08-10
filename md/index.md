# 운영 위키

이 위키는 `backend`, `infra`, `system`, `user` 문서를 한곳에 모아 둔 운영 안내서다. 아래 표에서 각 묶음이 무엇을 다루는지와 안에 어떤 문서가 들어 있는지 먼저 보고 들어가면 찾기 쉽다.

## 문서 빠르게 찾기

| 분류 | 다루는 내용 | 안에 있는 문서 | 먼저 읽을 때 |
| --- | --- | --- | --- |
| [backend](backend/index.md) | 신청, 승인, 계정 수명주기, 알림, API 서버 구조 | 개요, 시스템 아키텍처, 도메인 설명, 운영 가이드, 인증·보안, 외부 연동 | Spring Boot 서버 흐름과 DB 구조를 먼저 파악할 때 |
| [infra](infra/index.md) | config-server가 계정, 홈 디렉터리, Pod, NodePort, Kerberos를 만드는 방식 | 개요, 시스템 아키텍처, 기초 개념, 데이터베이스, 운영 매뉴얼, API 레퍼런스, Helm 차트, kdc-setup | 승인 뒤 실제로 어떤 인프라 작업이 일어나는지 볼 때 |
| [system](system/index.md) | GPU 서버 운영 기반, 이미지, 상태 수집, 원격 부팅, 모니터링, Kerberos/NFS | container-images, server-state, remote-operations, monitoring, kerberos-nfs | 서버 운영 코드와 공통 운영 절차를 볼 때 |
| [user](user/index.md) | 학생 사용자의 신청, 접속, 홈페이지 사용, 백업 안내 | LAB & FARM 유저 매뉴얼, 홈페이지 이용 방법, 서버 내 파일 백업하기 | 최종 사용자 관점의 사용법을 확인할 때 |
| [PDF 다운로드](downloads.md) | 각 문서의 PDF 산출물 | system PDF, infra PDF | 문서를 인쇄하거나 공유용 PDF가 필요할 때 |

## 상황별 출발점

| 하고 싶은 일 | 먼저 볼 문서 | 이어서 볼 문서 |
| --- | --- | --- |
| 새 관리자로 전체 구조를 익힌다 | [backend 개요](backend/개요.md) | [infra 개요](infra/개요.md), [system 목차](system/index.md) |
| 승인 뒤 계정과 Pod가 어떻게 만들어지는지 본다 | [infra 개요](infra/개요.md) | [infra 시스템 아키텍처](infra/design/시스템-아키텍처.md), [API 레퍼런스](infra/operations/API-레퍼런스.md) |
| 운영 중 장애를 점검한다 | [infra 운영 매뉴얼](infra/operations/운영-매뉴얼.md) | [infra 데이터베이스](infra/design/데이터베이스.md), [system monitoring](system/monitoring/index.md) |
| Kerberos와 NFS 흐름을 본다 | [infra kdc-setup](infra/kdc-setup/index.md) | [system kerberos-nfs](system/kerberos-nfs/index.md) |
