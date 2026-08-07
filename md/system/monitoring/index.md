# monitoring

`monitoring`은 FARM/LAB 서버의 자원, GPU, container, 공유 스토리지와 주요 service
상태를 지속적으로 수집하고 metric, dashboard와 alert로 제공한다. 서버에서 수집한
상태는 Prometheus에 저장되며, Grafana에서 조회하고 Alertmanager를 통해 운영
알림으로 전달한다.

NFS 인증 상태와 장애 증거 수집, 제한된 복구 작업도 같은 metric 체계에 연결되어
있다. 각 기능은 독립된 service와 state file로 실행되고 exporter가 결과를 읽어
Prometheus에 제공한다.

| 문서 | 내용 |
| --- | --- |
| [설계](design.md) | monitoring의 목표와 구조, 구성요소별 역할·입력·처리·출력, 주요 설정과 코드 위치 |
| [운영](operations.md) | exporter와 monitoring stack 배포, endpoint 확인, 장애 진단과 변경 검증 절차 |
