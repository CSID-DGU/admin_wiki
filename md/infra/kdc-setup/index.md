# kdc-setup

> 역할: config-server가 FARM AD 사용자 신원, 사용자 keytab, 선택 노드의 ccache,
> Kerberos NFS 홈을 연결하는 인프라 경계를 설명한다.

`kdc-setup`은 Kubernetes의 config-server 경로를 위한 문서다. 범용 NFS service
keytab, NAS KVNO, 다른 컨테이너 런타임의 운영 기준은
[System Kerberos/NFS](../../system/kerberos-nfs/index.md)에서 다룬다.

## 문서 구성

| 문서 | 읽어야 하는 경우 | 핵심 내용 |
| --- | --- | --- |
| 현재 페이지 | 전체 역할과 문서 위치를 빠르게 확인할 때 | 책임 범위, 전환 상태, 문서 경계 |
| [설계](design.md) | 계정·Pod·자격 증명 흐름을 이해할 때 | AD, Secret, 선택 노드, ccache, NFS의 관계 |
| [운영](operations.md) | 점검·장애 대응·노드 추가가 필요할 때 | 안전한 점검 순서, 사용자 생명주기, 복구 기준 |
| [설정](config.md) | 배포 설정의 소유자와 변경 방법을 확인할 때 | Helm·CI·Kubernetes Secret의 주입 경로와 검증 |

## 한눈에 보는 흐름

```text
승인 시스템
   -> config-server
      -> FARM AD DC: 사용자·전용 그룹·RFC2307·keytab
      -> Kubernetes Secret: 사용자 keytab 보관
      -> 선택된 FARM 노드: root-only keytab·refresh timer·ccache
      -> 사용자 Pod: keytab 없이 ccache와 FARM 홈을 사용
```

## 책임 경계

- config-server는 계정·Pod 수명주기와 제한된 AD·노드 관리 요청을 조정한다.
- AD는 사용자, 전용 그룹, RFC2307 UID/GID와 사용자 keytab을 제공한다.
- 선택 노드는 keytab을 root 전용으로 보관하고 사용자 ccache를 갱신한다.
- Pod는 장기 자격 증명인 keytab을 받지 않고 ccache만 사용한다.
- NAS 홈 생성·삭제는 Kerberos 관리 채널과 분리된 경로가 담당한다.
- 비밀 값과 변경 이력은 관리자 전용 시크릿·배포 설정 문서에서 별도로 관리한다.

## 전환 상태

신규 계정과 신규 Pod의 기준은 FARM AD 경로다. 전환 전에 생성된 Pod는 재생성
전까지 이전 Realm이나 이전 홈 마운트를 유지할 수 있다. 이전 Pod를 새 경로의
파일·timer로 덮어쓰지 말고, Pod 환경과 hostPath를 확인한 뒤 재생성 계획으로
전환한다.

## 관련 문서

- [System Kerberos/NFS](../../system/kerberos-nfs/index.md): 공통 Kerberos NFS와 NAS service 경계
- [System container-images](../../system/container-images.md): 이미지의 ccache 소비 경계
- [설정](config.md): config-server 배포 설정의 주입·검증 기준
