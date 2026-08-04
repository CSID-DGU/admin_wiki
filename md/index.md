# 운영 위키

DGU AI LAB의 GPU 서버 자동화 시스템을 유지보수·운영하기 위한 문서 모음입니다. 학생이 서버 사용을 신청하면 Admin BE가 승인을 처리하고, 승인이 나면 Infra Server가 실제 Ubuntu 계정과 컨테이너를 만들며, 그 아래 물리 서버와 클러스터는 System 영역이 지탱합니다. 지금 다루려는 문제가 이 네 층 중 어디에 속하는지에 따라 들어갈 섹션이 갈립니다.

## 목차

<div class="main-toc" markdown>

| 섹션 | 이 섹션이 하는 일 | 이럴 때 들어가세요 |
| --- | --- | --- |
| [`backend`](backend/index.md) | 신청을 받아 승인을 처리하고, 인증·알림·스케줄러까지 돌리는 Admin BE(Spring Boot) 서버 코드를 다룸 | 신청·승인 로직, API, 인증, 알림 발송을 고치거나 조사할 때 |
| [`infra`](infra/index.md) | BE의 요청을 받아 실제로 Ubuntu 계정을 만들고 K8s Pod를 띄우는 Infra Server 코드를 다룸 | 계정·Pod가 실제로 만들어지는 과정, NodePort 배정을 다룰 때 |
| [`system`](system/index.md) | GPU 서버 자체를 세팅하고 지키는 운영 스크립트를 다룸(공통 설정, container image, 원격 부팅, 모니터링, AD/Kerberos) | 서버 하드웨어·OS·네트워크 레벨 문제나 신규 서버 구축을 다룰 때 |
| [`user`](user/index.md) | 이 시스템을 실제로 쓰는 학생·연구원을 위한 사용 안내를 다룸 | 개발자가 아니라 사용자에게 사용법을 안내할 때 |

</div>
