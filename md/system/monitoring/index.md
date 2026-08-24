# monitoring 개요

> [설계](design.md) · [운영](operations.md) · [GitHub](https://github.com/CSID-DGU/admin_infra_server)

`monitoring` 매뉴얼은 FARM/LAB 서버와 그 위에서 도는 service의 상태를 계속
지켜보는 방법을 설명한다. 서버 자원과 GPU, container, 공유 스토리지의 상태를 모아
그래프로 보여주고, 이상이 생기면 알림을 보내는 것까지가 이 모듈이 하는 일이다.

처음 보는 사람은 이 페이지에서 "어떤 매뉴얼을 먼저 읽어야 하는지"를 잡고, 각 매뉴얼
안에서 세부 내용을 내려가면 된다.

## monitoring이 무엇을 하나

`monitoring`은 **각 서버에 상태를 수집하는 프로그램을 설치해
두고, 수집한 값을 한곳에 모아 저장한 뒤, 그래프로 보여주고 이상 상태면 알림을
보낸다.**

수집·저장·조회·알림은 각각 다른 프로그램이 담당한다. 어떤 프로그램이 무엇을 맡고
서로 어떻게 연결되는지는 [설계](design.md) 2장에 있다.

## 상황별로 볼 곳

| 상황 | 확인할 매뉴얼 |
| --- | --- |
| 그래프로 서버 상태를 보고 싶다 | [운영](operations.md) 9장 Grafana 점검 |
| 알림을 받았는데 무엇부터 확인해야 할지 모르겠다 | [운영](operations.md) 8장 Alert별 진단 순서 |
| 어떤 값이 어디에서 나오는지 찾고 싶다 | [운영](operations.md) 7장 무엇을 어디에서 보는가 |
| 서버를 새로 추가했다 | [운영](operations.md) 11장 새 서버 추가 체크리스트 |
| exporter나 Prometheus를 배포해야 한다 | [운영](operations.md) 1~5장 |
| 배포한 것이 제대로 떴는지 확인하고 싶다 | [운영](operations.md) 6장 배포 후 endpoint 확인 |
| 구조가 궁금하다 (Prometheus가 왜 FARM/LAB 두 개인지 등) | [설계](design.md) 2장 설계 구조 |
| 각 exporter가 정확히 무엇을 수집하는지 알고 싶다 | [설계](design.md) 3장 서버 metric 수집 |
| 명령이 서버 접속 단계에서 실패한다 | [Ansible 설정](../ansible/config.md) 8장 문제 해결 |

## 매뉴얼 읽기 순서

### 1. Ansible 설정을 먼저 마친다

배포 명령은 전부 Ansible로 서버에 접속한다.
[Ansible 설정](../ansible/config.md)이 끝나 있지 않으면 어떤 명령도 서버에 닿지
못한다. Ansible 자체가 낯설다면 [Ansible 기초 개념](../ansible/basic.md)을 먼저 본다.

### 2. 설계 매뉴얼에서 구조를 본다

- [설계](design.md)는 수집·저장·조회·알림을 담당하는 각 구성요소가 무엇을 입력받아
  무엇을 내놓는지 설명한다.
- FARM과 LAB에 Prometheus가 하나씩 있고 Grafana와 Alertmanager는 하나씩만 두는
  이유(2장), exporter 세 개가 각각 무엇을 보는지(3장)가 여기 있다.

### 3. 운영 매뉴얼에서 배포와 점검 절차를 따라간다

- [운영](operations.md)은 배포 순서, endpoint 확인, 알림이 왔을 때의 진단 순서를
  다룬다.
- 설계 매뉴얼이 "무엇을 어떻게 수집하는지"를 설명한다면, 운영 매뉴얼은 "그래서
  실제로 어떻게 배포하고 확인하는지"를 설명한다.
- `D-state`, `forensics`, `canary`처럼 진단에 쓰이는 용어는 운영 매뉴얼 앞머리의
  "운영 원칙"에 정리되어 있다.

## 매뉴얼 지도

| 매뉴얼 | 역할 | 여기서 이해하는 내용 |
| --- | --- | --- |
| 개요 (현재 페이지) | 출발점 | monitoring이 하는 일, 매뉴얼 읽는 순서 |
| [설계](design.md) | 개념·구조 | 구성요소별 역할과 입력·처리·출력, FARM/LAB Prometheus 구성, 주요 설정과 코드 위치 |
| [운영](operations.md) | 실행 절차 | exporter와 monitoring stack 배포, endpoint 확인, alert 진단, 새 서버 추가 |

## 이 매뉴얼이 다루는 범위

- 서버와 service의 상태를 **수집·저장·조회하고 알림을 보내는 것**까지 다룬다.
  상태를 읽어서 보여주는 것이 목적이고, 서버 설정을 바꾸는 것은 목적이 아니다.
- 서버가 공통 운영 기준에 맞게 설정되어 있는지 점검하고 고치는 일은 다루지 않는다.
  [server-state](../server-state/index.md) 참고.
- 부팅 시점에 한 번 수행하는 점검과 복구는 다루지 않는다.
  [remote-operations](../remote-operations/index.md) 참고.
- Kerberos 인증과 NFS mount 자체의 구조는 다루지 않는다.
  [Kerberos/NFS 설계](../kerberos-nfs/design.md) 참고.
- Ansible 접속 설정은 이 모듈이 갖지 않는다. [Ansible 설정](../ansible/config.md) 참고.
- DB 비밀번호, Grafana 비밀번호, webhook 주소 같은 실제 값은 적지 않는다. 어디에서
  관리하는지와 확인 방법만 적는다.
