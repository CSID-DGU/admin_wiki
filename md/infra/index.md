# Infra

## 개요

이 문서는 연구실 GPU 서버에서 사용자 Pod를 만들고 운영하는 데 필요한 내용을 모아 둔 곳이다. Kubernetes, 계정, NAS 홈 디렉터리, Kerberos, NodePort를 다룬다.

## 목차

| 구분 | 문서 | 먼저 읽을 때 |
| --- | --- | --- |
| 처음 보기 | [개요](개요.md) | config-server가 하는 일을 먼저 볼 때 |
| 동작 방식 | [시스템 아키텍처](design/시스템-아키텍처.md) | 계정, Pod, GPU 노드, 포트가 만들어지는 순서를 볼 때 |
| 배경 지식 | [기초 개념](design/기초-개념.md) | Kubernetes, NFS, 네트워크 용어를 확인할 때 |
| 포트 DB | [데이터베이스](design/데이터베이스.md) | NodePort 기록과 DB 복구 방법을 확인할 때 |
| 개발 시작 | [처음 작업할 때](operations/시작.md) | 로컬 실행, 브랜치, 배포 방법을 확인할 때 |
| 운영 | [운영 매뉴얼](operations/운영-매뉴얼.md) | 점검, 배포, 장애 대응을 할 때 |
| API | [API 레퍼런스](operations/API-레퍼런스.md) | config-server 요청과 응답을 확인할 때 |
| Helm | [Helm 차트 레퍼런스](operations/Helm-차트-레퍼런스.md) | Helm 값과 차트 파일을 바꿀 때 |
| Kerberos | [kdc-setup](kdc-setup/index.md) | FARM AD, Kerberos, NFS 설정을 점검할 때 |
