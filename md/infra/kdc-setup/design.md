# kdc-setup 설계

> [개요](index.md) · [운영](operations.md) · [설정](config.md)

## 1. 이 설정에서 지킬 것

- FARM AD의 RFC2307 UID/GID와 NAS의 숫자 소유권을 같은 값으로 유지한다.
- 사용자 keytab은 Pod에 전달하지 않고, 선택 노드의 root 전용 경로에만 둔다.
- Pod를 실행하기 전에 해당 노드에서 사용자 TGT와 ccache 소유권을 검증한다.
- AD를 관리하는 접속과 노드를 관리하는 접속에 같은 키를 쓰지 않는다.
- NFS에서 D-state가 보이면 mount나 서비스를 반복해서 다시 시작하지 않는다.

## 2. 파일과 서비스가 있는 곳

```text
config-server
  ├─ AD 관리 채널 -> AD DC
  │    사용자 + <user>_gid + RFC2307 UID/GID + 사용자 keytab
  ├─ Kubernetes API -> Secret krb5-keytab-<user>
  └─ 노드 관리 채널 -> Pod가 배치될 FARM 노드 한 대
       /etc/decs-krb/keytabs/<user>.keytab   root-only
       decs-krb-refresh@<user>.timer
       /run/user/<uid>/krb5cc_ailab          사용자 소유
             └─ Pod는 ccache와 FARM 홈만 공유
```

AD 사용자와 Secret은 계정이 있는 동안 유지한다. 노드의 keytab, 환경 파일, timer, ccache는 Pod가 올라간 노드에서만 쓴다. Pod를 지우면 노드의 파일은 지우지만 AD 사용자와 Secret은 다음 Pod를 위해 남긴다.

## 3. 계정과 인증 파일

| 항목 | 위치 | 사용하는 곳 | 권한 |
| --- | --- | --- | --- |
| 사용자·전용 그룹 | FARM AD | config-server, winbind, NAS | RFC2307 UID/GID 일치 |
| 사용자 keytab | Kubernetes Secret | config-server | 관리자만 관리 |
| 노드 keytab | 선택된 FARM 노드 | root, refresh service | root 소유 `0400` |
| 갱신 환경 파일 | 선택된 FARM 노드 | refresh service | root 소유 `0400` |
| 사용자 ccache | `/run/user/<uid>/krb5cc_ailab` | Pod, 호스트 NFS 경로 | 사용자 UID/GID, `0600` |
| 머신 ccache | `/tmp/krb5cc_0` | rpc.gssd | 현재 노드 머신 principal 전용 |

`/tmp/krb5cc_0`에는 현재 노드의 머신 ticket만 둔다. 여기에 사용자 ticket이나 다른 Realm ticket을 넣으면 NFS 인증이 달라질 수 있다. 사용자 확인과 복구에는 별도 ccache를 사용한다.

## 4. 계정 생성부터 삭제까지

### 계정 생성

1. config-server가 UID/GID를 할당하고 계정 파일을 갱신한다.
2. NAS 관리 경로가 같은 숫자 소유권으로 홈 디렉터리를 준비한다.
3. AD 관리 채널이 사용자와 `<user>_gid` 그룹을 만들고 RFC2307 속성을 설정한다.
4. AD가 사용자 keytab을 발급하고 config-server가 Kubernetes Secret에 저장한다.

마지막 단계가 실패하면 계정 생성도 실패한다. NAS 홈과 계정 파일은 되돌리려고 하지만, AD 사용자·전용 그룹·Secret 일부가 남을 수 있다. 같은 이름으로 다시 만들기 전에는 이 세 곳을 확인한다.

### Pod 시작

1. config-server가 대상 FARM 노드를 선택한다.
2. Secret의 keytab을 해당 노드의 제한된 관리 채널로 전달한다.
3. 노드는 root 전용 keytab·환경 파일·`decs-krb-refresh@<user>.timer`를 준비한다.
4. refresh service가 사용자 TGT를 발급하고 ccache 소유권을 검증한다.
5. 검증에 성공할 때만 Pod가 ccache와 FARM 홈을 hostPath로 공유하며 시작한다.

### Pod·계정 삭제

Pod 삭제는 해당 노드의 timer, keytab, 환경 파일과 ccache를 정리한다. 계정 삭제는
AD 사용자와 Secret을 지우고 모든 FARM 노드에 사용자 keytab, timer, ccache 정리를 요청한다.
전용 그룹은 자동으로 지우지 않는다. 지울 필요가 있으면 운영 규칙을 확인한 뒤 따로 처리한다.

## 5. 접속 경로

| 접속 경로 | 대상 | 할 수 있는 일 |
| --- | --- | --- |
| AD 관리 채널 | AD DC | 사용자·전용 그룹 생성/삭제, keytab 발급 |
| 노드 관리 채널 | FARM 실행 노드 | keytab 배포·삭제, timer 제어, ccache 검증 |
| NAS 관리 채널 | NAS | 홈 생성·소유권 설정·삭제 |

각 접속 경로는 다른 키와 forced-command를 사용한다. AD를 수정하는 키로 모든 노드에 일반 셸 접속을 할 수 없게 한다.

## 6. 바꾸면 안 되는 규칙

1. 사용자 keytab을 Pod에 복사하거나 mount하지 않는다.
2. AD의 UID/GID, config-server 계정 파일, NAS 소유권을 따로 바꾸지 않는다.
3. Pod 시작 전에 대상 노드의 TGT와 ccache 소유권을 확인한다.
4. 머신 ccache에는 현재 노드의 머신 principal만 둔다.
5. D-state가 있는 노드에서 강제 unmount·반복 mount·반복 service restart를 하지 않는다.
