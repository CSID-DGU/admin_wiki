# Kerberos/NFS 디버깅 로그

이 문서는 Kerberos/NFS에서 발생한 장애와 재현 실험을 축적하는 인덱스다.
정상 상태를 만드는 절차는 [운영 문서](../operations.md)에 두고, 여기에는 장애가
어떻게 관측됐고 어떤 가설을 어떤 조건에서 검증했는지 기록한다.

## 기록 목록

| 검증일 | 상태 | 문제 | 핵심 결론 |
| --- | --- | --- | --- |
| 2026-07-22 | 영구 조치 적용·운영 복원 완료 | [NFSv4.1 session slot 고착 해결 및 운영 적용](nfs-v41-session-slot-stuck-remediation.md) | LAB storage를 CentOS Stream 10 `6.12.0-250.el10`으로 교체하고 AD·keytab·NFS export와 LAB1~LAB10 mount를 복원함 |
| 2026-07-20 | 관측, 인과 미확정 | [LAB9에서 `sec=krb5`를 사용하는 이유](lab9-why-sec-krb5.md) | `krb5p`에서 `krb5`로 전환한 뒤 D-state 지속 시간, SUNRPC 적체와 mount probe 지연이 크게 감소함 |
| 2026-07-16 | 재현 완료, 과거 장애 원인 후보 | [NFSv4.1 session slot 고착](nfs-v41-session-slot-stuck.md) | 구형 storage kernel에서 지연된 idmap decode가 NFSv4.1 slot 하나를 영구 `INUSE` 상태로 남기는 경로를 재현함 |

상태는 다음 의미로 사용한다.

- **관측**: 증상과 증거는 있지만 원인 경로를 재현하지 못했다.
- **재현 완료**: 통제한 조건에서 같은 kernel 또는 protocol 경로를 다시 만들었다.
- **원인 후보**: 재현된 경로가 과거 장애를 설명하지만 장애 발생 시점의 직접
  trace가 없어 동일 원인이었다고 확정할 수 없다.
- **원인 확정**: 장애가 시작된 시점의 증거와 재현 결과가 같은 경로를 가리킨다.

## 장애 발생 시 먼저 할 일

NFS `hard` mount 관련 process가 D-state에 들어간 경우에는 새로운 `find`, `du`,
`stat`, canary I/O를 반복하지 않는다. 각 명령이 새로운 NFS request와 D-state
process를 추가할 수 있다.

먼저 NFS 경로를 읽지 않는 local 상태만 수집한다.

```bash
date -Ins
uname -r
findmnt -rn -o TARGET,SOURCE,FSTYPE,OPTIONS

ps -e -o state=,pid=,ppid=,etimes=,comm=,wchan:48=,args= \
  | awk '$1 ~ /^D/ {print}'

cat /proc/net/rpc/nfs 2>/dev/null || true
cat /run/decs-nfs-forensics/status.json 2>/dev/null || true
cat /var/lib/decs-nfs-gss/recovery.state 2>/dev/null || true
cat /var/lib/decs-nfs-gss/canary.state 2>/dev/null || true

systemctl --no-pager --full status rpc-gssd.service
journalctl -u rpc-gssd.service -b --no-pager -n 200
```

forensics가 배포된 host에서는 자동 snapshot이 생성됐는지 먼저 확인한다. 자동
trigger가 없었다면 local 상태만 읽는 수동 snapshot을 한 번 실행할 수 있다.

```bash
sudo systemctl start decs-nfs-forensics-snapshot.service
sudo cat /var/lib/decs-nfs-forensics/last_snapshot.state
```

이미 mount된 경로에 D-state caller가 있으면 `rpc-gssd` restart, forced unmount,
반복 remount를 먼저 실행하지 않는다. 증거를 보존한 뒤 storage·network 상태와
kernel wait path를 기준으로 복구 범위를 결정한다.

## 새 디버깅 문서 작성 형식

새 문제는 한 파일에 다음 내용을 남긴다.

1. **상태와 영향 범위**: 발생 시각, host, kernel, mount source/target/security
2. **증상**: 사용자 증상, process state, wait channel, alert
3. **확인한 사실과 가설**: 관측 사실과 아직 증명하지 못한 추론을 분리
4. **실험 목적**: 어떤 가설을 반증하거나 확인하려 했는지
5. **재현 조건**: server/client, version, cache, 동시성, fault와 안전장치
6. **실행 명령**: 사전 확인, fault 주입, workload, 관측, cleanup 순서
7. **결과와 판정 기준**: 성공/실패를 판단한 trace와 metric
8. **복구와 예방**: 임시 containment, 영구 수정, monitoring 변경
9. **원본 증거**: 결과 README, curated evidence, script와 checksum 링크

운영 환경에서 fault를 주입한 명령은 일반 runbook처럼 제시하지 않고 반드시
실행 일자와 승인·안전 조건을 붙인 **과거 실행 기록**으로 표시한다. 반복 실험은
가능하면 격리 VM harness로 옮긴다.
