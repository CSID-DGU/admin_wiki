# Redis 키 카탈로그

Redis는 코드를 안 보면 지금 어떤 키가 왜 그 값을 가지고 있는지 짐작하기 어렵습니다. 이 문서의 역할은 장애 상황에서 코드를 뒤지지 않고도 "이 키가 뭘 의미하고, 지워도 되는지, 왜 이 TTL을 가지는지"를 이 표만 보고 판단할 수 있게 하는 것입니다. 그래서 장애 대응·디버깅 중에도, 새 캐시·중복 방지 키를 설계할 때도 이 문서를 기준점으로 삼습니다.

---

## 전체 요약

| 분류 | 키 패턴 | 타입 | TTL |
|------|---------|------|-----|
| 인증 | `email:verify:{email}` | String | 5분 |
| 인증 | `VERIFIED:{email}` | String | 10분 |
| 세션 | `RT:{userId}` | String | 7일 |
| 이메일 중복 방지 | `email:preexpiry:{requestId}:{dayLabel}:{date}` | String | 25시간 |
| Slack 큐 | `slack:notification:queue` | List | 없음 |
| Slack 큐 | `slack:infra:notification:queue` | List | 없음 |
| Slack 캐시 | `slack:cache:users:list` | String | 1시간 |

---

## 1. 인증 키

이메일 인증 흐름에서 사용하는 두 개의 키입니다. 둘 다 TTL이 지나면 자동으로 사라지고, 정상 경로에서는 완료 즉시 명시 삭제됩니다.

### `email:verify:{email}`

이메일 인증번호를 임시 저장합니다.

```
저장  POST /api/auth/email/send  →  SET email:verify:user@example.com = "183726" (TTL 5분)
확인  POST /api/auth/email/verify →  GET email:verify:user@example.com
삭제  인증 성공 직후              →  DEL email:verify:user@example.com
     (5분 안에 인증 안 하면 TTL 만료로 자동 삭제)
```

| 항목 | 값 |
|------|----|
| 값 형태 | 숫자 인증번호 문자열 (ex: `"183726"`) |
| TTL | 5분 (`AUTH_CODE_EXPIRE_SECONDS = 300`) |

---

### `VERIFIED:{email}`

인증번호 확인이 완료됐음을 나타내는 상태 키입니다. **이 키가 없으면 회원가입 API가 400을 반환합니다.**

```
저장  인증번호 일치 확인 후       →  SET VERIFIED:user@example.com = "true" (TTL 10분)
삭제  회원가입 완료 직후           →  DEL VERIFIED:user@example.com
     (10분 안에 가입 안 하면 TTL 만료로 자동 삭제)
```

| 항목 | 값 |
|------|----|
| 값 형태 | `"true"` |
| TTL | 10분 |

**TTL 설계 이유**: 인증번호 확인(5분)과 회원가입 폼 제출(10분)을 단계별로 분리한 이유는, 사용자가 인증 직후 바로 가입 폼을 제출하지 않을 수 있기 때문입니다. 더 짧은 TTL을 가진 `email:verify` 키를 먼저 삭제하고, `VERIFIED` 키에는 5분 더 긴 TTL(10분)을 줍니다.

**흐름 요약**

```
이메일 발송       인증번호 확인               회원가입
  │                   │                        │
  ▼                   ▼                        ▼
email:verify     DEL email:verify          DEL VERIFIED
(TTL 5분)   →   SET VERIFIED          →   (회원가입 완료)
                (TTL 10분)
```

---

## 2. 세션 키

### `RT:{userId}`

Refresh Token을 저장하는 핵심 세션 키입니다. **이 키가 없으면 해당 사용자는 로그아웃 상태입니다.**

```
저장  로그인 성공          →  SET RT:42 = "<JWT>" (TTL 7일)
갱신  토큰 재발급          →  SET RT:42 = "<새 JWT>" (TTL 7일, 기존 키 재사용 가능)
삭제  로그아웃             →  DEL RT:42
     (7일 미갱신 시 TTL 만료로 자동 삭제 — 자동 로그아웃)
```

| 항목 | 값 |
|------|----|
| 값 형태 | Refresh Token JWT 문자열 |
| TTL | 7일 (`jwt.refresh-token-expire-time`) |
| `{userId}` | User 테이블의 PK (`BIGINT`) |

**설계 포인트**: Access Token은 Redis에 저장하지 않습니다(Stateless). Refresh Token만 Redis에 저장해서, 필요시 `DEL RT:{userId}`로 즉시 세션을 무효화(강제 로그아웃)할 수 있습니다. 자세한 내용은 [인증·보안](인증-보안.md)을 참고합니다.

**확인 방법**

```bash
# 사용자 42번이 로그인 상태인지
EXISTS RT:42       # 1 = 로그인, 0 = 로그아웃

# 남은 세션 시간 (초)
TTL RT:42          # -2 = 만료됨, 양수 = 남은 초

# 현재 로그인된 사용자 전체 조회
KEYS RT:*
```

---

## 3. 이메일 중복 방지 키

### `email:preexpiry:{requestId}:{dayLabel}:{date}`

스케줄러가 같은 날 같은 요청에 만료 예고 이메일을 두 번 보내지 않도록 막습니다.

**키 예시**: `email:preexpiry:42:7일:2026-07-15`

```
체크  이메일 발송 직전  →  SETNX email:preexpiry:42:7일:2026-07-15 "sent" (TTL 25h)
                           키가 이미 있으면 → 발송 건너뜀
                           키가 없으면     → 발송 진행 후 키 생성
삭제  TTL 만료 (25시간 후 자동)
```

| 항목 | 값 |
|------|----|
| 값 형태 | `"sent"` |
| TTL | 25시간 (24시간 주기보다 1시간 길게 — 스케줄러 실행 시각 편차 흡수) |
| `{dayLabel}` | `7일`, `3일`, `1일` (만료까지 남은 날 수) |
| `{date}` | 만료 목표 날짜 `yyyy-MM-dd` (today+7/3/1 중 해당일, 발송 당일이 아님) |

**Fail-open 설계**: Redis 장애 시 `setIfAbsent()`가 예외를 던집니다. 이 경우 `false`를 반환해 이메일 발송을 허용합니다(fail-open). 중복 발송보다 누락이 더 나쁘다는 판단입니다. 자세한 패턴은 [핵심 설계 패턴](핵심-설계-패턴.md) 3번을 참고합니다.

**확인 방법**

```bash
# 특정 요청의 중복 방지 키 전체 조회
KEYS email:preexpiry:42:*

# 오늘자 전체 만료 예고 키 조회
KEYS email:preexpiry:*:2026-07-15
```

---

## 4. Slack 알림 큐

Slack Webhook API는 채널당 초당 1건의 rate limit이 있습니다. 비즈니스 로직이 직접 Slack API를 호출하면 블로킹됩니다. 대신 Redis List를 큐로 사용해 비동기 처리합니다.

**공통 구조**

```
알림 발생 시 → RPUSH (오른쪽 삽입, FIFO)
전용 Worker → LPOP (왼쪽 꺼내기, 1초 간격)
발송 실패 → RPUSH로 재삽입 (최대 3회, 3회 초과 시 폐기)
```

두 큐는 소비하는 Worker 클래스도 분리되어 있습니다. `slack:notification:queue`는 `SlackNotificationWorker`가, `slack:infra:notification:queue`는 `InfraSlackNotificationWorker`가 각각 전담합니다. 서로 완전히 독립 운영되므로 한쪽 큐가 밀려도 다른 쪽 발송에는 영향이 없습니다.

### `slack:notification:queue`

일반 비즈니스 알림 큐입니다 (신청 접수, 승인, 거절, 삭제 등). `SlackNotificationWorker`가 소비합니다.

| 항목 | 값 |
|------|----|
| 값 형태 | `SlackNotificationDTO` JSON 직렬화 |
| TTL | 없음 (영구 보존, 꺼낼 때까지 유지) |

### `slack:infra:notification:queue`

Infra 서버 관련 알림 전용 큐입니다. `slack:notification:queue`와 별도로 운영해 우선순위나 처리 경로를 분리합니다. `InfraSlackNotificationWorker`가 소비합니다.

| 항목 | 값 |
|------|----|
| 값 형태 | `slack:notification:queue`와 동일 |

**확인 방법**

```bash
# 현재 큐에 쌓인 메시지 수
LLEN slack:notification:queue
LLEN slack:infra:notification:queue

# 큐 내용 조회 (삭제하지 않고 확인)
LRANGE slack:notification:queue 0 -1
LRANGE slack:infra:notification:queue 0 -1
```

큐 길이가 계속 늘어난다면 `SlackNotificationWorker`가 멈췄거나 Slack API 장애를 의심합니다. 자세한 대응은 [운영 가이드](운영-가이드.md) 11절을 참고합니다.

**동작을 직접 확인하고 싶을 때**

메시지를 수동으로 넣어보고 Worker가 가져가는 과정을 실시간으로 볼 수 있습니다. DTO 필드는 실제 `SlackNotificationDTO`와 맞춰야 역직렬화 에러가 나지 않습니다.

```bash
# 큐에 테스트 메시지 하나 삽입 (RPUSH는 오른쪽 끝에 추가)
RPUSH slack:notification:queue '{"type":"DM","username":"test_user","email":"test@test.com","message":"테스트"}'
# 결과가 (integer) 1이면 큐에 1건 쌓인 것

# 별도 터미널에서 실시간 명령 로그 확인
MONITOR
# 이 상태에서 스케줄러나 알림을 트리거하면 RPUSH → LPOP이 순서대로 찍히는 것을 볼 수 있음
```

---

## 5. Slack 캐시

### `slack:cache:users:list`

Slack 워크스페이스 멤버 목록을 캐싱합니다. DM 발송 시 이메일 → Slack UserId 변환에 사용됩니다. 매번 Slack `users.list` API를 호출하면 rate limit에 걸릴 수 있어 1시간 TTL로 캐싱합니다.

```
저장  Slack users.list API 호출 후  →  SET slack:cache:users:list = <멤버 목록 JSON> (TTL 1h)
삭제  TTL 만료 (1시간 후 자동)
```

| 항목 | 값 |
|------|----|
| 값 형태 | Slack 멤버 목록 JSON 직렬화 |
| TTL | 1시간 |

---

## redis-cli 빠른 참조

```bash
# ─── Redis Pod 접속 ──────────────────────────────────────────────
kubectl exec -it <redis-pod-name> -n <namespace> -- redis-cli

# ─── 키 존재 여부 / 값 / TTL ──────────────────────────────────────
EXISTS RT:42                        # 1 = 있음, 0 = 없음
GET RT:42                           # 값 조회
TTL RT:42                           # 남은 TTL (초). -2 = 만료/없음

# ─── 인증 관련 ───────────────────────────────────────────────────
EXISTS VERIFIED:user@example.com    # 인증 완료 상태 확인
KEYS email:verify:*                 # 인증번호 대기 중인 이메일 목록

# ─── Slack 큐 ────────────────────────────────────────────────────
LLEN slack:notification:queue       # 큐 메시지 수
LRANGE slack:notification:queue 0 4 # 앞에서 5개 확인 (삭제 안 함)

# ─── 만료 예고 중복 방지 ──────────────────────────────────────────
KEYS email:preexpiry:42:*           # requestId=42의 발송 이력
KEYS email:preexpiry:*              # 전체 발송 이력 (주의: 많으면 느림)

# ─── 운영 환경 전체 키 스캔 (KEYS * 대신 사용) ──────────────────
SCAN 0 MATCH * COUNT 100
```

> `KEYS *` 명령은 Redis를 블로킹합니다. 운영 환경에서는 반드시 `SCAN`을 사용하세요.
