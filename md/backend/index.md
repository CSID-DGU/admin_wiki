# Backend

DGU AI LAB Admin Backend(Spring Boot) 유지보수를 위한 기술 문서입니다. 신청 접수·승인, 인증, Redis 연동, 스케줄러, Infra Server 연동까지 BE 코드가 하는 일과 그 이유를 다룹니다.

GitHub 레포: [CSID-DGU/admin_be](https://github.com/CSID-DGU/admin_be)

## 읽는 순서 (온보딩)

처음 합류했다면 아래 순서대로 읽습니다. 순서는 임의로 나열한 것이 아니라 "환경을 갖춘다 → 왜 필요한지 안다 → 무슨 일이 일어나는지 안다 → 데이터가 어떻게 생겼는지 안다 → 코드를 어떻게 쓰는지 안다 → 반복되는 함정을 안다"는 이해의 흐름을 따릅니다. 뒤 문서일수록 앞 문서에서 나온 개념(Request 상태, 스케줄러 등)을 이미 안다고 가정하고 설명합니다.

| 순서 | 문서 | 다루는 내용 |
| --- | --- | --- |
| 1 | [시작](시작.md) | 로컬 개발 환경 세팅. IntelliJ, `application.yml`, 로컬 DB, Swagger 확인까지의 절차 |
| 2 | [개요](개요.md) | 시스템의 목적, 전체 구조, 기술 스택, LAB·FARM 서버 환경 |
| 3 | [시스템 아키텍처](시스템-아키텍처.md) | Request 상태 전이, 회원가입부터 만료 처리까지 전체 흐름, 세 가지 스케줄러 |
| 4 | [도메인 설명](도메인-설명.md) | User·Request·ResourceGroup 등 주요 엔티티 구조와 ERD |
| 5 | [코드 컨벤션](코드-컨벤션.md) | 패키지 구조, 네이밍, 예외 처리, 테스트 작성 규칙 |
| 6 | [핵심 설계 패턴](핵심-설계-패턴.md) | AFTER_COMMIT, Self-Injection, SETNX 중복 방지, 보상 트랜잭션 등 코드 전반에 반복되는 패턴 |

## 참고자료 (상황별)

아래 문서들은 순서대로 읽기보다, 필요할 때 찾아보는 문서입니다.

| 문서 | 다루는 내용 | 이럴 때 읽으세요 |
| --- | --- | --- |
| [인증·보안](인증-보안.md) | JWT AccessToken/RefreshToken 구조, 로그인·재발급·로그아웃, 인증 필터, 역할 기반 접근 제어 | 로그인이 안 되거나 토큰 재발급 오류를 조사할 때 |
| [외부 연동](외부-연동.md) | Infra Server API 명세, WebClient 타임아웃 설정, 에러 처리와 보상 트랜잭션 연계, Prometheus 연동 | Infra Server와 통신하는 코드를 수정하거나 디버깅할 때 |
| [Redis 키 카탈로그](Redis-키-카탈로그.md) | BE가 쓰는 모든 Redis 키의 패턴·타입·TTL·저장/삭제 시점 | Redis 관련 버그를 조사하거나 새 키를 추가할 때 |
| [에러 코드 카탈로그](에러-코드-카탈로그.md) | 59개 ErrorCode 전체 목록과 발생 상황 | API 에러 메시지의 원인을 조사하거나 새 에러 케이스를 추가할 때 |
| [운영 가이드](운영-가이드.md) | 서버 접속, 배포 구조(CI/CD), GitHub Secrets, kubectl 명령어, 장애 대응, 메시지 템플릿 API, Redis 상태 확인 | 배포하거나 운영 중 장애에 대응할 때 |

## API

- Swagger: [http://210.94.179.18:30083/swagger-ui/index.html](http://210.94.179.18:30083/swagger-ui/index.html)
