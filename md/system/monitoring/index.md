# Monitoring

> 역할: FARM/LAB 서버, NFS, GPU와 사용자 container의 실행 상태를 반복 관측하고,
> Prometheus·Grafana·Alertmanager를 통해 시각화와 경보를 제공한다.

이 문서는 monitoring 문서의 시작점이다. **설계**는 수집 데이터가 어떤
component를 거쳐 metric과 alert가 되는지 설명하고, **운영**은 배포·점검·장애
대응 명령과 코드 위치를 설명한다.

## 문서 구성

| 문서 | 핵심 내용 |
| --- | --- |
| 현재 페이지 | 책임 범위, 핵심 component와 운영 원칙 |
| [설계](design.md) | exporter, Prometheus, Grafana, Alertmanager, GSS health와 forensics의 데이터 흐름 |
| [운영](operations.md) | 배포, endpoint 점검, metric/alert 코드 링크, 장애별 진단 순서 |

## 한눈에 보는 구조

```text
FARM/LAB host
  ├─ gpu-user-exporter :30072
  ├─ cluster-monitor-exporter :30074 + public :N89/healthz
  ├─ node-exporter :30070
  ├─ NFS GSS readiness/canary/recovery systemd worker
  └─ NFS forensics ring/watch/snapshot
             │ scrape/status
             ▼
FARM Prometheus ─┐
                 ├─ FARM Grafana ─ dashboard
LAB Prometheus ──┘
       │ rules
       ▼
Alertmanager -> localhost relay -> internal Slack notify API
```

## 핵심 component

| component | endpoint/산출물 | 역할 |
| --- | --- | --- |
| `gpu-user-exporter` | `:30072/metrics`, `:30072/-/healthy` | GPU process를 DB의 실제 사용자/container에 귀속 |
| `cluster-monitor-exporter` | `:30074/metrics`, `:30074/healthz` | mount, GSS, GPU, Docker, container, 연결성, D-state 수집 |
| public health listener | 서버별 `N89/healthz` | 외부에서 NAT와 host 도달 가능성 확인 |
| NFS GSS worker | `/run`·`/var/lib` state | readiness, canary와 guarded missing-mount recovery |
| NFS forensics | status JSON, local incident snapshot | 제한된 packet/kernel trace를 보존 |
| keytab health check | profile status JSON | AD KVNO, storage keytab과 GSS service drift를 읽기 전용 확인 |
| Prometheus/Alertmanager | cluster별 Kubernetes release | scrape, rule 평가, alert routing |
| Grafana | FARM NodePort `30080` | FARM/LAB datasource와 dashboard를 한 UI에서 제공 |

## 운영 경계

- 지속 관측은 `monitoring`, 부팅 orchestration은 `remote-operations`, host desired
  state는 `server-state`가 소유한다.
- `cluster-monitor-exporter`가 직접 mount하지 않는다. 별도 systemd recovery
  worker가 fstab, DNS/RPC, Kerberos readiness, canary와 D-state gate를 통과한
  **missing mount만** 복구한다.
- keytab checker는 AD password, NAS keytab, service와 mount를 변경하지 않는다.
- forensics는 증거를 수집할 뿐 mount/restart/reboot를 수행하지 않는다.
- 자동 복구는 stopped container 시작, SSH 시작, 안전성이 확인된 NVML symlink
  repair처럼 영향 범위가 제한된 작업에만 사용한다.
- FARM과 LAB Prometheus는 장애와 저장소를 분리하고, Grafana dashboard만 공통
  UI에서 datasource UID와 cluster label로 구분한다.

## 주요 코드

- [cluster-monitor-exporter](https://github.com/CSID-DGU/admin_infra_server/tree/main/monitoring/prometheus/exporters/cluster-monitor-exporter)
- [gpu-user-exporter](https://github.com/CSID-DGU/admin_infra_server/tree/main/monitoring/prometheus/exporters/gpu-user-exporter)
- [Prometheus/Alertmanager 설정](https://github.com/CSID-DGU/admin_infra_server/tree/main/monitoring/prometheus/config)
- [Grafana dashboards](https://github.com/CSID-DGU/admin_infra_server/tree/main/monitoring/grafana/dashboards)
- [monitoring Ansible](https://github.com/CSID-DGU/admin_infra_server/tree/main/monitoring/ansible_playbook)
- [NFS forensics](https://github.com/CSID-DGU/admin_infra_server/tree/main/monitoring/nfs-forensics)
- [Kerberos/NFS keytab checker](https://github.com/CSID-DGU/admin_infra_server/tree/main/monitoring/health-checks/kerberos-nfs-keytab)

Kerberos credential과 FQDN mount 원칙은 [Kerberos/NFS 설계](../kerberos-nfs/design.md),
KVNO·timer·mount 장애 절차는 [Kerberos/NFS 운영](../kerberos-nfs/operations.md)을
함께 참고한다.
