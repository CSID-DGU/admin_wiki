# Infra

`infra` 문서는 config-server(코드는 `admin_infra-proposed`)를 중심으로, 승인 결과가 실제 계정·홈 디렉터리·Pod·NodePort로 이어지고 회수·이동·변경되는 과정을 설명한다. 내용은 v3.3.71 코드 기준이다.

처음 보는 사람은 이 페이지에서 "어떤 문서를 먼저 읽어야 하는지"를 잡고, 각 문서 안에서 세부 내용을 내려가면 된다.

## 어디부터 보면 되나

| 상황 | 먼저 볼 문서 | 이어서 볼 문서 |
| --- | --- | --- |
| config-server가 시스템에서 무슨 일을 하는지 먼저 이해하고 싶다 | [개요](개요.md) | [시스템 아키텍처](design/시스템-아키텍처.md) |
| 승인·회수·이동 등 작업이 실제로 어떤 단계를 거치는지 궁금하다 | [시스템 아키텍처](design/시스템-아키텍처.md) | [데이터베이스](design/데이터베이스.md), [API 레퍼런스](operations/API-레퍼런스.md) |
| Kubernetes, UID/GID, NFS, NodePort 같은 용어가 낯설다 | [기초 개념](design/기초-개념.md) | 다시 [시스템 아키텍처](design/시스템-아키텍처.md) |
| 배포, 점검, 장애 대응 절차를 확인해야 한다 | [운영 매뉴얼](operations/운영-매뉴얼.md) | [Helm 차트 레퍼런스](operations/Helm-차트-레퍼런스.md), [데이터베이스](design/데이터베이스.md) |
| 자원이 남거나 상태가 어긋나는 지점(무결성·정합성)을 확인해야 한다 | [무결성·정합성 점검](design/무결성-정합성-점검.md) | [시스템 아키텍처](design/시스템-아키텍처.md) |
| API 입력과 응답을 바로 확인해야 한다 | [API 레퍼런스](operations/API-레퍼런스.md) | [시스템 아키텍처](design/시스템-아키텍처.md) |
| Kerberos와 AD, keytab 흐름을 따로 봐야 한다 | [kdc-setup](kdc-setup/index.md) | [설계](kdc-setup/design.md), [운영](kdc-setup/operations.md) |

## 문서는 이런 순서로 이어진다

### 1. 역할과 전체 흐름을 먼저 본다

- [개요](개요.md)는 config-server가 전체 시스템에서 맡는 역할을 설명한다.
- `admin_be`가 어떤 작업을 등록하고, config-server가 실제로 무엇을 바꾸는지, 어느 스택에 떠 있는지 여기서 먼저 잡는다.

### 2. 실제 생성 순서를 중심 문서에서 본다

- [시스템 아키텍처](design/시스템-아키텍처.md)는 작업 등록과 제어기, 여덟 가지 작업 종류의 단계, 실패했을 때 남는 것과 되돌리는 것을 설명한다.
- 이 문서가 `infra` 문서 묶음의 중심이다. 나머지 문서는 이 흐름을 이해하거나 운영하는 데 필요한 설명을 덧붙인다.

### 3. 막히는 용어와 기록 구조를 보충한다

- [기초 개념](design/기초-개념.md)은 UID/GID, Kubernetes, NFS, NodePort 같은 용어를 설명한다.
- [데이터베이스](design/데이터베이스.md)는 스택 DB의 포트 배정·작업 이력·작업 소유권 테이블과 백업을 설명한다.

생성 순서는 아키텍처 문서에서 보고, 용어나 기록 구조는 이 두 문서에서 보충하면 된다.

### 4. 운영 문서와 참조 문서로 내려간다

- [운영 매뉴얼](operations/운영-매뉴얼.md)은 operation 스택의 배포, 점검, 장애 대응, 복구 순서를 설명한다.
- [API 레퍼런스](operations/API-레퍼런스.md)는 config-server 엔드포인트의 입력과 응답을 설명한다.
- [Helm 차트 레퍼런스](operations/Helm-차트-레퍼런스.md)는 배포할 때 어떤 값을 바꾸고, 그 값이 어느 리소스에 들어가는지 설명한다.

운영자는 보통 `개요 -> 시스템 아키텍처 -> 운영 매뉴얼` 순서로 읽고, API나 배포값이 필요할 때 옆 문서를 같이 본다.

### 5. Kerberos는 따로 묶어서 본다

- [kdc-setup](kdc-setup/index.md)은 AD, Secret, keytab, ccache, NFS 경로를 따로 묶은 문서다.
- Kerberos는 보안 규칙과 운영 절차가 따로 많아서 일반 흐름 문서와 분리해 두었다.
- Kerberos 이슈를 볼 때는 `kdc-setup 개요 -> 설계 -> 운영 -> 설정` 순서로 읽으면 된다.

## 문서 지도

| 문서 | 역할 | 여기서 이해하는 내용 | 보통 이어서 보는 문서 |
| --- | --- | --- | --- |
| [개요](개요.md) | 출발점 | config-server의 역할, 작업 종류, 관련 저장소, 배포 위치 | [시스템 아키텍처](design/시스템-아키텍처.md) |
| [시스템 아키텍처](design/시스템-아키텍처.md) | 중심 문서 | 작업 종류별 단계, 실행 방식, 계정·포트 번호 규칙 | [데이터베이스](design/데이터베이스.md), [API 레퍼런스](operations/API-레퍼런스.md) |
| [기초 개념](design/기초-개념.md) | 배경지식 보충 | UID/GID, 계정 파일, Kubernetes, NFS, NodePort 같은 개념 | 다시 본문 문서 |
| [데이터베이스](design/데이터베이스.md) | 기록 구조 보충 | 스택 DB, 포트 배정·작업 이력 테이블, 잠금, 백업 | [운영 매뉴얼](operations/운영-매뉴얼.md) |
| [무결성·정합성 점검](design/무결성-정합성-점검.md) | 점검 결과 | 고아 자원·상태 불일치가 생기는 지점과 책임 경계 | [시스템 아키텍처](design/시스템-아키텍처.md) |
| [처음 작업할 때](operations/시작.md) | 작업 시작 안내 | 브랜치 규칙, 테스트, 실험 스택·E2E, PR 흐름 | [운영 매뉴얼](operations/운영-매뉴얼.md) |
| [운영 매뉴얼](operations/운영-매뉴얼.md) | 운영 지침 | 점검, 배포, 오류 대응, 복구 순서 | [데이터베이스](design/데이터베이스.md), [Helm 차트 레퍼런스](operations/Helm-차트-레퍼런스.md) |
| [API 레퍼런스](operations/API-레퍼런스.md) | API 참고 | 작업 등록·결과·단계 기록 API의 입력, 응답, 호출 주체 | [시스템 아키텍처](design/시스템-아키텍처.md) |
| [Helm 차트 레퍼런스](operations/Helm-차트-레퍼런스.md) | 배포 구조 참고 | Helm values, 템플릿, Secret, 스택 설치가 덮어쓰는 값 | [운영 매뉴얼](operations/운영-매뉴얼.md) |
| [kdc-setup](kdc-setup/index.md) | Kerberos 전용 목차 | AD, Secret, 노드, Pod 사이의 Kerberos 흐름 전체 | [설계](kdc-setup/design.md), [운영](kdc-setup/operations.md) |

## 이 문서가 다루는 범위

- `infra`는 config-server가 직접 만들고 바꾸고 지우는 계정, 홈 디렉터리, Pod, NodePort, Kerberos 준비를 다룬다.
- NAS service keytab, NFS 서버 자체 설정, 사용자 이미지 내부 동작처럼 다른 묶음이 더 적합한 내용은 `system` 문서로 보낸다.
- 실제 값, 비밀번호, keytab, SSH 개인키는 여기서 설명하지 않고 운영 확인 절차와 위치만 적는다.
