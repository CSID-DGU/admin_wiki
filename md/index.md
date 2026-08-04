# 운영 위키

DGU AI LAB GPU 서버 자동화 시스템을 유지보수·운영하기 위한 문서 모음입니다. 시스템은 사용자가 신청하면(User) → Admin BE가 승인 처리하고(Backend) → Infra Server가 실제 계정·컨테이너를 만들고(Infra) → 그 위 물리 서버와 클러스터를 System 영역이 지탱하는 구조입니다. 무엇을 고치려는지에 따라 아래 네 섹션 중 하나로 들어갑니다.

## 목차

<div class="main-toc" markdown>

| 섹션 | 이 섹션이 다루는 대상 | 이럴 때 들어가세요 |
| --- | --- | --- |
| [`backend`](backend/index.md) | Admin BE(Spring Boot) 애플리케이션 코드. 신청 접수·승인, 인증, 알림, 스케줄러 | 신청/승인 로직, API, 인증, 알림 발송을 고치거나 조사할 때 |
| [`infra`](infra/index.md) | BE가 호출하는 Infra Server(config-server) 코드. Ubuntu 계정·K8s Pod 생성·삭제 | 계정이나 Pod가 실제로 만들어지는 과정, NodePort 배정을 다룰 때 |
| [`system`](system/index.md) | GPU 서버 자체의 운영 스크립트. 공통 설정, container image, 원격 부팅, 모니터링, AD/Kerberos | 서버 하드웨어·OS·네트워크 레벨 문제나 신규 서버 구축을 다룰 때 |
| [`user`](user/index.md) | 학생·연구원을 위한 사용 안내. 신청 방법, 홈페이지 이용, 접속, 백업 | 개발이 아니라 최종 사용자에게 사용법을 안내할 때 |

</div>
