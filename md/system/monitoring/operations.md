# Monitoring 운영

이 문서는 monitoring 구성 요소를 배포하고 endpoint, metric, alert와 incident를
점검하는 방법을 설명한다.

## 운영 원칙

- `up=1`과 실제 collection freshness를 구분한다. HTTP process가 응답해도 마지막
  성공 collection이 오래됐으면 정상으로 판단하지 않는다.
- metric 수집, 증거 보존과 상태 변경을 분리한다. exporter는 mount하지 않고,
  forensics는 service restart나 reboot를 수행하지 않는다.
- NFS caller가 D-state이면 `find`, `du`, `stat`, canary나 recovery를 반복 실행하지
  않고 local state와 이미 수집된 snapshot을 먼저 보존한다.
- 자동 복구 결과는 원래 정상 상태와 구분해 metric과 state에 남긴다. inhibit 또는
  backoff가 설정된 worker를 endpoint 호출로 우회하지 않는다.
- 배포는 `monitoring/ansible_playbook/`을 기준으로 하고 target host의 개별 install
  script를 운영 entry point로 사용하지 않는다.
- DB password, Grafana password, webhook과 Kerberos credential은 metric, alert
  label, Git values와 일반 journal에 기록하지 않는다.

## 1. 배포 순서

새 host 또는 NFS GSS monitoring을 처음 적용할 때는 다음 순서를 권장한다.

1. inventory와 host FQDN/SPN/mount source 확인
2. NFS GSS readiness/canary/recovery worker 설치
3. NFS forensics 설치
4. exporter 배포
5. Prometheus target/rule 반영
6. Grafana datasource/dashboard 확인
7. alert delivery test

운영 배포 entry point는 exporter 내부 개별 shell script가 아니라
`monitoring/ansible_playbook/`이다.

## 2. Exporter 배포

```bash
cd /home/jy/server_manage/monitoring
```

두 exporter를 한 host에 배포:

```bash
ANSIBLE_CONFIG=ansible_playbook/ansible.cfg \
ansible-playbook ansible_playbook/deploy_exporters.yml \
  -e exporter_hosts=farm8
```

FARM 전체 또는 FARM/LAB 전체:

```bash
ANSIBLE_CONFIG=ansible_playbook/ansible.cfg \
ansible-playbook ansible_playbook/deploy_exporters.yml \
  -e exporter_hosts=FARM

ANSIBLE_CONFIG=ansible_playbook/ansible.cfg \
ansible-playbook ansible_playbook/deploy_exporters.yml
```

한 exporter만 전체 재배포:

```bash
ANSIBLE_CONFIG=ansible_playbook/ansible.cfg \
ansible-playbook ansible_playbook/deploy_cluster_monitor_exporter_all.yml

ANSIBLE_CONFIG=ansible_playbook/ansible.cfg \
ansible-playbook ansible_playbook/deploy_gpu_user_exporter_all.yml
```

target에는 다음 systemd service와 endpoint가 생긴다.

```text
cluster-monitor-exporter.service -> :30074/metrics, :30074/healthz, :N89/healthz
gpu-user-exporter.service        -> :30072/metrics, :30072/-/healthy
```

배포 기준과 요구 조건은
[Ansible README](https://github.com/CSID-DGU/admin_infra_server/blob/main/monitoring/ansible_playbook/README.md),
실제 task는 [deploy_exporters.yml](https://github.com/CSID-DGU/admin_infra_server/blob/main/monitoring/ansible_playbook/deploy_exporters.yml)에서 확인한다.

## 3. NFS GSS와 forensics 배포

NFS GSS readiness/canary/recovery worker:

```bash
ANSIBLE_CONFIG=ansible_playbook/ansible.cfg \
ansible-playbook ansible_playbook/deploy_nfs_gss_health.yml \
  -e nfs_gss_health_hosts=lab8
```

NFS forensics:

```bash
ANSIBLE_CONFIG=ansible_playbook/ansible.cfg \
ansible-playbook ansible_playbook/deploy_nfs_forensics.yml
```

중요한 systemd unit과 state:

```text
decs-kerberos-nfs-ready.service
decs-nfs-gss-canary-probe.service/.timer
decs-nfs-gss-mount-recovery.service/.timer
/run/decs-nfs-gss/ready.state
/var/lib/decs-nfs-gss/canary.state
/var/lib/decs-nfs-gss/recovery.state

decs-nfs-forensics-buffer.service
decs-nfs-forensics-watch.service/.timer
decs-nfs-forensics-snapshot.service
/run/decs-nfs-forensics/status.json
/var/lib/decs-nfs-forensics/
```

FARM은 전용 read-only canary export가 준비될 때까지 canary만 비활성화하며
keytab/kinit/kvno/rpc-gssd readiness와 guarded recovery는 유지한다. LAB canary는
`sec=krb5` 전용 read-only export를 사용한다.

## 4. Keytab checker 배포

FARM 읽기 전용 checker:

```bash
ANSIBLE_CONFIG=ansible_playbook/ansible.cfg \
ansible-playbook ansible_playbook/deploy_kerberos_nfs_keytab_check.yml
```

LAB을 상시 점검 대상으로 전환한 뒤에만 두 profile을 활성화한다.

```bash
ANSIBLE_CONFIG=ansible_playbook/ansible.cfg \
ansible-playbook ansible_playbook/deploy_kerberos_nfs_keytab_check.yml \
  -e '{"keytab_check_profiles":["farm","lab"]}'
```

```bash
systemctl --user list-timers 'check-nfs-keytab@*.timer'
systemctl --user status check-nfs-keytab@farm.service --no-pager
```

checker는 drift를 고치지 않는다. KVNO history, repair와 rotation은
[Kerberos/NFS 운영](../kerberos-nfs/operations.md#8-farm-nas-service-account-kvno)을
따른다.

## 5. Prometheus/Alertmanager 배포

먼저 server-side render와 cluster precondition만 검증한다.

```bash
ANSIBLE_CONFIG=ansible_playbook/ansible.cfg \
ansible-playbook ansible_playbook/deploy_prometheus.yml
```

변경 적용:

```bash
ANSIBLE_CONFIG=ansible_playbook/ansible.cfg \
ansible-playbook ansible_playbook/deploy_prometheus.yml \
  -e prometheus_dry_run=false
```

한 환경만 배포하려면 `prometheus_farm_enabled=false` 또는
`prometheus_lab_enabled=false`를 사용한다. playbook은 kubeconfig 대상 cluster,
node Ready/DiskPressure, 필수 Secret 이름을 확인한 후 Helm을 실행한다.

FARM에서 필요한 Secret:

- `monitoring-grafana-admin`: `admin-user`, `admin-password`
- `cluster-monitor-slack-webhook-farm`: `url`

값은 Git values에 넣지 않는다. Alertmanager는 Slack webhook으로 직접 보내지
않고 localhost relay를 거쳐 internal notify API로 보낸다.

현재 control plane의 역할은 다음처럼 구분한다.

- FARM Prometheus는 FARM 자원 metric과 FARM/LAB의
  `cluster-monitor-exporter`를 수집하고 중앙 alert rule을 평가한다.
- FARM Alertmanager와 relay는 FARM/LAB 서비스 경보를 내부 notify API로 보낸다.
- LAB Prometheus는 LAB node/GPU metric을 독립 저장한다. LAB release의 Grafana와
  Alertmanager는 비활성화되어 있다.
- FARM Grafana는 기본 FARM datasource와 `prometheus-lab` datasource를 함께
  사용한다.

## 6. 배포 후 endpoint 확인

target host에서:

```bash
systemctl status cluster-monitor-exporter gpu-user-exporter --no-pager
journalctl -u cluster-monitor-exporter -n 100 --no-pager
journalctl -u gpu-user-exporter -n 100 --no-pager

curl -fsS http://127.0.0.1:30074/healthz
curl -fsS http://127.0.0.1:30074/metrics | head
curl -fsS http://127.0.0.1:30072/-/healthy
curl -fsS http://127.0.0.1:30072/metrics | head
curl -fsS http://127.0.0.1:30070/metrics | head
```

`:30070`의 `node-exporter`는 `kube-prometheus-stack`에서 배포하므로 앞의 두 custom
exporter처럼 host systemd unit을 확인하지 않는다. endpoint가 없으면 그 cluster의
DaemonSet, Service와 node scheduling 상태를 확인한다.

public health port는 서버 번호 `N`에 대해 `9000 + N*100 - 11`이다. 예를 들어
FARM8은 `9789/healthz`다. 이 endpoint는 exporter process/collection freshness와
외부 NAT 도달 경로를 확인하는 용도이며, 모든 dependency가 준비됐음을 보장하지는
않는다.

NFS GSS host-only API:

```bash
curl -fsS http://127.0.0.1:30074/nfs-gss/ready
curl -fsS http://127.0.0.1:30074/nfs-gss/health
curl -fsS -X POST http://127.0.0.1:30074/nfs-gss/probe
curl -fsS -X POST http://127.0.0.1:30074/nfs-gss/recover
```

`probe`와 `recover`는 loopback 요청만 허용하며 worker를 queue한 뒤 즉시
응답한다. `recover`를 반복 호출하기 전에 recovery state와 inhibit reason을
확인한다.

## 7. 무엇을 어디에서 보는가

| 관측 대상 | 대표 metric/alert | 구현/설정 링크 |
| --- | --- | --- |
| CPU, memory, filesystem, disk, network | `node_cpu_*`, `node_memory_*`, `node_filesystem_*`, `node_disk_*`, `node_network_*` | [FARM values](https://github.com/CSID-DGU/admin_infra_server/blob/main/monitoring/prometheus/config/prometheus-farm-values.yaml), [LAB values](https://github.com/CSID-DGU/admin_infra_server/blob/main/monitoring/prometheus/config/prometheus-lab-values.yaml) |
| exporter process와 freshness | `up`, `cluster_monitor_exporter_last_collection_timestamp_seconds`, `ClusterMonitorExporter*` | [collector](https://github.com/CSID-DGU/admin_infra_server/blob/main/monitoring/prometheus/exporters/cluster-monitor-exporter/cmd/cluster-monitor-exporter/main.go), [rules](https://github.com/CSID-DGU/admin_infra_server/blob/main/monitoring/prometheus/config/prometheus-farm-values.yaml) |
| required mount와 latency | `cluster_monitor_host_mount_up`, `..._responsive`, `..._probe_seconds` | [mount collector](https://github.com/CSID-DGU/admin_infra_server/blob/main/monitoring/prometheus/exporters/cluster-monitor-exporter/cmd/cluster-monitor-exporter/main.go), [storage dashboards](https://github.com/CSID-DGU/admin_infra_server/tree/main/monitoring/grafana/dashboards) |
| Kerberos NFS readiness | `cluster_monitor_nfs_gss_ready`, `ClusterMonitorNFSGSSReadinessFailed` | [readiness](https://github.com/CSID-DGU/admin_infra_server/blob/main/monitoring/prometheus/exporters/cluster-monitor-exporter/script/decs_nfs_gss_ready.sh), [GSS collector](https://github.com/CSID-DGU/admin_infra_server/blob/main/monitoring/prometheus/exporters/cluster-monitor-exporter/cmd/cluster-monitor-exporter/nfs_gss_health.go) |
| canary/recovery | `cluster_monitor_nfs_gss_canary_*`, `..._recovery_*` | [canary](https://github.com/CSID-DGU/admin_infra_server/blob/main/monitoring/prometheus/exporters/cluster-monitor-exporter/script/decs_nfs_gss_canary_probe.sh), [recovery](https://github.com/CSID-DGU/admin_infra_server/blob/main/monitoring/prometheus/exporters/cluster-monitor-exporter/script/decs_nfs_gss_mount_recovery.sh) |
| D-state, lease, hung task | `cluster_monitor_host_dstate_*`, `cluster_monitor_nfs_*`, `ClusterMonitorNFS*` | [forensics adapter](https://github.com/CSID-DGU/admin_infra_server/blob/main/monitoring/prometheus/exporters/cluster-monitor-exporter/cmd/cluster-monitor-exporter/nfs_forensics.go), [forensics scripts](https://github.com/CSID-DGU/admin_infra_server/tree/main/monitoring/nfs-forensics) |
| host GPU/Docker/container | `cluster_monitor_host_gpu_up`, `...docker_daemon_up`, `...container_*` | [cluster collector](https://github.com/CSID-DGU/admin_infra_server/blob/main/monitoring/prometheus/exporters/cluster-monitor-exporter/cmd/cluster-monitor-exporter/main.go) |
| 사용자별 GPU | `docker_gpu_user_memory_used_bytes`, `...sm_utilization_percent`, `...process_count` | [gpu-user-exporter](https://github.com/CSID-DGU/admin_infra_server/blob/main/monitoring/prometheus/exporters/gpu-user-exporter/main.go), [GPU dashboard](https://github.com/CSID-DGU/admin_infra_server/blob/main/monitoring/grafana/dashboards/gpu-usage-dashboards.yaml) |
| 외부 연결 | `cluster_monitor_external_connectivity_*`, public health | [exporter](https://github.com/CSID-DGU/admin_infra_server/blob/main/monitoring/prometheus/exporters/cluster-monitor-exporter/cmd/cluster-monitor-exporter/main.go), [Apps Script](https://github.com/CSID-DGU/admin_infra_server/blob/main/monitoring/prometheus/exporters/cluster-monitor-exporter/google-apps-script/external_connectivity_monitor.gs) |
| AD/NAS keytab | checker JSON/exit code | [keytab checker](https://github.com/CSID-DGU/admin_infra_server/tree/main/monitoring/health-checks/kerberos-nfs-keytab) |

canonical alert rule은
[prometheus-farm-values.yaml](https://github.com/CSID-DGU/admin_infra_server/blob/main/monitoring/prometheus/config/prometheus-farm-values.yaml)이다.
exporter 내부 `prometheus/cluster_monitor_alerts.yml`은 metric 이름을 보여 주는
reference이며 실제 FARM release와 값이 다를 수 있다.

## 8. Alert별 진단 순서

### Exporter down 또는 stale

1. Prometheus target에서 connection error와 scrape timestamp를 구분한다.
2. target systemd status/journal을 확인한다.
3. `:30074/healthz`와 `/metrics`를 각각 확인한다.
4. process는 살아 있지만 stale이면 마지막 실행 command와 D-state를 확인한다.
5. 변경된 env/config와 binary 배포 시간을 확인한 뒤 exporter만 재배포한다.

### Required mount down/slow/unresponsive

1. `findmnt`로 mount 존재, FQDN source, filesystem과 `sec`를 확인한다.
2. mount probe와 storage ping/peer diagnosis label을 확인한다.
3. GSS readiness에서 처음 실패한 stage를 확인한다.
4. D-state, lease expiry, hung-task와 local forensic snapshot을 확인한다.
5. mount가 없을 때만 recovery state를 확인한다.
6. mount가 이미 있거나 D-state caller가 있으면 강제 remount를 반복하지 않는다.

Kerberos source는 IP가 아니라 FQDN이어야 한다. 자세한 기준은
[Kerberos/NFS 운영의 mount 절](../kerberos-nfs/operations.md#5-nfs-mount-source)을
따른다.

### GSS readiness/canary/recovery

```bash
systemctl status decs-kerberos-nfs-ready.service --no-pager
systemctl status decs-nfs-gss-canary-probe.timer --no-pager
systemctl status decs-nfs-gss-mount-recovery.timer --no-pager
journalctl -u decs-kerberos-nfs-ready.service -n 100 --no-pager
cat /run/decs-nfs-gss/ready.state
cat /var/lib/decs-nfs-gss/canary.state
cat /var/lib/decs-nfs-gss/recovery.state
```

- keytab/kinit stage: host machine credential 확인
- kvno stage: DNS/FQDN/SPN/KDC 확인
- rpc-gssd stage: service와 잘못된 `-n` override 확인
- canary stage: 전용 export와 user share를 혼동하지 않았는지 확인
- inhibited recovery: D-state 또는 mount timeout 증거를 보존하고 원인을 처리

### GPU 사용자 mapping 이상

1. `nvidia-smi`와 exporter scrape success를 확인한다.
2. ignored process count가 증가했는지 확인한다.
3. PID의 cgroup container ID와 Docker inspect를 비교한다.
4. DB cache refresh success와 cache age/entry를 확인한다.
5. DB record와 실제 running container가 어긋났다면 user-lifecycle에서 관리하는 절차로
   고친다.

### Container SSH/GPU alert

1. container가 running인지 먼저 확인한다.
2. exporter가 start/SSH/NVML recovery를 시도했는지 metric과 journal을 확인한다.
3. container image가 configured regex 대상인지 확인한다.
4. NVML mismatch가 아니라 application/GPU allocation 문제면 자동 symlink repair를
   반복하지 않는다.

## 9. Grafana 점검

- LAB dashboard datasource UID가 `prometheus-lab`인지 확인한다.
- dashboard query의 `cluster`, `server_id`, `job` label이 scrape config와 일치하는지
  확인한다.
- storage dashboard에서 mount probe, responsive, D-state, blocked process,
  hung-task를 같은 시간축으로 비교한다.
- GPU dashboard에서 DB-known 사용자 metric과 device 전체 metric을 함께 본다.
- 새 server 추가 시 dashboard에 hard-coded server/GPU panel 누락이 없는지 확인한다.

dashboard 원본:

- [FARM storage latency](https://github.com/CSID-DGU/admin_infra_server/blob/main/monitoring/grafana/dashboards/storage-latency-farm-dashboard.yaml)
- [LAB storage latency](https://github.com/CSID-DGU/admin_infra_server/blob/main/monitoring/grafana/dashboards/storage-latency-lab-dashboard.yaml)
- [GPU usage](https://github.com/CSID-DGU/admin_infra_server/blob/main/monitoring/grafana/dashboards/gpu-usage-dashboards.yaml)
- [Network traffic](https://github.com/CSID-DGU/admin_infra_server/blob/main/monitoring/grafana/dashboards/network-traffic-dashboards.yaml)

## 10. 테스트

```bash
cd /home/jy/server_manage/monitoring

(cd prometheus/exporters/cluster-monitor-exporter && go test ./...)
(cd prometheus/exporters/gpu-user-exporter && go test ./...)
bash nfs-forensics/tests/test_watch.sh
bash prometheus/exporters/cluster-monitor-exporter/tests/test_nfs_gss_ready.sh
bash prometheus/exporters/cluster-monitor-exporter/tests/test_nfs_gss_mount_recovery.sh
python3 prometheus/config/tests/test_slack_notify_relay.py
```

변경 위험에 맞게 최소한 다음을 함께 검증한다.

- metric 이름/type/help와 0/failure path
- recovery가 healthy mount를 건드리지 않는지
- D-state에서 mount attempt가 차단되지만 existing mount는 healthy로 처리되는지
- Alertmanager relay가 secret을 출력하지 않고 internal API payload로 변환하는지
- FARM/LAB dashboard datasource가 바뀌지 않았는지

## 11. 새 서버 추가 체크리스트

1. `ansible_playbook/inventory.ini`에 `farmN`/`labN` 형식으로 추가
2. `group_vars/exporters.yml`의 mount source, SPN과 환경 기본값 확인
3. host share target와 public `N89` port 계산 확인
4. GSS readiness/forensics/exporter 배포
5. Prometheus `:30070`, `:30072`, `:30074` scrape target 추가
6. 방화벽/NAT public health 확인
7. Grafana dashboard server/GPU panel 확인
8. alert rule label과 Alertmanager route 확인
9. endpoint와 실제 alert delivery 검증

## 12. 운영 문서에 계속 추가할 내용

설계와 운영을 분리한 뒤 다음 정보를 운영 문서에 누적하면 좋다.

- 서비스별 owner, endpoint, systemd/Kubernetes resource와 dependency
- metric별 정상 범위, alert `for`와 runbook link
- 최근 배포 version/commit과 마지막 검증 시각
- FARM/LAB retention, PV 용량과 capacity threshold
- alert silence 승인/만료 기준과 false-positive 기록
- 자동 복구별 시도 횟수, inhibit 해제와 rollback 절차
- incident snapshot 보존 기간, 접근 권한과 개인정보 취급
- 새 server/metric/dashboard 추가 checklist

설계 문서에는 구성 요소의 관계와 안전 경계를 유지하고, host별 현재 값과 일회성
incident 결과는 canonical config/runbook 또는 별도 evidence에 기록한다.
