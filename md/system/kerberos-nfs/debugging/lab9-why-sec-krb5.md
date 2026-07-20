# LAB9에서 `sec=krb5`를 사용하는 이유

> 상태: LAB9에서 `sec=krb5p` 전환 전 24시간과 `sec=krb5` 전환 후 약 51시간을
> 비교한 운영 관측이다. 전환 뒤 NFS 지연과 적체가 크게 감소했지만, 관측 기간이
> 다르고 security flavor만 통제한 실험이 아니므로 `krb5p`를 단일 원인으로
> 확정하지는 않는다.

## 1. 결론

LAB9의 Kerberos NFS 기본값은 `sec=krb5`로 유지한다. 이 선택은 Kerberos
principal 인증을 유지하면서 RPC payload 암호화 비용을 제외하고, LAB9에서 실제로
관측된 D-state 지속·SUNRPC 적체·mount probe 지연을 낮추기 위한 운영 기준이다.

`krb5p`가 잘못된 방식이라는 뜻은 아니다. NFS payload 기밀성이 반드시 필요한
경로에서는 `krb5p`를 사용해야 한다. 다만 현재 LAB9 사용자 공유의 기본 profile은
가용성과 지연 안정성을 우선해 `krb5`를 사용한다. `krb5i` 또는 `krb5p`는
요구사항이 있고 부하 검증을 통과한 경로에서만 명시적으로 선택한다.

## 2. security flavor의 차이

| flavor | 제공하는 보호 | LAB9에서의 위치 |
| --- | --- | --- |
| `sec=krb5` | Kerberos principal 인증 | 기본값 |
| `sec=krb5i` | 인증 + RPC payload 무결성 | 변조 방지가 명시적으로 필요한 경로에서 검토 |
| `sec=krb5p` | 인증 + 무결성 + RPC payload 암호화 | 기밀성이 필요한 경로에서 성능 검증 후 사용 |

`sec=krb5`에서는 사용자와 NFS service가 Kerberos로 서로 인증되지만, NFS payload
자체는 암호화되지 않는다. 따라서 패킷 캡처와 forensics evidence는 root만 읽을 수
있게 보관하고, 보호되지 않은 네트워크에서 기밀 데이터를 전송해야 한다면 이번
성능 결과만으로 `krb5`를 선택해서는 안 된다.

## 3. 왜 전환했나

`sec=krb5p` 사용 중 LAB9에서는 NFS 관련 D-state가 관측 기간 내내 존재했고,
SUNRPC task와 transport reply 대기가 누적됐다. mount responsiveness probe도
설정된 10초 timeout 상한에 도달했다. 이 상태에서는 home 경로를 읽는 SSH나
사용자 process가 NFS 대기에 연쇄적으로 묶일 수 있다.

`krb5p`는 각 RPC payload에 무결성 처리와 암복호화를 추가한다. 이 비용이 장애의
단일 원인이라고 입증한 것은 아니지만, storage·kernel·network에서 이미 발생한
지연을 더 크게 보이게 하는 증폭 요인인지 확인할 운영상 이유가 있었다. 그래서
principal 인증은 유지하면서 privacy 처리를 제외하는 `sec=krb5`로 전환하고 동일한
NFS health 지표를 계속 관측했다.

## 4. 전환 전후 결과

측정 대상은 **LAB9**다.

| 지표 | `krb5p` 전환 전 24시간 | `krb5` 전환 후 약 51시간 |
| --- | ---: | ---: |
| NFS D-state 존재 비율 | 100% | 약 4.1% |
| D-state 프로세스 최대 | 28개 | 8개 |
| 최장 연속 D-state | 83,339초(약 23.1시간) | 1,236초(약 20분 36초) |
| `xprt_pending` 평균 | 5.35 | 1.29 |
| RPC task 최대 | 3,696 | 525 |
| 마운트 probe 최대 | 10초 | 0.429초 |
| lease 만료 | 없음 | 없음 |

변화 폭은 다음과 같다.

| 비교 항목 | 변화 |
| --- | ---: |
| NFS D-state 존재 비율 | 95.9%p 감소 |
| D-state 프로세스 최대 | 약 71.4% 감소 |
| 최장 연속 D-state | 약 98.5% 감소 |
| `xprt_pending` 평균 | 약 75.9% 감소 |
| RPC task 최대 | 약 85.8% 감소 |
| 마운트 probe 최대 | 약 95.7% 감소 |

가장 중요한 변화는 D-state가 “항상 존재하는 상태”에서 짧고 간헐적인 상태로
바뀐 점이다. `xprt_pending` 평균과 RPC task 최대도 함께 감소했으므로 단순히
D-state process 이름만 달라진 것이 아니라 NFS transport 적체 자체가 줄어든
방향과 일치한다.

전환 전 mount probe의 10초는
`cluster-monitor-exporter`의 command timeout 상한과 같다. 따라서 이 값은 정상
응답에 10초가 걸렸다기보다 probe가 timeout 또는 기존 in-flight probe 상태에
도달했을 가능성이 크다. 전환 후 최대 0.429초는 관측 구간에서 10초 상한에
도달하지 않았음을 보여준다.

두 구간 모두 lease 만료가 없었다. 따라서 이번 비교에서 확인한 개선은 lease
만료 복구 여부보다 D-state 지속, RPC queue와 mount 응답성에 관한 것이다.

## 5. 지표의 의미

| 지표 | 판정 방법 | 구현 |
| --- | --- | --- |
| NFS D-state 존재 비율 | 유효 sample 중 NFS/RPC 관련 D-state process가 하나 이상인 sample 비율 | `cluster_monitor_nfs_forensics_d_state_processes` |
| D-state 프로세스 최대 | 관측 구간의 NFS/RPC 관련 D-state process 최대값 | 같은 metric의 `max_over_time` |
| 최장 연속 D-state | 가장 오래 연속 관측된 NFS/RPC 관련 D-state process의 시간 | `cluster_monitor_nfs_forensics_d_state_oldest_seconds` |
| `xprt_pending` 평균 | transport reply를 기다리는 SUNRPC task 수의 구간 평균 | `cluster_monitor_nfs_xprt_pending` |
| RPC task 최대 | NFS RPC client task 수의 구간 최대 | `cluster_monitor_nfs_rpc_tasks` |
| 마운트 probe 최대 | required mount에 수행한 bounded `statfs` 시간의 구간 최대 | `cluster_monitor_host_mount_probe_seconds` |
| lease 만료 | local NFSv4 lease deadline을 넘긴 시간 | `cluster_monitor_nfs_lease_expired_seconds` |

수집 경로는 다음과 같다.

```text
LAB9 kernel·/proc 상태
  -> NFS forensics watcher status.json
  -> cluster-monitor-exporter metrics
  -> FARM Prometheus
  -> 같은 server="LAB9" label의 전환 전후 구간 집계
```

구현은 [forensics watcher](https://github.com/CSID-DGU/admin_infra_server/blob/main/monitoring/nfs-forensics/bin/decs_nfs_forensics_watch.sh),
[forensics metric adapter](https://github.com/CSID-DGU/admin_infra_server/blob/main/monitoring/prometheus/exporters/cluster-monitor-exporter/cmd/cluster-monitor-exporter/nfs_forensics.go),
[mount/D-state collector](https://github.com/CSID-DGU/admin_infra_server/blob/main/monitoring/prometheus/exporters/cluster-monitor-exporter/cmd/cluster-monitor-exporter/main.go)에서
확인한다.

## 6. 이 결과로 말할 수 있는 것과 없는 것

말할 수 있는 범위는 다음과 같다.

- LAB9에서 `krb5` 전환 뒤 모든 주요 NFS 적체 지표가 같은 방향으로 개선됐다.
- 약 51시간의 전환 후 구간에는 24시간 전환 전 구간과 같은 장시간 고착이
  관측되지 않았다.
- Kerberos 인증을 유지한 `krb5`가 LAB9의 현재 운영 baseline으로 더 안정적이었다.

아직 확정할 수 없는 범위는 다음과 같다.

- `krb5p`의 암호화 비용만으로 전환 전 D-state가 발생했다는 인과관계
- 같은 시기에 달라졌을 수 있는 workload, storage queue, network, kernel 상태의 영향
- FARM/LAB의 다른 host에서도 감소 폭이 동일할 것이라는 일반화
- 51시간보다 긴 기간이나 peak workload에서도 같은 결과가 유지된다는 보장

따라서 이 기록의 판정은 **LAB9 운영 선택을 지지하는 강한 전후 관측**이며,
통제된 benchmark나 원인 확정 실험은 아니다. 원인을 더 좁히려면 동일 workload와
동일 시간대에 `krb5`/`krb5p`를 반복 교차하는 격리 실험이 필요하다.

## 7. 운영 기준과 확인 방법

LAB9의 desired mount option은 `sec=krb5`다. mount source는 IP가 아니라 NFS
service principal과 일치하는 FQDN을 사용한다. D-state가 이미 존재할 때는 확인을
위해 mount를 반복해서 읽거나 즉시 remount하지 말고 먼저 local forensics 상태를
보존한다.

현재 mount의 security flavor는 다음처럼 정확히 확인한다.

```bash
LAB9_MOUNT_TARGET=/home/tako9/share

findmnt -T "$LAB9_MOUNT_TARGET" -n -o TARGET,SOURCE,FSTYPE,OPTIONS
findmnt -T "$LAB9_MOUNT_TARGET" -n -o OPTIONS \
  | tr ',' '\n' \
  | grep -Fx 'sec=krb5'
```

`grep -F 'sec=krb5'`만 사용하면 `sec=krb5p`도 일치하므로 option을 쉼표 단위로
분리해 exact match한다. 전환 이후에도 최소한 다음 조건을 함께 확인한다.

- NFS D-state 존재 비율과 최장 연속 시간이 다시 증가하지 않는가
- `xprt_pending` 평균과 RPC task 최대가 전환 전 수준으로 돌아가지 않는가
- mount probe가 10초 timeout 상한에 다시 도달하지 않는가
- `cluster_monitor_nfs_lease_expired_seconds`가 계속 0인가
- payload 기밀성 요구가 새로 생겨 `krb5p`가 필요한 경로가 되지 않았는가

기본 security policy는 [Kerberos/NFS 운영 저장소](https://github.com/CSID-DGU/admin_infra_server/blob/main/kerberos-nfs/README.md),
배포 값은 [monitoring exporter 변수](https://github.com/CSID-DGU/admin_infra_server/blob/main/monitoring/ansible_playbook/group_vars/exporters.yml)를
기준으로 한다. 상세 장애 채증과 D-state 대응은 [디버깅 로그 개요](index.md)의
절차를 따른다.

## 8. 다음 측정에서 함께 남길 값

현재 비교표에는 구간 길이만 있고 정확한 시작·종료 timestamp와 원본 query/export
artifact가 없다. 다음 재측정부터는 아래 값을 함께 보관해야 같은 결과를 재계산할
수 있다.

- 전환 시각과 두 구간의 시작·종료 시각(타임존 포함)
- LAB9의 source FQDN, target, NFS version과 전체 mount option
- client/server kernel, storage 상태와 구간별 workload
- 사용한 PromQL 또는 `samples.tsv` 집계 script와 원본 결과
- exporter command timeout과 scrape interval
- 전환과 동시에 수행한 다른 설정 변경

원본 artifact를 저장소에 추가하면 이 문서의 표 아래에 commit 고정 링크를 추가한다.
