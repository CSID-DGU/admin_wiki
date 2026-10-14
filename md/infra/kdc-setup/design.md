# kdc-setup 설계

## 이 문서에서 다루는 내용

- AD 사용자, Secret, 노드 keytab, ccache가 어디에 놓이고 누가 쓰는지
- 계정 생성, Pod 시작, Pod·계정 삭제 때 Kerberos 관련 파일이 어떻게 바뀌는지
- 바꾸면 안 되는 보안·운영 규칙

## 빠른 이동

| 필요할 때 | 문서 |
| --- | --- |
| 전체 흐름을 먼저 본다 | [개요](index.md) |
| 점검과 장애 대응을 본다 | [운영](operations.md) |
| 실제 설정값의 위치를 본다 | [설정](config.md) |

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
5. 도메인의 모든 DC가 이 사용자를 같은 UID로 돌려줄 때까지 기다린다. 복제 전에 노드가 사용자를 조회하면 "없는 사용자"가 노드에 캐시되어 첫 컨테이너가 자기 홈에 쓰지 못한다.
6. 보조 그룹을 AD에 반영한다. NAS는 그룹 권한도 AD 기준으로 판정하므로 계정 파일에만 쓴 그룹은 NFS에서 효력이 없다.

4단계가 실패하면 계정 생성도 실패하고, AD 사용자 삭제를 시도한 뒤 계정 파일을 되돌린다. 이번 작업이 새로 만든 빈 홈만 지우고 이미 있던 홈은 남긴다. 그래도 AD 사용자·전용 그룹·Secret 일부가 남을 수 있으므로 같은 이름으로 다시 만들기 전에는 이 세 곳을 확인한다.

### Pod 시작

1. config-server가 대상 FARM 노드를 선택한다.
2. 그 노드가 사용자를 같은 UID로 확인할 수 있을 때까지 기다린다(`check-identity`, 최대 900초).
3. Secret의 keytab을 해당 노드의 제한된 관리 채널로 전달한다.
4. 노드는 root 전용 keytab·환경 파일·`decs-krb-refresh@<user>.timer`를 준비한다.
5. refresh service가 사용자 TGT를 발급하고 ccache 소유권을 검증한다.
6. 검증에 성공할 때만 Pod가 ccache와 FARM 홈을 hostPath로 공유하며 시작한다.

배포가 성공하면 그 사용자·노드 조합의 정리 예약(`krb5_cleanup_pending`)을 지운다. 남겨 두면 재조정이 방금 배포한 keytab을 뒤늦게 지운다.

### Pod·계정 삭제

Pod 삭제는 해당 노드의 timer, keytab, 환경 파일과 ccache를 정리한다. 다만 **같은 노드에 같은 사용자의 다른 Pod가 있으면 남긴다.** 지우면 살아 있는 Pod의 티켓이 갱신되지 않아 홈이 `nobody`로 보인다. 이동은 새 Pod가 준비된 뒤 기존 노드의 keytab을 같은 규칙으로 정리한다.

계정 삭제는 AD 사용자와 Secret을 지우고, **작업이 받은 노드(`node_name`)** 의 keytab, timer, ccache를 정리한다. 노드를 모르면 지우지 않고 보류한다. 모든 노드를 훑으면 같은 이름의 무관한 옛 계정까지 지울 수 있기 때문이다. admin_be는 사용자가 컨테이너를 썼던 노드마다 계정 회수를 따로 등록한다.

정리에 실패한 노드는 `krb5_cleanup_pending`에 남고, 30분 재조정이 다시 시도한다. 재조정은 포트 배정 기록에 없는 사용자의 keytab을 고아 후보로 로그에 남기지만 자동으로 지우지는 않는다(구 시스템 계정과 구분할 수 없다).

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
