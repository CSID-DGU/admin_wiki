# server-state 운영

> [개요](index.md) · [설계](design.md)

## 1. 운영 서버 점검 흐름

### 1.1 `existing-host-drift`란?

`existing-host-drift`는 `config/profiles.yml`에 정의된 **점검 항목
묶음의 이름**이다. 그 안에는 접속 확인(baseline-host)부터 os-common,
docker-engine, nvidia-driver, nvidia-container-runtime, kubernetes-node,
network-tuning, kerberos-nfs-client, monitoring-exporters,
user-container-host까지 10개 영역이 순서대로 들어 있다. "운영 중인
FARM/LAB 서버가 이 10개 영역의 공통 기준을 다 지키고 있는지 확인하는
점검표"라고 보면 된다.

실제로 실행하는 스크립트는 `./server-state/bin/server-state`이고, 내부
동작은 `script/cli.py`가 맡는다. `cli.py`가 `config/profiles.yml`을
읽어서 `existing-host-drift`에 묶인 10개 영역의 점검·복구 항목을 순서대로
꺼내 쓰는 구조다.

### 1.2 "명령어를 만들어서 보여준다"는 게 무슨 뜻인가

`profiles.yml`에는 완성된 명령이 아니라, `{host}`나 `{repo}` 같은
자리표시자가 들어간 **명령 틀**만 적혀 있다. 예를 들어 `os-common`
영역의 점검 항목 하나는 실제로 다음과 같이 정의되어 있다.

```yaml
# config/profiles.yml (os-common 영역의 점검 항목 중 하나)
command: "ANSIBLE_CONFIG={repo}/monitoring/ansible_playbook/ansible.cfg \
  ansible {host} -b -m shell -a '. /etc/os-release && test \"$ID\" = ubuntu ...'"
```

`check` 명령을 실행하면 `script/cli.py`가 이 틀의 `{host}`를 실제 서버
이름(`farm8`)으로, `{repo}`를 실제 저장소 경로로 바꿔 채운 뒤, 그 결과
문자열을 화면에 출력만 한다. 예시:

```text
$ ./server-state/bin/server-state check --hosts farm8 --profile os-common
farm8 [os-common] ubuntu-release: DRY-RUN
  detail: ANSIBLE_CONFIG=/home/jy/server_manage/monitoring/ansible_playbook/ansible.cfg ansible farm8 -b -m shell -a '. /etc/os-release && test "$ID" = ubuntu && printf "%s\n" "$VERSION_ID"'
```

`detail:` 뒤에 나온 문자열이 "만들어서 보여준 명령"이다. `server-state`는
자리표시자를 채운 문자열을 Python에서 만들어 출력하기만 할 뿐, 이 명령을
실제로 실행(예: `subprocess` 호출)하지 않는다. 서버 상태를 실제로
확인하려면 관리자가 이 문자열을 복사해서 직접 실행해야 한다.

### 1.3 전체 점검 흐름

아래 5단계 중 실제로 서버 상태가 바뀌는 건 5번뿐이고, 그마저도 관리자가
직접 실행해야만 일어난다.

1. **점검 대상 서버 선택** — 공용 inventory(3절 "공용 inventory와 서버
   목록" 참고)에서 `--hosts` 조건(`all`, `farm8` 등)에 맞는 서버를
   로컬에서 골라낸다. 서버에 접속하지 않는다.
2. **점검 항목 생성** — `config/profiles.yml`의 `existing-host-drift`
   profile을 서버별 변수(hostname, IP 등)로 채워 로컬에서 명령 목록을
   만든다. 서버에 접속하지 않는다.
3. **점검 명령을 DRY-RUN으로 출력** — 서버별로 실행하면 될 읽기 전용
   Ansible 명령을 화면에 보여줄 뿐, 실행하거나 서버에 접속하지 않는다.
4. **복구 명령을 DRY-RUN으로 출력** — 3번에서 차이가 발견된 항목에 한해
   복구용 Ansible 명령(`--check --diff` 포함)을 보여준다. 역시 실행하지
   않는다.
5. **관리자가 검토 후 직접 실행** — 3, 4번에서 출력된 명령을 관리자가
   그대로 복사해 실행해야 서버 상태가 바뀐다. `server-state`는 이 단계를
   대신 실행하지 않는다.

실제 명령은 다음과 같다. 1~3번 단계가 `check` 한 번으로 함께 실행된다.

```bash
cd /home/jy/server_manage

# 전체 서버의 점검 항목 확인
./server-state/bin/server-state check \
  --hosts all \
  --profile existing-host-drift

# 특정 서버(farm8)만 확인
./server-state/bin/server-state check \
  --hosts farm8 \
  --profile existing-host-drift
```

두 명령 모두 서버에 접속하거나 서버 상태를 바꾸지 않는다. 화면에 출력된
`DRY-RUN` 명령을 관리자가 직접 실행하거나, 별도 자동화가 그 명령을
실행하도록 연결해야 실제 점검(3번 단계 이후)이 이루어진다.

4번 단계, 즉 차이가 있을 때 사용할 복구 명령만 먼저 볼 수도 있다.

```bash
./server-state/bin/server-state plan \
  --hosts farm8 \
  --profile existing-host-drift
```

## 2. 신규 서버 구축 흐름

새 서버를 운영 서버와 같은 상태로 만드는 것이 `new-host-bootstrap`의
목적이다. 다만 아무것도 설치되지 않은 장비의 전원 투입부터 전부 처리하는
형태는 아니다. 다음 조건은 먼저 준비되어 있어야 한다.

- Ubuntu가 설치되어 있다.
- IP, hostname과 SSH 접속이 준비되어 있다.
- 관리 계정이 비대화형 sudo를 사용할 수 있다.
- 서버가 공용 inventory에 등록되어 있다.

이후 표준 설치 순서를 확인한다.

```bash
./server-state/bin/server-state plan \
  --hosts farm8 \
  --profile new-host-bootstrap
```

`ansible_playbook/bootstrap_gpu_server.yml`에는 package 설치와 설정 파일 변경을
실제로 수행하는 idempotent task가 들어 있다. 각 단계는 tag로 나뉘며, 먼저
생성된 명령의 host, tag와 변수를 확인한 뒤 `--check --diff`로 예상 변경을
검토한다. 실제 적용은 검토가 끝난 Ansible 명령에서 `--check`를 제거하여
관리자가 실행한다.

다음 항목은 공통 설정이라도 자동으로 밀어 넣지 않고 별도 승인을 요구한다.

- NVIDIA driver 변경: reboot와 실행 중 GPU workload 조정이 필요하다.
- Kubernetes join: cluster별 token과 controller 승인이 필요하다.
- Kerberos machine keytab: FARM과 LAB의 도메인 가입 방식이 다르고 secret을
  안전하게 전달해야 한다.
- Kerberos NFS mount: 실행 중 container와 사용자 session에 영향을 줄 수 있다.

Kerberos/NFS의 상세 점검과 복구 순서는
[Kerberos/NFS 매뉴얼](../kerberos-nfs/index.md)에서 관리한다.

현재 `apply`도 실제 변경 없이 복구 계획만 출력한다.

```bash
./server-state/bin/server-state apply \
  --hosts farm8 \
  --profile existing-host-drift
```

`apply --execute`는 아직 구현되지 않았으며 실행하면 오류로 중단된다.

## 3. 공용 inventory와 서버 목록

기본 inventory는 `user-lifecycle/server_info/servers.jsonl`이다. 서버 한
대당 한 줄(JSON)로 host 이름, `server_id`, domain(FARM/LAB), SSH 접속 정보
(`ansible_host`, `ansible_port`, `ansible_user`), 네트워크 인터페이스, OS
버전 등을 담는다. 이 파일은 사람이 손으로 쓰지 않는다.
`user-lifecycle/server_info/generate_servers_jsonl.py`가 Ansible `setup`
facts(각 서버에서 실제로 수집한 정보)와 고정 topology 정보를 합쳐서 만든
결과물이다.

이 파일은 원래 `user-lifecycle`(사용자·container 생성)이 관리하던 서버
목록이다. `server-state`는 점검할 서버 목록이 필요할 때 이 파일을 그대로
읽어서 쓰고("공용" inventory), 자신만의 목록을 별도로 만들지 않는다. IP,
SSH port와 논리 server ID를 두 군데에서 따로 관리하면 서로 달라지는
문제가 생기기 때문이다. `server-state`의 `script/inventory.py`가 이
파일을 읽어서 `--hosts` selector에 맞는 서버를 골라낸다.

```bash
./server-state/bin/server-state list-hosts --hosts all
./server-state/bin/server-state list-hosts --hosts farm
./server-state/bin/server-state list-hosts --hosts farm8,lab10
```

selector는 `all`, `farm`, `lab`, 개별 host 이름과 여러 host 조합을 지원한다.

## 4. 공통 설정 추가 방법

1. 설정을 실제로 관리할 모듈을 정한다.
2. `config/profiles.yml`에 작은 profile을 추가한다.
3. 부작용 없이 읽을 수 있는 항목만 `checks`에 둔다.
4. 복구는 가능하면 Ansible `--check --diff` 명령부터 제공한다.
5. driver, cluster join, keytab과 mount처럼 위험한 작업은 `manual` 또는
   `gated`로 둔다.
6. 모든 서버에 필요한 설정이면 `new-host-bootstrap`과
   `existing-host-drift`에 모두 추가한다.
7. profile 순서와 서버별 변수 치환 test를 추가한다.

## 5. 테스트

```bash
cd /home/jy/server_manage/server-state
python3 -m unittest discover -s tests -v

./bin/server-state --format json check \
  --hosts farm8 \
  --profile existing-host-drift

./bin/server-state plan \
  --hosts lab10 \
  --profile new-host-bootstrap
```

테스트와 dry-run 출력에서는 실제 운영 서버를 변경하지 않는다.
