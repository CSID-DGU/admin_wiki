# Infra

이 묶음은 `admin_infra`의 config-server가 계정, 홈 디렉터리, Pod, NodePort, Kerberos를 어떻게 다루는지 설명한다. 처음 보는 사람도 어디서 시작해야 할지 바로 잡을 수 있게, 읽는 목적별 경로와 문서 지도를 함께 둔다.

## 먼저 읽을 길

| 지금 하려는 일 | 추천 순서 |
| --- | --- |
| 처음 합류해서 전체를 훑는다 | [개요](개요.md) → [시스템 아키텍처](design/시스템-아키텍처.md) → [운영 매뉴얼](operations/운영-매뉴얼.md) |
| 승인 뒤 무슨 작업이 일어나는지 본다 | [개요](개요.md) → [시스템 아키텍처](design/시스템-아키텍처.md) → [API 레퍼런스](operations/API-레퍼런스.md) |
| 배포나 장애 대응을 한다 | [운영 매뉴얼](operations/운영-매뉴얼.md) → [데이터베이스](design/데이터베이스.md) → [Helm 차트 레퍼런스](operations/Helm-차트-레퍼런스.md) |
| 용어가 낯설다 | [기초 개념](design/기초-개념.md) → 필요한 본문 문서 |
| Kerberos, AD, keytab 흐름을 본다 | [kdc-setup](kdc-setup/index.md) → [설계](kdc-setup/design.md) → [운영](kdc-setup/operations.md) |

## 문서 지도

| 묶음 | 문서 | 이 문서에서 보는 것 | 다음에 읽을 문서 |
| --- | --- | --- | --- |
| 입문 | [개요](개요.md) | config-server가 시스템에서 맡는 역할과 큰 흐름 | [시스템 아키텍처](design/시스템-아키텍처.md) |
| 설계 | [시스템 아키텍처](design/시스템-아키텍처.md) | 계정, 홈 디렉터리, Pod, NodePort가 만들어지는 순서 | [데이터베이스](design/데이터베이스.md), [API 레퍼런스](operations/API-레퍼런스.md) |
| 설계 | [기초 개념](design/기초-개념.md) | UID/GID, Kubernetes, NFS, NodePort 같은 배경 용어 | 필요한 본문 문서 |
| 설계 | [데이터베이스](design/데이터베이스.md) | infra-mysql과 NodePort 배정 기록 구조 | [운영 매뉴얼](operations/운영-매뉴얼.md) |
| 작업 시작 | [처음 작업할 때](operations/시작.md) | 브랜치, 로컬 실행, 배포 흐름, PR 규칙 | [운영 매뉴얼](operations/운영-매뉴얼.md) |
| 운영 | [운영 매뉴얼](operations/운영-매뉴얼.md) | 배포, 상태 점검, 장애 확인, 복구 순서 | [데이터베이스](design/데이터베이스.md), [Helm 차트 레퍼런스](operations/Helm-차트-레퍼런스.md) |
| 운영 | [API 레퍼런스](operations/API-레퍼런스.md) | config-server 엔드포인트, 입력, 응답, 호출 주체 | [시스템 아키텍처](design/시스템-아키텍처.md) |
| 운영 | [Helm 차트 레퍼런스](operations/Helm-차트-레퍼런스.md) | Helm values와 차트 템플릿이 어디에 쓰이는지 | [운영 매뉴얼](operations/운영-매뉴얼.md) |
| Kerberos | [kdc-setup](kdc-setup/index.md) | AD, Secret, 노드, Pod 사이의 Kerberos 흐름 전체 | [설계](kdc-setup/design.md), [운영](kdc-setup/operations.md) |

## 이 묶음의 범위

- `infra`는 config-server가 직접 만드는 계정, 홈 디렉터리, Pod, NodePort, Kerberos 준비를 다룬다.
- NAS service keytab, NFS 서버 자체 설정, 사용자 이미지 내부 동작처럼 다른 묶음이 더 적합한 내용은 `system` 문서로 보낸다.
- 실제 값, 비밀번호, keytab, SSH 개인키는 여기서 설명하지 않고 운영 확인 절차와 위치만 적는다.
