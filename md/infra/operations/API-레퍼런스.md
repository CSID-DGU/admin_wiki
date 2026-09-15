# API 레퍼런스

## 이 문서에서 다루는 내용

- config-server HTTP API(v2.0)의 엔드포인트, 호출 주체, 입력, 응답
- 작업 등록 방식(생성·회수)과 결과·단계 기록 조회
- 인증, 입력 검증, 오류 형식

## 빠른 이동

| 필요할 때 | 문서 |
| --- | --- |
| 승인 뒤 내부 처리 순서를 먼저 본다 | [시스템 아키텍처](../design/시스템-아키텍처.md) |
| 운영 중 오류 응답을 해석한다 | [운영 매뉴얼](운영-매뉴얼.md) |
| Kerberos 준비 실패를 본다 | [kdc-setup 운영](../kdc-setup/operations.md) |

config-server의 HTTP API 명세다. 배포된 API 목록은 config-server의 Swagger UI(`/apidocs/`)에서도 볼 수 있다. 요청 본문 스키마는 코드의 요청 모델(`request_models.py`)에서 만들어지므로 문서와 실제 검증 규칙이 같다.

---

## 1. 공통 사항

| 항목 | 값 |
|------|-----|
| 주소 | 클러스터 내부 Service `containerssh-config-service` (80 → 8000) |
| 요청/응답 형식 | JSON (`Content-Type: application/json`) |
| 인증 | `X-Internal-Token` 헤더. Secret `config-server-api-token`이 설정된 환경에서 없거나 틀리면 **401** `UNAUTHORIZED`. 토큰 없이 열린 경로는 `GET /health`, `GET /requests/{request_id}/status`, API 문서(`/apidocs`, `/apispec_1.json`)뿐이다 |
| 계정 접두어 | `accounts.prefix`가 설정된 환경은 그 접두어로 시작하지 않는 계정에 대한 변경 요청을 **403**으로 거절한다 |
| 입력 검증 | 본문을 요청 모델로 검사해 실패하면 **400** `INVALID_REQUEST`. 모르는 필드는 무시하고 문자열 앞뒤 공백은 지운다 |
| 오류 형식 | 모든 실패가 `infra_error` — `step`(실패한 단계), `error`(코드), `detail`, 필요하면 `rollback`·`errors` |

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
| `OperationJobService` | `POST /operations/provision·revoke·migrate`, `GET /operations/{kind}/{request_id}`, `GET .../steps` | 승인, 만료·계정 삭제, 마이그레이션, 결과 폴링, 신청 상세 타임라인 |
| `PodService` | `DELETE /pods/{pod_name}` | 고아 Pod 삭제 |
| `GroupService` | `POST /groups`, `POST /users/{username}/groups` | 그룹 생성, 승인 시 기존 계정에 그룹 추가 |
| (프론트엔드 nginx) | `GET /requests/{request_id}/status` | 승인 진행 표시. nginx가 이 경로만 넘긴다 |

---

## 2. GET /health

**성공 응답.** `200`

```json
{"status": "OK", "run_mode": "noprobe", "oplog_write_failures": 0}
```

`run_mode`는 실행 방식(baseline·noprobe·full), `oplog_write_failures`는 작업 이력 기록 실패 누적 수(조회 불능이면 `null`)다. 외부 의존성(DB, Kubernetes, NAS)은 검사하지 않는다.

---

## 3. POST /operations/provision — 생성 작업 등록

| 항목 | 값 |
|------|-----|
| 호출 주체 | admin_be 승인 |
| 응답 | 등록만 하고 **202**. 실행은 제어기가 한다 |

**입력.**

```json
{
  "request_id": "4821",
  "username": "user2100",
  "account": {
    "passwd_base64": "cHc=",
    "gecos": "홍길동",
    "primary_group_name": "user2100",
    "supplementary_groups": [{"name": "ailab", "gid": 20005}]
  }
}
```

| 필드 | 규칙 |
|------|------|
| `request_id` | admin_be 신청 번호. 양의 정수(문자열로 저장) |
| `username` | 필수 |
| `account` | **계정을 새로 만들 때만** 보낸다. 이미 계정이 있으면 빼고 보내 컨테이너만 만든다 |
| `account.passwd_base64` | UTF-8 평문 비밀번호의 base64. 서버가 SHA-512 crypt 해시를 만들어 작업에 넣고, 평문은 작업 이력에 남기지 않는다 |
| `account.primary_group_name` | 생략하면 `username` |

**실행 단계(제어기).** 계정 생성 → 홈 생성 → Kerberos principal (`account`가 있을 때) → 사용자 설정 조회(`GET /api/requests/config/by-request/{request_id}`) → Pod 준비 → 노드 선택 → Pod 스펙(포트 배정, Kerberos 배포) → Pod 생성(로그인 비밀번호 Secret `<pod>-account`) → Ready 대기(최대 500초) → NodePort Service 생성. `full` 방식은 이어서 접근 시험을 한다.

로그인 비밀번호가 비어 있으면 Pod를 만들지 않고 `LOGIN_PASSWORD_MISSING`으로 실패한다.

**성공 응답.** `202` — `{"request_id": "4821", "job_id": 812, "status": "accepted"}`

**대표 실패.**

| 상태 | 의미 |
|:---:|------|
| 400 | 입력 오류 |
| 403 | 계정 접두어 불일치 |
| 409 | 같은 신청의 생성 작업이 아직 끝나지 않음 (`JOB_ALREADY_REGISTERED`) |
| 503 | 작업 저장소·작업 이력 기록 불가 (`JOB_STORE_UNAVAILABLE`, `JOB_LOG_UNAVAILABLE`) |

---

## 4. POST /operations/revoke — 회수 작업 등록

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
| `node_name` | keytab을 지울 노드. 없으면 지운 Pod의 노드. 계정 회수에서 노드를 모르면 **보류**한다(모든 노드를 훑으면 같은 이름의 무관한 옛 계정까지 지울 수 있음) |
| `delete_account` | 참이면 계정·Kerberos까지 회수. 기본 거짓 |

`pod_name`도 없고 `username`+`delete_account`도 아니면 400이다.

**실행 단계(제어기).** 접속 포트 해제 → 포트 배정 반환 → Pod 삭제 → 그 노드 keytab 정리 → (`delete_account`면) 회수 가능 확인 → 계정 삭제 → Kerberos 정리. **홈 디렉터리는 보존한다.** 이미 없는 Pod는 성공으로 끝난다.

**성공 응답.** `202`. 실패 코드는 3절과 같다.

---

## 5. GET /operations/{kind}/{request_id} — 작업 결과

`kind`는 `provision`, `revoke`, `migrate`(그 외 404 `UNKNOWN_JOB_KIND`). 마이그레이션 작업의 `result`에는 `status`(`migrated`/`skipped`), `reason`, `from_node`, `to_node`, `old_pod_name`, `old_pod_cleanup`이 더 붙는다.

```json
{
  "request_id": "4821", "kind": "provision", "job_id": 812, "phase": "SUCCESS",
  "error_code": null, "updated_at": "2026-09-15 11:43:38",
  "result": {
    "uid": 50001, "gid": 50001, "pod_name": "ailab-user2100-1a2b3c4d", "node": "farm2",
    "ports": [{"internal_port": 22, "external_port": 32001, "usage_purpose": "ssh"}]
  }
}
```

| phase | 의미 |
|-------|------|
| `none` | 등록 이력 없음 |
| `START` | 대기·실행 중 |
| `SUCCESS` | 완료. 생성 작업은 만든 자원을 `result`로 준다(하루 뒤 `result`는 사라지고 phase만 남음) |
| `FAIL` | 실패. `error_code`에 원인. 자원을 남긴 실패는 `DEGRADED` |
| `UNKNOWN` | 요청은 나갔으나 실행 여부를 알 수 없음 |

---

## 6. GET /operations/{kind}/{request_id}/steps — 단계 기록

한 신청의 작업을 최근 순으로 최대 5개, 작업마다 끝난 단계를 시각순으로 돌려준다.

```json
{
  "request_id": "4821", "kind": "provision",
  "jobs": [{
    "job_id": 812, "started_at": "2026-09-15T11:39:47Z", "finished_at": "2026-09-15T11:43:38Z",
    "phase": "SUCCESS", "error_code": null,
    "steps": [
      {"at": "2026-09-15T11:43:31Z", "action": "WAIT_READY", "phase": "SUCCESS", "attempt": 1,
       "probe": null, "step": null, "error_code": null,
       "summary": {"image_source": "pulled", "image_pull_seconds": 214.8, "image_size_mb": 7014}}
    ]
  }]
}
```

제어기가 작업을 실행하는 동안 진행 상황 단계가 바뀌면 `action: "PROGRESS"`, `phase: "INFO"` 행이 남고 `summary`에 `stage`·`message`가 온다(예: `pulling_image` "이미지 다운로드 중" → `starting_container`). 진행 상황 조회(7절)는 마지막 단계만 1시간 보관하지만, 이 행은 작업 이력에 계속 남는다.

`summary`는 화면에 보여도 되는 항목만 담는다(내부 주소·마운트 경로·명령 출력 제외). 컨테이너 준비 대기(`WAIT_READY`)는 `image_source`(`pulled`/`cached`), `image_pull_seconds`, `image_size_mb`, `mount_retries`, `restarts`를, 접근 시험 행은 시험별 근거를 담는다. 재시도 행은 `phase`가 `RETRY`이고 `step`에 다시 돌린 단계 이름이 온다.

---

## 7. GET /requests/{request_id}/status — 생성 진행 상황

토큰 없이 조회한다. 프론트엔드 nginx가 `/pod-status/requests/{id}/status`를 이 경로로 넘긴다.

```json
{"request_id": "4821", "stage": "pulling_image", "message": "이미지 다운로드 중", "updated_at": "..."}
```

`stage`: `unknown`(이력 없음), `started`, `selecting_node`, `building_pod_spec`, `allocating_nodeport`, `deploying_krb5`, `creating_pod`, `pulling_image`, `starting_container`, `mount_retrying`, `creating_services`, `ready`, `failed`. `failed`의 `message`에는 원인 분류만 담고 상세는 로그와 단계 기록에서 본다. 진행 상태는 최종 갱신 후 1시간 보존한다.

---

## 8. POST /operations/migrate — 마이그레이션 작업 등록

**입력.**

```json
{"request_id": "4821", "username": "user2100", "pod_name": "ailab-user2100-1a2b3c4d", "nodes": ["farm2", "farm6", "farm7"], "force": true}
```

| 필드 | 규칙 |
|------|------|
| `request_id` | 필수. 신청 번호 |
| `username` | 필수 |
| `pod_name` | 옮길 Pod. 없으면 사용자의 실행 중인 Pod |
| `nodes` | 후보 노드 목록(현재 노드 포함), 1개 이상 |
| `min_improvement_ratio` | 0~1. 생략하면 0.2. 최고 후보가 이만큼 좋아져야 옮긴다 |
| `force` | 참이면 개선 비율을 보지 않고 가장 여유 있는 후보로 옮긴다 |

**실행 단계(제어기).** 옮길 노드 선택(노드 이름 확인, 기존 Pod·현재 노드 확인, GPU 점수 비교) → 사용자 설정 조회 → 기존 Pod 로그인 비밀번호 Secret 이어받기 → Pod 준비 → Pod 스펙 → Pod 생성 → Ready 대기(최대 500초) → 접속 포트 연결 → 기존 Pod·Service·포트 배정·비밀번호 Secret 정리.

- 현재 노드 말고 후보가 없거나(`no_candidate_node`) 개선 비율을 못 넘으면(`no_significant_improvement`) 남은 단계를 돌리지 않고 **성공**으로 끝나며 결과 `status`가 `skipped`다.
- 새 Pod가 실패하면 새 Pod와 새 포트를 정리하고 기존 Pod는 그대로 둔다(작업 FAIL).
- 기존 Pod 정리가 실패해도 새 Pod가 서비스 중이므로 작업은 성공이고 결과 `old_pod_cleanup`이 `failed`다.
- **홈 디렉터리는 유지되지만 컨테이너 안의 시스템 변경(설치한 패키지 등)은 유지되지 않는다.**

**성공 응답.** `202`. 결과는 `GET /operations/migrate/{request_id}`로 본다.

| 상태 | 의미 |
|:---:|------|
| 400 | 입력 오류 |
| 403 | 계정 접두어 불일치 |
| 409 | 같은 신청의 마이그레이션 작업이 아직 끝나지 않음 |

작업 실패 코드: `UNKNOWN_NODE`, `POD_NOT_FOUND`, `CURRENT_NODE_NOT_IN_CANDIDATES`, `LOGIN_PASSWORD_MISSING`, 그 밖에 생성 단계와 같은 코드.

---

## 9. DELETE /pods/{pod_name} — 고아 Pod 삭제 (동기)

신청 기록이 없는 Pod를 지울 때만 쓴다. 신청이 있는 Pod는 회수 작업(4절)으로 지운다.

**입력.** 경로의 `pod_name`(`ailab-` 형식), 선택 쿼리 `request_id`.

**처리 순서.** 접속 포트 해제 → 포트 배정 반환 → Pod 삭제(실제 삭제까지 최대 60초 대기) → 그 노드 keytab 정리.

**성공 응답.** `200`

```json
{"status": "deleted", "pod_name": "ailab-user2100-1a2b3c4d",
 "progress": {"servicesDeleted": true, "nodeportsReleased": true, "podDeleteRequested": true, "podDeleted": true}}
```

Pod가 원래 없었으면 `already_absent: true`가 붙는다. 실패는 400(잘못된 Pod 이름), 500(단계 실패 — `rollback` 포함).

---

## 10. POST /groups — 그룹 생성

**입력.** `{"name": "developers", "gid": 20005, "members": ["user2100"]}` — `name` 필수, `gid` 생략 시 자동 배정, `members` 선택.

**성공 응답.** `201` — `{"group": {"name": "developers", "gid": 20005}}`

| 상태 | 의미 |
|:---:|------|
| 400 | 입력 오류, 존재하지 않는 멤버(`INVALID_GROUP_MEMBER`) |
| 409 | 그룹 이름 중복(`GROUP_NAME_EXISTS`) 또는 gid 중복(`GROUP_GID_EXISTS`) |
| 500 | GID 대역 소진 |

---

## 11. POST /users/{username}/groups — 사용자 그룹 추가

**입력.** `{"groups": ["developers", "ai-lab"]}` (1개 이상)

**성공 응답.** `200` — `{"status": "updated", "user": "user2100", "groups": [...]}`. 이미 속한 그룹은 그대로 둔다.

| 상태 | 의미 |
|:---:|------|
| 400 | `groups` 누락 |
| 404 | 사용자 없음(`USER_NOT_FOUND`), 또는 존재하지 않는 그룹 포함(`GROUP_NOT_FOUND`) |

---

## 12. v2.0에서 없어진 API

| 옛 API | 대신 쓰는 것 |
|--------|-------------|
| `POST /migrate` (동기) | `POST /operations/migrate` (작업) |
| `POST /delete-pod` | `DELETE /pods/{pod_name}` |
| `PUT /accounts/groups` | `POST /groups` |
| `PUT /accounts/users/{username}/groups` | `POST /users/{username}/groups` |
| `POST /create-pod`, `PUT /accounts/users` | `POST /operations/provision` |
| `DELETE /accounts/users/{username}` | `POST /operations/revoke` (`delete_account: true`) |
| `GET /pods/{username}/status` | `GET /requests/{request_id}/status` |
| `GET /accounts/users`, `GET /accounts/users/{username}` | 작업 결과·단계 기록 |
| `DELETE /accounts/groups/{groupname}` | 없음 |

---

## 13. 호출할 때 확인할 점

- 변경 API는 반드시 내부 토큰으로 부른다. 토큰 값은 셸 변수에만 담고 명령 기록·로그·이슈에 남기지 않는다.
- 생성·회수는 등록 응답(202)이 완료가 아니다. 결과 조회로 `SUCCESS`를 확인한다.
- 회수는 홈 디렉터리를 지우지 않는다. 홈 정리는 NAS 운영 절차로 따로 한다.
- 8888 포트도 다른 포트처럼 NodePort Service로 열린다. Jupyter 인증이 없는 이미지는 내부망에서만 접근하게 한다.
