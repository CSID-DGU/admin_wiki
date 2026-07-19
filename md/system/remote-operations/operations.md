# remote-operations 운영

> [개요](index.md) · [설계](design.md) · [설정](config.md)

## 1. 사용법

target 확인과 수동 WOL (`admin_infra_server/remote-operations`에서 실행):

```bash
./script/wake_targets.sh --list-targets
./script/wake_targets.sh FARM1 LAB1
```

한 서버의 boot health:

```bash
./script/check_server_boot_health.sh --server-id FARM1
```

한 서버의 기존 container 시작/post-check:

```bash
./script/restart_all_remote_containers.sh FARM1
```

systemd 설치와 확인:

```bash
./script/install_remote_boot_service.sh
sudo systemctl start remote-boot.service
systemctl status remote-boot.service
journalctl -u remote-boot.service -b
```

## 2. dry-run과 검증

```bash
./test/dry_run_remote_boot.sh wake FARM1 LAB1
./test/dry_run_remote_boot.sh health FARM1
./test/dry_run_remote_boot.sh containers FARM1
./test/dry_run_remote_boot.sh full FARM1 LAB1
```

dry-run은 sleep, WOL, Ansible 변경과 Docker 작업 대신 계획을 기록한다. 설정
파싱, target 분할과 단계 순서를 production 영향 없이 검증하기 위한 공개
계약이다.

실제 연결을 확인할 때:

```bash
./test/integration_smoke_test.sh
```

Slack 알림 설정을 확인할 때:

```bash
./test/test_slack_notification.sh --server-id FARM1
```

`REMOTE_BOOT_SLACK_ENABLED`와 webhook URL이 설정돼 있어야 하며, 테스트
메시지를 실제로 전송해 alert 경로가 살아있는지 확인한다.

운영 전에는 최소한 다음을 확인한다.

- MAC/broadcast IP와 Ansible host가 같은 물리 서버를 가리키는지
- gate timeout이 선택된 서버 전체가 동시에 부팅되는 시간을 감안해도 충분한지
- 실패 알림에 비밀값이 포함되지 않는지

## 3. 실패 처리 원칙

- 선택된 대상 중 gate를 통과하지 못한 서버가 있으면 container 재시작 단계로
  넘어가지 않는 것이 기본이다.
- gate 단계에서 서버별 통과/대기 상태를 구분해 기록한다 (`wait_for_priority_servers.sh`가
  통과한 서버와 재시도 중인 서버를 분리해서 로그로 남긴다).
- mount 또는 GPU 문제를 부팅 script에서 무제한 복구하지 않는다. 반복 상태는
  `monitoring`으로 넘기고, Kerberos/NFS 고위험 복구는 해당 runbook을 따른다.
- 실제 사용자 container의 DB record나 Docker 옵션을 부팅 script에서 다시
  만들지 않는다.

## 4. 새 서버 추가

1. `user-lifecycle/server_info/servers.jsonl`과 Ansible inventory에 서버를
   등록한다.
2. local env의 FARM/LAB target 목록과 MAC을 추가한다.
3. 필요한 경우 필수 mount template를 정한다.
4. WOL dry-run과 개별 WOL을 확인한다.
5. 개별 boot health check를 실행한다.
6. container restart를 한 서버에 제한해 검증한다.
7. `monitoring`의 scrape target/exporter 배포를 별도로 완료한다.
