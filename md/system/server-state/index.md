# server-state

`server-state`는 FARM/LAB GPU 서버가 따라야 할 공통 운영 상태를 정의하고,
운영 서버 점검과 신규 서버 구성을 같은 기준과 순서로 수행하는 모듈이다.

서버 상태는 OS 공통 패키지, Docker, NVIDIA, Kubernetes, storage network,
Kerberos/NFS, monitoring, 사용자 container 전제조건으로 나뉜다. 각 구성요소에는
목표 상태와 담당 모듈, 점검 방법, 구성 방법, 적용 안전 수준이 연결되어 있다.
따라서 관리자는 전체 기준을 한곳에서 선택하되, 실제 작업은 해당 영역을
소유하는 Ansible role이나 playbook에서 수행한다.

| 문서 | 내용 |
| --- | --- |
| [설계](design.md) | 해결하려는 문제, 정책과 구성요소 구조, 소유권, 설정값 결정 방식, 코드 위치 |
| [운영](operations.md) | 대상과 구성요소 확인, 운영 서버 점검, 신규 서버 계획·적용, 결과 해석, 테스트 |
