# kdc-setup 설정

> [개요](index.md) · [설계](design.md) · [운영](operations.md)

## 설정 모델

config-server의 FARM AD 연계 설정은 Helm values, CI secret, Kubernetes Secret과
노드의 root 전용 파일로 나뉜다. 실제 비밀 값과 변경 이력은 관리자 전용
시크릿·배포 설정 문서에서 별도로 관리하며, 이 문서에는 값·개인키·keytab을
적지 않는다.

```text
CI Secret / 관리자 전용 시크릿 문서
  -> Helm values 주입
  -> config-server Deployment 환경 변수·Secret mount
  -> 제한된 AD/노드 관리 채널
  -> 노드 root-only keytab과 사용자 ccache
```

## 설정 그룹

| 그룹 | 대표 항목 | 소비자 | 관리 기준 |
| --- | --- | --- | --- |
| Realm | `KRB5_REALM` | config-server, 사용자 Pod | 신규 경로는 FARM AD Realm으로 통일 |
| 노드 관리 | `FARM_SSH_*`, 노드 목록 | config-server | key와 계정은 AD 관리 채널과 분리 |
| AD 관리 | `FARM_AD_SSH_*`, DC 목록 | config-server | AD DC에만 제한된 명령을 허용 |
| 홈 경로 | `FARM_HOME_MOUNT_ROOT` | 사용자 Pod | FARM 노드의 기존 NFS mount를 가리킴 |
| NAS 홈 관리 | NAS SSH 설정 | config-server | 홈 생성·삭제만 담당, AD/keytab과 분리 |
| 사용자 keytab | `krb5-keytab-<user>` Secret | config-server | 값은 Pod에 mount하지 않음 |

## Kubernetes 배포 확인

값을 출력하지 않고 Deployment가 필요한 환경 변수와 Secret mount를 참조하는지
확인한다.

```bash
kubectl -n ailab-infra get deploy containerssh-config-server \
  -o custom-columns=IMAGE:.spec.template.spec.containers[0].image,SA:.spec.template.spec.serviceAccountName
kubectl -n ailab-infra describe deploy containerssh-config-server
kubectl -n ailab-infra get secret farm-ssh-key farm-ad-ssh-key
```

사용자 keytab Secret은 이름·생성 시각만 확인한다. `kubectl get secret -o yaml`,
`jsonpath`로 `data`를 출력하거나 terminal history에 남기는 명령은 사용하지 않는다.

## 노드 설정 기준

노드는 사용자별 keytab을 `/etc/decs-krb/keytabs/` 아래 root 전용으로 보관하고,
`decs-krb-refresh@<user>.timer`가 사용자 ccache를 갱신하도록 준비한다. 노드
머신 ccache와 사용자 ccache는 서로 다른 파일·principal로 분리한다.

| 대상 | 설정 기준 |
| --- | --- |
| 사용자 keytab·환경 파일 | root 소유, `0400` |
| 사용자 ccache | 대상 UID/GID 소유, `0600` |
| 머신 ccache | 현재 노드 머신 principal만 사용 |
| rpc.gssd | 노드 Kerberos NFS 경로와 함께 점검 |
| forced-command 계정 | 일반 셸·포괄적인 sudo 없이 허용 동작만 실행 |

## 현재 보류된 ConfigMap

config-server에 mount되는 `krb5-conf` ConfigMap은 현재 계정·Pod 생성의 직접적인
Kerberos client 설정 원본이 아니다. config-server가 KDC 기반 명령을 직접 쓰게
되기 전에는 KDC·admin server 주소의 소유자와 주입 경로를 먼저 확정한다. 그 전에는
빈 endpoint를 정상 Kerberos 구성으로 해석하거나 이를 장애 복구에 사용하지 않는다.

## 변경 전 확인표

1. 변경 대상이 AD 관리·노드 관리·NAS 홈 관리 중 어느 경계인지 구분한다.
2. 실제 비밀 값은 관리자 전용 시크릿 문서에서만 확인하고 일반 문서에 복사하지 않는다.
3. 한 대의 canary 노드와 시험 사용자로 ccache·NFS 접근을 검증한다.
4. 기존 Pod가 이전 Realm·홈 경로를 쓰는지 확인하고, 설정값을 덮어쓰지 않는다.
5. 검증 뒤에만 CI/Helm 설정을 확대 적용한다.
