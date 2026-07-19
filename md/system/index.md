# System

## 개요

System 영역은 **DECS GPU 서버와 사용자 container를 일관된 상태로 운영하기
위한 시스템 관리 코드**를 담당한다. 새로운 서버를 기존 서버와 같은 설정으로
구축하고, 사용자가 사용할 container와 image를 관리하며, 서버 전원부터
monitoring과 공유 storage 접근까지 운영에 필요한 전체 흐름을 유지하는 것이
목적이다.

주요 담당 범위는 다음과 같다.

- 모든 GPU 서버의 Docker, NVIDIA, Kubernetes와 network 공통 설정을 점검하고
  신규 서버에도 같은 기준을 적용한다.
- 사용자 container의 생성·수정·삭제와 공통 container image를 관리한다.
- 서버 원격 부팅과 부팅 순서를 관리하여 사용자 관리 DB와 GPU 서버가 올바른
  순서로 준비되도록 한다.
- 서버, GPU, container와 사용자 상태를 수집하여 장애와 이상 상태를 관측한다.
- AD/Kerberos 인증을 사용해 사용자가 NAS/NFS 공유 storage에 안전하게
  접근하도록 한다.

즉, Backend나 Frontend 애플리케이션 기능이 아니라 **GPU 서버에서 사용자
작업 환경이 실제로 생성되고, 실행되고, 관측되고, storage에 연결되는 운영
기반**을 관리하는 영역이다.

## 목차

| 구성요소 | 상세 문서 | PDF |
| --- | --- | --- |
| 전체 통합 매뉴얼 | - | [PDF 열기](../../pdf/system/server-manage-manual.pdf) |
| 전체 구조 | 현재 페이지 | [PDF 열기](../../pdf/system/server-manage-index.pdf) |
| `container-images/` | [문서 열기](container-images.md) | [PDF 열기](../../pdf/system/container-images-manual.pdf) |
| `user-lifecycle/` | [문서 열기](user-lifecycle.md) | [PDF 열기](../../pdf/system/user-lifecycle-manual.pdf) |
| `server-state/` | [문서 열기](server-state.md) | [PDF 열기](../../pdf/system/server-state-manual.pdf) |
| `remote-operations/` | [문서 열기](remote-operations/index.md) | [PDF 열기](../../pdf/system/remote-operations-manual.pdf) |
| `monitoring/` | [문서 열기](monitoring/index.md) | [PDF 열기](../../pdf/system/monitoring-manual.pdf) |
| `kerberos-nfs/` | [문서 열기](kerberos-nfs/index.md) | [PDF 열기](../../pdf/system/kerberos-nfs-manual.pdf) |
