# server-state 운영

> [개요](index.md) · [설계](design.md)

## 1. 기존 서버 점검 흐름

기존 FARM/LAB 서버에서는 `existing-host-drift` profile을 사용한다.

```text
공용 inventory에서 서버 선택
  -> 공통 기준의 점검 항목 생성
  -> 서버별 읽기 전용 명령 확인
  -> 차이가 있는 항목의 복구 계획 확인
  -> 담당 관리자가 승인한 playbook 실행
```

전체 서버 또는 특정 서버의 점검 항목을 확인하는 명령은 다음과 같다.

```bash
cd /home/jy/server_manage

./server-state/bin/server-state check \
  --hosts all \
  --profile existing-host-drift

./server-state/bin/server-state check \
  --hosts farm8 \
  --profile existing-host-drift
```

여기서 주의할 점은 현재 `check`가 실제 서버에 접속하여 결과를 수집하는
명령은 아니라는 것이다. 서버별로 실행할 읽기 전용 Ansible 명령을
`DRY-RUN`으로 출력한다. 따라서 현재 단계에서는 관리자가 출력된 명령을
실행하거나, 별도 자동화가 그 명령을 실행해야 실제 상태를 알 수 있다.

복구에 사용할 명령도 실행하지 않고 먼저 확인할 수 있다.

```bash
./server-state/bin/server-state plan \
  --hosts farm8 \
  --profile existing-host-drift
```

## 2. 신규 서버 구축 흐름

새 서버를 기존 서버와 같은 상태로 만드는 것이 `new-host-bootstrap`의
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

## 3. 공용 서버 목록

기본 inventory는 `user-lifecycle/server_info/servers.jsonl`이다.
`server-state`가 별도 서버 목록을 만들지 않는 이유는 IP, SSH port와 논리
server ID를 두 군데에서 관리하여 서로 달라지는 문제를 막기 위해서다.

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
