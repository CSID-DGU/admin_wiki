# API 레퍼런스

## 이 문서에서 다루는 내용

- config-server HTTP API의 엔드포인트, 호출 주체, 입력, 응답
- 작업 등록 방식(여덟 가지 작업 종류)과 결과·단계 기록 조회
- 인증, 입력 검증, 오류 형식

## 빠른 이동

| 필요할 때 | 문서 |
| --- | --- |
| 승인 뒤 내부 처리 순서를 먼저 본다 | [시스템 아키텍처](../design/시스템-아키텍처.md) |
| 운영 중 오류 응답을 해석한다 | [운영 매뉴얼](운영-매뉴얼.md) |
| Kerberos 준비 실패를 본다 | [kdc-setup 운영](../kdc-setup/operations.md) |

config-server의 HTTP API 명세다. 배포된 API 목록은 config-server의 Swagger UI(`/apidocs/`)에서도 볼 수 있다(토큰 필요). 요청 본문 스키마는 코드의 요청 모델(`request_models.py`)에서 만들어지므로 문서와 실제 검증 규칙이 같다.

---

## 1. 공통 사항

| 항목 | 값 |
|------|-----|
| 주소 | 클러스터 내부 Service `containerssh-config-service` (80 → 8000) |
| 요청/응답 형식 | JSON (`Content-Type: application/json`) |
| 인증 | 모든 경로에 `X-Internal-Token` 헤더가 필요하다. 없거나 틀리면 **401** `UNAUTHORIZED`. 토큰 없이 열린 경로는 `GET /health` 하나다. API 문서(`/apidocs`, `/apispec_1.json`)도 경로와 요청 형식이 드러나므로 토큰을 요구한다 |
| 토큰 미설정 | 서버에 토큰이 없으면 검사를 끄지 않고 `/health` 외의 요청을 모두 **503** `API_TOKEN_NOT_CONFIGURED`로 거절한다. Secret이 빠진 채 배포되면 API가 통째로 열리던 것을 막기 위해서다 |
| 계정 접두어 | `accounts.prefix`가 설정된 환경(실험 스택)은 그 접두어로 시작하지 않는 계정에 대한 변경 요청을 **403** `ACCOUNT_PREFIX_MISMATCH`로 거절한다 |
| 입력 검증 | 본문을 요청 모델로 검사해 실패하면 **400** `INVALID_REQUEST`. 모르는 필드는 무시하고 문자열 앞뒤 공백은 지운다 |
| 이름 규칙 | 사용자·그룹 이름은 `[a-z_]`로 시작하는 32자 이하의 소문자·숫자·`_`·`-` |
| 신청 번호 | `request_id`는 양의 정수(문자열로 저장) |
| 오류 형식 | 모든 실패가 `infra_error` — `step`(실패한 단계), `error`(코드), `detail`, 필요하면 `progress`·`errors` |

입력 검증 실패 예시:

```json
{
  "step": "VALIDATE_REQUEST",
  "error": "INVALID_REQUEST",
  "detail": "min_improvement_ratio: Input should be greater than or equal to 0",
  "errors": [{"field": "min_improvement_ratio", "message": "Input should be greater than or equal to 0"}]
}
```

admin_be 호출 주체:

| admin_be | 엔드포인트 | 시점 |
|------|------|------|
| `ConfigServerJobClient` | `POST /operations/{kind}`, `GET /operations/{kind}/{request_id}`, `GET .../steps` | 승인, 만료·계정 삭제, 이동·재시작, 비밀번호 재설정, 그룹, 포트 변경, 이용 정지, 홈 정리, 결과 폴링, 신청 상세 타임라인 |
| `ConfigServerJobClient` | `GET /requests/{request_id}/status` | 승인 진행 표시. 화면은 admin_be를 거쳐 받는다(프론트엔드 nginx의 `/pod-status/` 직통 경로는 막혀 있다) |
| `PodService` | `DELETE /pods/{pod_name}` | 신청 기록이 없는 고아 Pod 삭제 |
| `ConfigServerReservedLinuxNames` | `GET /reserved-names` | 가입 단계의 우분투 계정명 검사 |

config-server가 admin_be를 부르는 경로도 같은 토큰을 쓴다: `GET /api/requests/config/by-request/{request_id}`(사용자 설정 조회), `POST /api/internal/slack/notify`(GPU 점검 알림).

---

## 2. GET /health, GET /health/details

**`/health` 성공 응답.** `200` — 토큰 없이 열린 유일한 경로다.

```json
{"status": "OK", "run_mode": "baseline"}
```

준비 상태 점검(startup·readiness probe)이 이 경로를 읽는다. 그래서 프로세스가 요청을 받을 수 있는지만 답하고 DB·Redis·Kubernetes·NAS는 건드리지 않는다. 예전에는 작업 이력 기록 실패 수를 Redis에서 함께 읽었는데, Redis가 사라지자 조회가 17초씩 걸려 준비 점검이 계속 실패했고 배포가 10분 한도를 채우고 중단됐다.

**`/health/details` 성공 응답.** `200` (토큰 필요)

```json
{"status": "OK", "run_mode": "baseline", "oplog_write_failures": 0}
```

`oplog_write_failures`는 작업 이력 기록 실패 누적 수다. 조회하지 못하면 `null`이다(0과 구분).

---

## 3. 작업 등록 공통

모든 작업 등록은 같은 형식으로 답한다.

**성공 응답.** `202` — `{"request_id": "4821", "job_id": 812, "status": "accepted"}`

등록만 하고 실행은 제어기가 한다. 끝났는지는 `GET /operations/{kind}/{request_id}`(9절)의 `phase`로 확인한다.

| 상태 | 의미 |
|:---:|------|
| 400 | 입력 오류 |
| 403 | 계정 접두어 불일치 |
| 409 | 같은 번호의 같은 종류 작업이 아직 끝나지 않음 (`JOB_ALREADY_REGISTERED`) |
| 503 | 작업 저장소·작업 이력 기록 불가 (`JOB_STORE_UNAVAILABLE`, `JOB_LOG_UNAVAILABLE`) |

작업 시작 행에는 목표 상태(입력)를 남기되 비밀번호 해시는 빼고 남긴다.

---

## 4. POST /operations/provision — 생성

**입력.**

```json
{
  "request_id": "4821",
  "username": "user2100",
  "account": {
    "passwd_hash": "$6$...",
    "gecos": "홍길동",
    "primary_group_name": "user2100",
    "supplementary_groups": [{"name": "ailab", "gid": 70005}, {"name": "newteam"}],
    "expected_uid": 21042
  },
  "supplementary_groups": []
}
```

| 필드 | 규칙 |
|------|------|
| `request_id` | 필수. admin_be 신청 번호 |
| `username` | 필수 |
| `account` | **계정을 새로 만들 때만** 보낸다. 이미 계정이 있으면 빼고 보내 컨테이너만 만든다 |
| `account.passwd_hash` / `passwd_base64` | 둘 중 **하나만**. `passwd_hash`는 SHA-512 crypt 해시(`$6$...`), `passwd_base64`는 해시 도입 전 방식(평문의 base64). 평문으로 받으면 서버가 해시로 바꿔 작업에 넣는다 |
| `account.gecos` | 사람 이름. 계정 파일 칸 구분자(`:`)·제어 문자·줄바꿈 불가 |
| `account.primary_group_name` | 생략하면 `username` |
| `account.supplementary_groups`, `supplementary_groups` | `{name, gid}` 목록. `gid`가 없으면 아직 인프라에 없는 새 공유 그룹이고, 작업이 GID를 정해 결과(`result.groups`)로 돌려준다. `account`가 없을 때도 기존 계정에 그룹을 더한다 |
| `account.expected_uid` | 이 사용자가 예전에 쓰던 UID. 대장에 같은 이름·UID의 계정이 있으면 새로 만들지 않고 이어받는다. 대장에 없으면 NAS 홈 소유자가 이 값과 같을 때 그 번호로 만든다 |

새 계정 이름이 예약 이름(이미지 그룹·시스템 계정·운영용 계정)이거나 공용 그룹 이름과 겹치면 등록하지 않고 **400** `USERNAME_CONFLICTS_GROUP`. 409는 admin_be가 "같은 신청의 작업이 진행 중"으로 읽으므로 400으로 답한다.

**실행 단계(제어기).** 계정 → 홈 → Kerberos principal → AD 복제 대기 → AD 그룹 반영 → 사용자 설정 조회 → Pod 준비 → 노드 선택 → Pod 스펙(포트 배정, keytab 배포) → Pod 생성(로그인 비밀번호 Secret `<pod>-account`) → Ready 대기(최대 500초) → NodePort Service 생성. 기존 계정이면 계정·AD 단계 대신 홈 확인(없으면 다시 만듦)부터 한다. `full` 방식은 이어서 접근 시험을 한다. 자세한 규칙은 [시스템 아키텍처](../design/시스템-아키텍처.md) 3절.

**대표 실패 코드.** `USER_ALREADY_EXISTS`, `UID_RANGE_EXHAUSTED`, `EXPECTED_UID_CONFLICT`, `HOME_OWNER_MISMATCH`, `NAS_SSH_FAILED`, `KDC_FAILED`, `AD_REPLICATION_TIMEOUT`, `NODE_SELECTION_FAILED`, `LOGIN_PASSWORD_MISSING`, `POD_READY_TIMEOUT`.

---

## 5. POST /operations/revoke — 회수

**입력.**

```json
{"request_id": "4821", "pod_name": "ailab-user2100-1a2b3c4d"}
```

```json
{"request_id": "4821", "username": "user2100", "node_name": "farm6", "delete_account": true}
```

| 필드 | 규칙 |
|------|------|
| `request_id` | 필수 |
| `pod_name` | 회수할 Pod. `ailab-` 형식 |
| `username` | `pod_name`이 없을 때 필요 |
| `node_name` | keytab을 지울 노드. 없으면 같은 작업에서 지운 Pod의 노드. 계정 회수에서 노드를 모르면 **보류**한다(`ACCOUNT_NODE_UNKNOWN`) |
| `delete_account` | 참이면 계정·Kerberos까지 회수. 기본 거짓 |

`pod_name`도 없고 `username`+`delete_account`도 아니면 400이다.

**실행 단계(제어기).** 접속 포트 해제 → 포트 배정 반환 → Pod 삭제 → 구운 노드 이미지 삭제 → 그 노드 keytab 정리 → (`delete_account`면) 회수 가능 확인 → 계정 삭제 → Kerberos 정리. **홈 디렉터리는 보존한다.** 이미 없는 Pod는 성공으로 끝난다. 같은 사용자의 컨테이너가 남아 있으면 계정 회수를 보류한다(`ACCOUNT_IN_USE`).

---

## 6. POST /operations/migrate — 이동·재시작

**입력.**

```json
{"request_id": "4821", "username": "user2100", "pod_name": "ailab-user2100-1a2b3c4d", "nodes": ["farm2", "farm6", "farm7"], "force": true}
```

```json
{"request_id": "4821", "username": "user2100", "pod_name": "ailab-user2100-1a2b3c4d", "nodes": ["farm6"], "recreate": true, "keep_changes": true}
```

| 필드 | 규칙 |
|------|------|
| `request_id`, `username` | 필수 |
| `pod_name` | 옮길 Pod. 없으면 사용자의 실행 중인 Pod |
| `nodes` | 후보 노드 목록(현재 노드 포함), 1개 이상 |
| `min_improvement_ratio` | 0~1. 생략하면 0.2. 최고 후보가 이만큼 좋아져야 옮긴다 |
| `force` | 참이면 개선 비율을 보지 않고 가장 여유 있는 후보로 옮긴다 |
| `recreate` | 참이면 노드를 고르지 않고 현재 노드에서 다시 만든다 |
| `keep_changes` | `recreate`일 때 컨테이너 변경분을 그 노드의 이미지로 구워 이어 준다. 기본 참 |
| `access_blocked` | 참이면 새로 만드는 접속 포트를 막힌 채로 만든다(이용 정지된 계정) |

**실행 단계(제어기).** 옮길 노드 선택 → 사용자 설정 조회 → 기존 Pod 로그인 비밀번호 Secret 이어받기 → Pod 준비 → (재시작이면) 변경분 굽기 → Pod 스펙 → Pod 생성 → Ready 대기 → 접속 포트 연결 → (`full`이면) 접근 시험 → 기존 Pod·Service·포트 배정·Secret·기존 노드 keytab 정리.

- 옮길 이유가 없으면(`no_candidate_node`, `no_significant_improvement`) 남은 단계를 돌리지 않고 **성공**이며 결과 `status`가 `skipped`다.
- 새 Pod가 실패하면 새 Pod와 새 포트만 정리하고 기존 Pod는 그대로 둔다.
- 기존 Pod 정리가 실패해도 작업은 성공이고 결과 `old_pod_cleanup`이 `failed`다.
- 이동은 홈만 이어지고 컨테이너 안의 시스템 변경은 유지되지 않는다. 재시작은 `keep_changes`면 변경분이 유지되고, 굽지 못하면 실패로 끝나며 기존 Pod는 그대로다.

**대표 실패 코드.** `UNKNOWN_NODE`, `POD_NOT_FOUND`, `CURRENT_NODE_NOT_IN_CANDIDATES`, `LOGIN_PASSWORD_MISSING`, `IMAGE_COMMIT_NO_CONTAINER`, `IMAGE_CHANGES_TOO_LARGE`, 그 밖에 생성 단계와 같은 코드.

---

## 7. 그 밖의 작업

### 7.1 POST /operations/password — 비밀번호 교체

```json
{"request_id": "12", "username": "user2100", "passwd_hash": "$6$..."}
```

계정 대장(`shadow`), 사용자의 모든 계정 Secret, 떠 있는 모든 Pod의 `/etc/shadow`를 새 해시로 바꾼다. 중간에 실패하면 옛 해시로 되돌리고 실패로 끝낸다. 실패의 `error_detail`에 되돌렸는지(`rolled_back`)가 남는다. Pod가 없어도 성공이다. 실패 코드: `USER_NOT_FOUND`, `SECRET_UPDATE_FAILED`, `POD_PASSWORD_SYNC_FAILED`.

### 7.2 POST /operations/group — 그룹

```json
{"request_id": "7", "op": "create", "name": "developers", "members": ["user2100"]}
{"request_id": "8", "op": "add", "username": "user2100", "groups": ["developers"]}
{"request_id": "9", "op": "remove", "username": "user2100", "name": "developers"}
```

| `op` | 필드 | 등록 때 거절하는 경우 |
|------|------|------|
| `create` | `name` 필수, `gid` 생략 시 공용 대역에서 자동, `members` 선택 | 사용자 이름과 겹침(400 `GROUP_NAME_CONFLICTS_USER`), 이미지 예약 이름(409 `GROUP_NAME_RESERVED`), 없는 멤버(400 `INVALID_GROUP_MEMBER`), 대역 밖 `gid`(400 `GID_OUT_OF_RANGE`) |
| `add` | `username`, `groups` | 없는 사용자(404 `USER_NOT_FOUND`), 없는 그룹(404 `GROUP_NOT_FOUND`) |
| `remove` | `username`, `name` | 없는 그룹(404), 사용자의 기본 그룹(409 `PRIMARY_GROUP`) |

등록 때 검사하고 실행 직전에 한 번 더 검사한다(그 사이 대장이 바뀔 수 있다). 결과 `result.gid`에 `create`가 정한 번호가 온다. 실패 코드: `AD_GROUP_CREATE_FAILED`, `AD_GROUP_MEMBER_FAILED`, `GID_RANGE_EXHAUSTED`, `ISSUED_ID_RECORD_FAILED`.

### 7.3 POST /operations/port — 추가 포트 변경

```json
{"request_id": "7", "username": "user2100", "pod_name": "ailab-user2100-1a2b3c4d",
 "ports": [{"internal_port": 3000, "usage_purpose": "웹 서버"}]}
```

`ports`는 **바뀐 뒤 추가 포트 전체 목록**이다(최대 10개). 내부 포트 22·8888·6080은 넣을 수 없고, 같은 내부 포트를 두 번 넣을 수 없으며, 용도로 `ssh`·`jupyter`·`novnc`·`vnc`는 쓸 수 없다. Pod를 다시 만들지 않는다. 결과 `result.ports`는 기본 포트를 포함한 전체 목록이다. 실패 코드: `POD_NOT_FOUND`, `POD_OWNER_MISMATCH`, `PORT_CHANGE_FAILED`.

### 7.4 POST /operations/access — 접속 차단·해제

```json
{"request_id": "7", "username": "user2100", "blocked": true}
```

계정의 모든 Pod의 모든 접속 포트를 막거나 푼다. Pod와 외부 포트 배정은 건드리지 않으므로 풀면 같은 포트로 다시 접속된다. Pod가 없으면 할 일 없이 성공이다. 더 나중에 등록된 작업이 이미 반대 상태로 맞춰 놓았으면 아무것도 바꾸지 않고 `ACCESS_SUPERSEDED`로 실패한다. 결과 `result.services`는 대상 Service 수다.

### 7.5 POST /operations/home — 홈 삭제

```json
{"request_id": "7", "username": "user2100", "expected_uid": 21042}
```

보존 기간이 지난 홈을 지운다. 컨테이너가 남아 있거나 생성·이동 작업이 돌고 있으면 `HOME_IN_USE`, 홈 소유자가 `expected_uid`와 다르면 `HOME_OWNER_MISMATCH`, 홈 경로가 안 보이면 `HOME_ROOT_UNREACHABLE`로 실패한다(재시도 없음). 홈이 이미 없으면 성공이고 `result.deleted`가 `false`다. 계정과 UID는 그대로 둔다.

---

## 8. 작업 종류별 결과

| `kind` | 성공 시 `result` |
|------|------|
| `provision` | `uid`, `gid`, `pod_name`, `node`, `ports`, `groups`(보조 그룹과 GID) |
| `revoke` | `pod_name`, `node`, `ports`(비어 있음) 등 |
| `migrate` | 위에 더해 `status`(`migrated`/`skipped`), `reason`, `from_node`, `to_node`, `old_pod_name`, `old_pod_cleanup`, `changes_kept` |
| `password` | `secrets`(바꾼 Secret 목록), `pods`(반영한·실패한 Pod) |
| `group` | `gid`, `pods` |
| `port` | `pod_name`, `node`, `ports` |
| `access` | `blocked`, `services` |
| `home` | `deleted` |

`ports`의 각 항목은 `internal_port`, `external_port`, `usage_purpose`다.

---

## 9. GET /operations/{kind}/{request_id} — 작업 결과

`kind`는 `provision`, `revoke`, `migrate`, `password`, `group`, `home`, `port`, `access`(그 외 404 `UNKNOWN_JOB_KIND`). `request_id`는 등록 때 보낸 번호 그대로다(접두어는 서버가 붙인다).

```json
{
  "request_id": "4821", "kind": "provision", "job_id": 812, "phase": "SUCCESS",
  "error_code": null, "updated_at": "2026-10-13 11:43:38",
  "result": {
    "uid": 21042, "gid": 21042, "pod_name": "ailab-user2100-1a2b3c4d", "node": "farm2",
    "ports": [{"internal_port": 22, "external_port": 30012, "usage_purpose": "ssh"}],
    "groups": [{"name": "ailab", "gid": 70005}]
  }
}
```

| phase | 의미 |
|-------|------|
| `none` | 등록 이력 없음 |
| `START` | 대기·실행 중 |
| `SUCCESS` | 완료. 만든 자원을 `result`로 준다(하루 뒤 `result`는 사라지고 phase만 남음) |
| `FAIL` | 실패. `error_code`에 원인. 재시도를 다 쓰고 자원을 남긴 실패는 `DEGRADED`, baseline에서 제어기 재시작으로 끊긴 작업은 `INTERRUPTED` |
| `UNKNOWN` | 요청은 나갔으나 실행 여부를 알 수 없음 |

---

## 10. GET /operations/{kind}/{request_id}/steps — 단계 기록

한 번호의 작업을 최근 순으로 최대 5개, 작업마다 끝난 단계를 시각순으로 돌려준다.

```json
{
  "request_id": "4821", "kind": "provision",
  "jobs": [{
    "job_id": 812, "started_at": "2026-10-13T11:39:47Z", "finished_at": "2026-10-13T11:43:38Z",
    "phase": "SUCCESS", "error_code": null,
    "steps": [
      {"at": "2026-10-13T11:43:31Z", "action": "WAIT_READY", "phase": "SUCCESS", "attempt": 1,
       "probe": null, "step": null, "resource": "pod", "error_code": null,
       "summary": {"image_source": "pulled", "image_pull_seconds": 214.8, "image_size_mb": 7014}}
    ]
  }]
}
```

| 필드 | 의미 |
|------|------|
| `action` | 단계 이름(`CREATE_ACCOUNT`, `SELECT_NODE`, `WAIT_READY`, `COMMIT_IMAGE` 등) |
| `phase` | `SUCCESS`, `FAIL`, `RETRY`, `UNKNOWN`. 시작 행은 끝 행과 짝이라 담지 않는다 |
| `probe` | 접근 시험·차단 시험 행이면 시험 이름 |
| `step` | 재시도 행이면 다시 돌린 단계 이름 |
| `resource` | 그 밖의 행이 다룬 대상(`account`, `replication`, `groups` 등). 같은 action이라도 화면이 계정 생성과 그룹 반영을 가려 보여 줄 수 있다 |
| `summary` | 화면에 보여도 되는 항목만. 내부 주소·마운트 경로·명령 출력은 뺀다 |

컨테이너 준비 대기(`WAIT_READY`) 안의 세부 단계도 같은 행으로 남는다: `PULL_IMAGE`(이미지 다운로드, 노드에 이미 있으면 없음), `START_CONTAINER`(컨테이너 시작·준비 확인), `MOUNT_VOLUME`(볼륨 마운트 재시도). Pod 이벤트를 5초마다 보고 판정하므로 시각은 5초 안쪽으로 근사다. 진행 상황 조회(11절)는 마지막 단계만 1시간 보관하지만, 이 행들은 작업 이력에 계속 남는다.

---

## 11. GET /requests/{request_id}/status — 생성 진행 상황

생성·이동 작업의 진행 상황이다. admin_be가 토큰을 붙여 조회해 화면에 전달한다.

```json
{"request_id": "4821", "stage": "pulling_image", "message": "이미지 다운로드 중", "updated_at": "..."}
```

`stage`: `unknown`(이력 없음), `started`, `selecting_node`, `committing_image`(재시작의 변경분 굽기), `building_pod_spec`, `allocating_nodeport`, `deploying_krb5`, `creating_pod`, `pulling_image`, `starting_container`, `mount_retrying`, `creating_services`, `ready`, `failed`. `failed`의 `message`에는 원인 분류만 담고 상세는 로그와 단계 기록에서 본다. 진행 상태는 최종 갱신 후 1시간 보존한다.

---

## 12. DELETE /pods/{pod_name} — 고아 Pod 삭제 (동기)

신청 기록이 없는 Pod를 지울 때만 쓴다. 신청이 있는 Pod는 회수 작업(5절)으로 지운다. admin_be도 신청이 있거나 생성·이동 작업 중인 사용자의 Pod는 이 경로로 지우지 못하게 막는다.

**입력.** 경로의 `pod_name`(`ailab-` 형식), 선택 쿼리 `request_id`(없으면 이 호출만 묶는 임시 키로 기록).

**처리 순서.** 접속 포트 해제 → 포트 배정 반환 → Pod 삭제(실제 삭제까지 최대 60초 대기) → 그 노드 keytab 정리.

**성공 응답.** `200`

```json
{"status": "deleted", "pod_name": "ailab-user2100-1a2b3c4d",
 "progress": {"servicesDeleted": true, "nodeportsReleased": true, "podDeleteRequested": true, "podDeleted": true}}
```

Pod가 원래 없었으면 `already_absent: true`가 붙는다. 실패는 400(잘못된 Pod 이름), 500(단계 실패 — `progress` 포함).

---

## 13. GET /reserved-names — 예약 이름 목록

```json
{"names": ["_apt", "_ssh", "adm", "admin", "..."]}
```

새 계정명으로 받지 않는 이름 전체다. 컨테이너 이미지가 이미 가진 그룹 이름, 시스템 계정, 운영용 계정(`admin`, `ubuntu`, `ailab-krb5` 등)을 합친 목록이다. 이 목록의 원본은 config-server 한 곳이고, admin_be는 받아서 캐시해 가입 단계에서 쓴다.

---

## 14. 없어진 API

| 옛 API | 대신 쓰는 것 |
|--------|-------------|
| `POST /groups`, `POST /users/{username}/groups` | `POST /operations/group` (`create`·`add`) |
| 동기 비밀번호 변경 | `POST /operations/password` |
| `POST /migrate` (동기) | `POST /operations/migrate` |
| `POST /delete-pod` | `DELETE /pods/{pod_name}` |
| `POST /create-pod`, `PUT /accounts/users` | `POST /operations/provision` |
| `DELETE /accounts/users/{username}` | `POST /operations/revoke` (`delete_account: true`) |
| `GET /pods/{username}/status` | `GET /requests/{request_id}/status` |
| `GET /accounts/users`, `GET /accounts/users/{username}` | 작업 결과·단계 기록 |

---

## 15. 호출할 때 확인할 점

- 모든 호출은 내부 토큰으로 부른다. 토큰 값은 셸 변수에만 담고 명령 기록·로그·이슈에 남기지 않는다.
- 등록 응답(202)은 완료가 아니다. 결과 조회로 `SUCCESS`를 확인한다.
- 회수는 홈 디렉터리를 지우지 않는다. 홈은 보존 기간이 지난 뒤 `/operations/home`으로만 지운다.
- 8888 포트도 다른 포트처럼 NodePort Service로 열린다. Jupyter 인증이 없는 이미지는 내부망에서만 접근하게 한다.
