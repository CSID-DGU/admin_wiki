# kdc-setup

> config-server가 FARM AD 계정, 사용자 keytab, 노드 ccache, Kerberos NFS 홈을 어떻게 연결하는지 설명한다.

`kdc-setup`은 config-server가 사용자 Pod를 만들 때 쓰는 Kerberos 설정 문서다. NAS service keytab, NAS KVNO, 다른 컨테이너 환경의 Kerberos 설정은
[System Kerberos/NFS](../../system/kerberos-nfs/index.md)에서 다룬다.

## 문서 안내

| 문서 | 읽어야 하는 경우 | 핵심 내용 |
| --- | --- | --- |
| 현재 페이지 | 문서의 역할을 먼저 볼 때 | AD, Secret, 노드, Pod가 이어지는 순서 |
| [설계](design.md) | 계정과 Pod를 만들 때 어떤 파일이 필요한지 볼 때 | AD, Secret, 선택 노드, ccache, NFS |
| [운영](operations.md) | 점검, 장애 대응, 노드 추가를 할 때 | 확인 순서와 명령 |
| [설정](config.md) | Helm, CI, Secret 설정을 바꿀 때 | 값이 들어가는 곳과 확인 방법 |

## 계정부터 Pod까지의 순서

```text
승인 시스템
   -> config-server
      -> FARM AD DC: 사용자·전용 그룹·RFC2307·keytab
      -> Kubernetes Secret: 사용자 keytab 보관
      -> 선택된 FARM 노드: root-only keytab·refresh timer·ccache
      -> 사용자 Pod: keytab 없이 ccache와 FARM 홈을 사용
```

## 누가 무엇을 하나

- config-server는 계정과 Pod 생성·삭제를 요청하고 AD와 노드 관리 명령을 실행한다.
- AD는 사용자, 전용 그룹, RFC2307 UID/GID, 사용자 keytab을 만든다.
- 선택된 노드는 keytab을 root만 읽을 수 있는 경로에 두고 사용자 ccache를 갱신한다.
- Pod는 keytab을 받지 않고 ccache만 사용한다.
- NAS 홈 디렉터리 생성·삭제는 NAS 관리 경로에서 처리한다.
- 비밀 값과 변경 이력은 관리자 전용 시크릿과 배포 설정 문서에만 둔다.

## 이전 Pod 처리

새 계정과 새 Pod는 FARM AD 설정을 사용한다. 전환 전에 만든 Pod는 다시 만들기 전까지 이전 Realm이나 홈 마운트를 쓸 수 있다. 이전 Pod에 새 keytab이나 timer 파일을 덮어쓰지 말고, 현재 Pod의 환경 변수와 hostPath를 확인한 뒤 다시 만든다.

## 관련 문서

- [System Kerberos/NFS](../../system/kerberos-nfs/index.md): NAS와 NFS의 Kerberos 설정
- [System container-images](../../system/container-images/index.md): 이미지가 ccache를 쓰는 방식
- [설정](config.md): config-server 배포 설정과 확인 방법
