# server-state 개요

`server-state`는 FARM/LAB GPU 서버의 공통 운영 기준을 정의하고, 각 서버가 해당
기준에 맞게 설정되어 있는지 점검하는 모듈이다. 구성요소별 설정 작업은 신규
서버를 같은 운영 기준에 맞게 구성할 때도 사용한다.

서버 상태는 OS 공통 패키지, Docker, NVIDIA, Kubernetes, storage network,
Kerberos/NFS와 monitoring으로 나뉜다. 각 구성요소에는 목표 상태, 점검 방법,
설정 방법, 실행 형태와 안전 수준이 연결되어 있다.

| 문서 | 내용 |
| --- | --- |
| [설계](design.md) | 목표, 구조, 구성요소별 상태·점검·설정, 실행 형태와 안전 수준, 설정값과 코드 위치 |
| [운영](operations.md) | 서버 등록, 환경 설정 변경, 구성요소 확장, 실행 제어 변경, 점검·설정과 검증 절차 |
