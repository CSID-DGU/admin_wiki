# 운영 위키

이 위키는 DGU AI LAB의 GPU 서버 서비스를 운영할 때 참고하는 문서를 모아 둔 곳이다. 서비스는 크게 네 부분으로 나뉜다. `backend`는 신청과 승인, `infra`는 계정과 Pod 생성, `system`은 서버와 스토리지 같은 운영 환경 관리, `user`는 사용자 안내를 맡는다.

## 먼저 보면 좋은 흐름

처음 읽을 때는 실제 서비스가 움직이는 순서대로 보는 편이 이해하기 쉽다.

1. [backend](backend/index.md)에서 신청, 승인, 상태 저장, 알림이 어떻게 처리되는지 본다.
2. [infra](infra/index.md)에서 승인된 사용자를 위해 계정, 홈 디렉터리, Pod, NodePort를 어떻게 만드는지 본다.
3. [system](system/index.md)에서 그 작업이 돌아가는 GPU 서버, 컨테이너 이미지, 모니터링, 원격 부팅, Kerberos/NFS 설정을 본다.
4. [user](user/index.md)에서 사용자가 실제로 보는 화면과 사용 절차를 본다.

전체 구조를 빠르게 잡고 싶다면 `backend -> infra -> system -> user` 순서로 읽으면 된다.

## 각 영역에서 무엇을 볼 수 있나

### [backend](backend/index.md)

`backend`는 Admin BE(Spring Boot) 문서다. 신청을 어떻게 저장하고 승인하는지, 어떤 API와 스케줄러가 도는지, 인증과 알림이 어떻게 붙는지를 여기서 본다.

- `시작 가이드`는 로컬 실행과 개발 시작점을 설명한다.
- [개요](backend/개요.md), [시스템 아키텍처](backend/시스템-아키텍처.md), [도메인 설명](backend/도메인-설명.md)은 서비스 전체 흐름과 DB 구조를 설명한다.
- [운영 가이드](backend/운영-가이드.md), [인증·보안](backend/인증-보안.md), [외부 연동](backend/외부-연동.md), [Redis 키 카탈로그](backend/Redis-키-카탈로그.md), [에러 코드 카탈로그](backend/에러-코드-카탈로그.md)는 운영과 장애 분석에 필요한 참고 문서다.

즉, "승인을 누르면 backend 안에서 무슨 일이 일어나는가"를 이해하는 데 필요한 내용이 여기 있다. 승인 이후 실제 계정과 Pod를 만드는 부분은 `infra`에서 이어서 본다.

### [infra](infra/index.md)

`infra`는 config-server 문서다. 승인된 사용자를 위해 실제 계정과 Pod를 어떤 순서로 만들고, 그 과정에서 포트, DB, Kerberos, Helm 설정이 어떻게 연결되는지 여기서 본다.

- [개요](infra/개요.md)는 config-server가 시스템에서 맡는 역할과 큰 흐름을 설명한다.
- [시스템 아키텍처](infra/design/시스템-아키텍처.md)는 계정, 홈 디렉터리, Pod, NodePort가 만들어지는 실제 순서를 설명한다.
- [기초 개념](infra/design/기초-개념.md), [데이터베이스](infra/design/데이터베이스.md)는 본문을 읽기 위한 배경지식과 포트 기록 구조를 정리한다.
- [운영 매뉴얼](infra/operations/운영-매뉴얼.md), [API 레퍼런스](infra/operations/API-레퍼런스.md), [Helm 차트 레퍼런스](infra/operations/Helm-차트-레퍼런스.md)는 운영, 디버깅, 배포 변경에 필요한 문서다.
- [kdc-setup](infra/kdc-setup/index.md)은 Kerberos와 AD 관련 흐름만 따로 묶어서 설명한다.

즉, "승인 결과가 실제 서버 자원 생성으로 어떻게 바뀌는가"를 이해하는 데 필요한 내용이 여기 있다. 그 아래 서버 설정과 운영 절차는 `system`에서 더 자세히 본다.

### [system](system/index.md)

`system`은 GPU 서버 운영 문서다. 어떤 서버 구성을 표준으로 보는지, 사용자 컨테이너 이미지를 어떻게 관리하는지, 서버 상태를 어떻게 수집하는지, 원격 부팅은 어떻게 하는지, Kerberos와 NFS는 어떻게 설정하는지를 여기서 다룬다.

- [server-state](system/server-state/index.md)는 서버에 기본으로 맞춰야 하는 설정과 점검 항목을 설명한다.
- [container-images](system/container-images/index.md)는 사용자 컨테이너 이미지와 시작 환경을 설명한다.
- [monitoring](system/monitoring/index.md)는 GPU, 컨테이너, 서비스 상태를 어떻게 수집하고 확인하는지 설명한다.
- [remote-operations](system/remote-operations/index.md)는 서버 전원을 원격으로 켜고 부팅 직후 무엇을 확인하는지 설명한다.
- [kerberos-nfs](system/kerberos-nfs/index.md)는 AD 로그인, Kerberos 인증, NFS 공유 디렉터리 연결을 어떻게 맞추는지 설명한다.

### [user](user/index.md)

`user`는 학생과 연구원이 실제로 사용하는 절차를 설명하는 문서다. 운영자가 사용자 입장에서 무엇이 보이고 어떤 절차를 따라가는지 확인할 때도 이쪽 문서를 보면 된다.

- [LAB & FARM 유저 매뉴얼](user/LAB-FARM-유저-매뉴얼.md)은 전체 사용 절차를 설명한다.
- [AI LAB 홈페이지 이용 방법](user/AI-LAB-홈페이지-이용-방법.md)은 웹 UI 사용법을 설명한다.
- [서버 내 파일 백업하기](user/서버-내-파일-백업하기.md)은 사용자 데이터 보존 측면을 설명한다.

### [PDF 다운로드](downloads.md)

`downloads`는 각 영역 문서의 PDF를 모아 둔 페이지다. 인쇄하거나 공유할 때 보면 된다.

## 상황별 출발점

| 하고 싶은 일 | 먼저 볼 문서 | 이어서 볼 문서 |
| --- | --- | --- |
| 새 관리자로 전체 구조를 익힌다 | [backend 개요](backend/개요.md) | [infra 개요](infra/개요.md), [system 목차](system/index.md) |
| 승인 뒤 계정과 Pod가 어떻게 만들어지는지 본다 | [infra 개요](infra/개요.md) | [infra 시스템 아키텍처](infra/design/시스템-아키텍처.md), [API 레퍼런스](infra/operations/API-레퍼런스.md) |
| 운영 중 장애를 점검한다 | [infra 운영 매뉴얼](infra/operations/운영-매뉴얼.md) | [infra 데이터베이스](infra/design/데이터베이스.md), [system monitoring](system/monitoring/index.md) |
| Kerberos와 NFS 흐름을 본다 | [infra kdc-setup](infra/kdc-setup/index.md) | [system kerberos-nfs](system/kerberos-nfs/index.md) |

## 처음 보는 사람을 위한 추천 순서

1. [backend 개요](backend/개요.md)에서 서비스가 왜 필요한지와 승인 흐름을 먼저 읽는다.
2. [infra 개요](infra/개요.md)와 [infra 시스템 아키텍처](infra/design/시스템-아키텍처.md)에서 승인 뒤 실제 계정과 Pod가 어떻게 만들어지는지 읽는다.
3. [system 목차](system/index.md)에서 서버 운영을 어떤 모듈로 쪼개 관리하는지 보고, 필요한 모듈로 내려간다.
4. Kerberos와 스토리지까지 이어지는 경로가 필요하면 [infra kdc-setup](infra/kdc-setup/index.md)과 [system kerberos-nfs](system/kerberos-nfs/index.md)를 함께 본다.
