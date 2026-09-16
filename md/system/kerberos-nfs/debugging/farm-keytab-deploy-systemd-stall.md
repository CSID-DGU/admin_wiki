# keytab 배포가 100초 넘게 걸린 원인 — 로그인마다 뜨는 소리 서버

## 1. 상태와 영향 범위

| 항목 | 내용 |
| --- | --- |
| 검증일 | 2026-09-16 |
| 상태 | 원인 확정, 영구 조치 적용·운영 검증 완료 |
| 대상 | FARM 노드 전체(증상은 FARM6·FARM9에서 상시, FARM2에서도 간헐 관측) |
| 환경 | Ubuntu 22.04, systemd 249.11 |
| 영향 | keytab 배포(`DEPLOY_KRB5`) 104~114초, 컨테이너 생성·마이그레이션 지연. 같은 시간대의 `sudo`, 신규 로그인도 함께 멈춤 |

Kerberos 자체의 문제가 아니라 **systemd 본체(PID 1)가 최대 90초 멈추는 문제**였다.

## 2. 증상

- 작업 이력에서 FARM6는 세 번 모두 정확히 104.1초, FARM9는 113.7초. FARM2는 1.4초.
- config-server는 farm SSH를 60초에 끊고 재시도한다. 로그에 `타임아웃, 재시도 1/2` 뒤
  재시도가 44~54초 만에 성공하는 패턴이 반복됐다.
- 같은 시각 노드에 접속해 `sudo`를 실행하면 비밀번호 입력 후 응답이 없다가 풀렸다.

## 3. 확인한 사실과 가설

배제한 가설과 근거는 다음과 같다.

| 가설 | 근거 |
| --- | --- |
| kinit이 KDC를 기다린다 | `KRB5_TRACE` 측정에서 KDC 왕복 0.01초, KDC 3대 모두 88 포트 즉시 연결 |
| DNS가 느리다 | `dns_lookup_kdc = false`, 주소 조회 0.00초 |
| systemd generator가 멈춘다 | 17개를 임시 디렉터리로 단독 실행해 전부 0.01~0.03초 |
| 스케줄러(10초 간격 SSH)가 원인이다 | FARM2와 FARM9의 로그인 빈도가 거의 같은데 FARM2만 빨랐다 |
| 노드 부하·NFS 고착이 원인이다 | FARM9는 CPU 65% 유휴·D-state 0. FARM6의 D-state 63개는 k8s NFS CSI가 5일 전 남긴 잔재로, systemd를 붙잡지 않는다 |

확정한 사실은 다음과 같다.

- systemd 본체 로그가 `Reloading.` 직후 **정확히 90.1초** 비어 있다(두 번 모두).
- 5초마다 도는 감시 타이머(`decs-nfs-forensics-watch`) 기록도 같은 구간에서 94초 비었다.
  타이머가 안 돌았다는 것은 PID 1이 멈춰 있었다는 뜻이다.
- 멈춤이 풀린 시각이 그 세션 소리 서버의 시작 제한 90초가 끝난 시각과 일치한다
  (`pulseaudio.service: start operation timed out`).
- 그 앞에는 항상 `dbus-daemon: Failed to activate service 'org.bluez': timed out (25000ms)`가
  있었다.

## 4. 인과 경로

1. config-server가 서비스 계정 `ailab-krb5`로 SSH 접속한다.
2. systemd가 그 계정의 사용자 세션(`user@<uid>.service`)을 띄운다.
3. 데스크톱 패키지가 깔려 있어 사용자 세션에서 **소리 서버(PulseAudio)가 자동 시작**된다.
4. PulseAudio가 시스템 D-Bus에 블루투스 서비스(`org.bluez`) 실행을 요청한다. 노드에
   블루투스 장치가 없어 응답이 오지 않고 25초 시간 초과가 난다.
5. 배포 스크립트가 로그인 0.1초 뒤 `daemon-reload`를 요청한다. PID 1이 위 대기에 얽혀
   **소리 서버 시작 제한 90초가 끝날 때까지 멈춘다.**
6. 그동안 `sudo` 세션 등록, 다른 로그인, timer 등록도 함께 멈춘다.

FARM2가 빨랐던 것은 구조가 달라서가 아니라 이 경합을 피했기 때문이다. 실제로 이후
FARM2에서도 113.3초가 한 번 관측됐다.

당시 스크립트는 **내용이 같은 unit 파일을 배포마다 덮어썼다.** 파일 시각이 바뀌면
systemd가 재로딩을 요구하므로, 재로딩이 필요한 상황을 스스로 만들고 있었다.

## 5. 재현 조건

- 노드에 데스크톱 패키지(PulseAudio)와 D-Bus 블루투스 활성화 파일이 있고, 블루투스
  장치는 없다.
- 로그인으로 새 사용자 세션이 뜬 직후 1초 안에 `daemon-reload`가 들어온다.

## 6. 실행 명령

```bash
# 멈춘 구간(systemd 본체와 커널)
sudo journalctl _PID=1 --since "<시작>" --until "<끝>" -o short-precise --no-pager
sudo journalctl --since "<시작>" --until "<끝>" --no-pager \
  | grep -iE "bluez|pulseaudio|timed out|Reloading"

# 5초 간격 감시 기록의 공백 = PID 1이 멈춘 구간
awk -F'\t' 'NR>2 && $1-p>15 {print strftime("%H:%M:%S",p), strftime("%H:%M:%S",$1), $1-p} NR>1{p=$1}' \
  /run/decs-nfs-forensics/samples.tsv

# 배포 경로 중 systemd를 거치지 않는 구간만 측정(정상이면 0.3초 내외)
#   config-server에서 forced-command의 list 동작 호출
```

## 7. 결과와 판정 기준

| 구간 | 조치 전 | 조치 후 |
| --- | --- | --- |
| keytab 배포 | FARM6 104.1초, FARM9 113.7초 | 0.4~1.2초 |
| keytab 정리 | 1.5초 | 1.2~1.3초 |
| 마이그레이션 전체 | 271초 | 10~11초 |
| PID 1 멈춤 | 6시간 관측 구간에서 2회(94초) | 전역 적용 후 0회 |

판정 기준은 두 가지다. 두 번째 배포에서 unit 파일 수정 시각이 바뀌지 않을 것(재로딩을
하지 않았다는 뜻), 그리고 감시 기록에 15초 이상 공백이 생기지 않을 것.

## 8. 복구와 예방

영구 조치는 `admin_infra_server` #15·#20으로 적용했다.

- 노드에 수동 설치돼 있던 `/usr/local/sbin/ailab-krb5-admin`을 저장소로 옮기고
  (`kerberos-nfs/script/farm/`), **내용이 달라졌을 때만** 쓰고 그때만 재로딩하도록 변경.
  `systemctl enable`의 자체 재로딩도 `--no-reload`로 제외.
- 첫 ticket은 systemd를 거치지 않고 갱신 스크립트를 직접 실행해 발급하고, 그 뒤에 timer를
  등록한다. timer 등록 실패는 조용히 넘기지 않는다(티켓이 24시간 뒤 만료되므로).
- systemd 호출 대기를 120초로 둔다. 남의 세션이 만든 멈춤(최대 90초)을 견디기 위해서다.
- 플레이북(`kerberos-nfs/ansible/deploy_farm_krb5_admin.yml`)이 FARM 6대에 배포하고,
  노드 전역에서 소리 서버를 끈다. 끄기 전에 확인한 내용은 다음과 같다.
    - 소리 서버를 띄우고 있는 것은 로그인 화면 계정과 진단 접속뿐이다.
    - 사용자 원격 데스크톱(VNC)은 컨테이너 안에서 돌아 host 설정과 무관하다.
    - FARM6의 xrdp는 소리 전달 설정만 있고 모듈이 없어 동작하지 않는다.
  되돌리려면 `/etc/systemd/user/pulseaudio.{service,socket}` 링크 두 개를 지운다.

## 9. 원본 증거

- 작업 이력: `operation_state_db.operation_log`의 `DEPLOY_KRB5`·`REMOVE_KRB5` 행
  (2026-09-15 12:41 ~ 2026-09-16 02:07 UTC)
- 노드 일지: FARM9 2026-09-16 01:08:18~01:09:48, 01:26:34~01:28:04 (KST),
  FARM6 01:23:08~01:24:38 (KST)
- 감시 기록: FARM9 `/run/decs-nfs-forensics/samples.tsv`
- 저장소: `admin_infra_server` PR #15, #20, 문서 `kerberos-nfs/docs/farm-krb5-admin.md`
- 운영 절차: [Kerberos/NFS 운영 9장](../operations.md#keytab-deploy-slow)
