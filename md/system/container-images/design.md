# container-images 설계

> [개요](index.md) · [운영](operations.md)

> **GitHub 코드 링크:** `admin_infra_server`는 비공개 저장소다. 코드 링크를
> 누르면 GitHub 로그인 화면을 거쳐 원래 파일과 line으로 이동한다. 조직 저장소에
> 접근 권한이 있는 계정으로 로그인해야 한다.

## 1. 개요

`container-images`의 목표는 GPU container가 시작된 직후 사용자가 자신의
계정과 공유 홈으로 접속하고, 선택한 GPU software 환경에서 바로 작업을 시작할
수 있게 하는 것이다.

모든 container는 전달받은 UID/GID로 계정과 그룹을 구성하고, 공유 홈의 사용자
설정과 password 파일을 이어서 사용한다. SSH와 Jupyter를 기본으로 제공하고,
필요한 경우 VNC와 Kerberos ccache 환경도 함께 구성한다. 이를 통해 container를
재시작하거나 다른 이미지 버전을 선택해도 같은 사용자 identity와 작업 환경을
유지한다.

계정, supplemental group, 홈 디렉터리와 Kerberos 정보처럼 사용자와 host마다
달라지는 값은 공통 `entrypoint.sh`가 시작 시 반영한다. CUDA, TensorFlow,
Python과 Ubuntu 조합은 각각의 이미지 버전으로 제공한다. 따라서 사용자는 필요한
GPU software 조합을 선택하면서도 모든 이미지 버전에서 동일한 방식으로 SSH, Jupyter,
VNC와 공유 홈을 사용할 수 있다.

## 2. 사용자 실행 환경

`Dockerfile`은 모든 이미지 버전에 필요한 프로그램과 `entrypoint.sh`를 image에
포함한다. 실제 사용자 정보와 실행 옵션은 container를 시작할 때 전달되며,
entrypoint가 이를 검증하고 런타임 환경을 구성한다.

사용자 실행 환경은 container 밖과 안에서 다음과 같이 나누어 준비한다.

| 구분 | 담당하는 작업 |
| --- | --- |
| `infra` | 사용자 UID/GID와 그룹 목록을 결정하고, host의 공유 스토리지와 Kerberos credential을 준비한 뒤 Docker mount와 환경 변수를 구성한다. |
| `entrypoint.sh` | 전달받은 identity를 container 계정과 그룹에 반영하고, mount된 홈과 credential을 사용자 권한으로 검증한 뒤 SSH·Jupyter·VNC를 시작한다. |

따라서 image에는 특정 사용자의 계정이나 홈을 미리 넣지 않는다. 같은 image를
사용하더라도 container를 생성할 때 전달된 identity, mount와 실행 옵션에 따라
각 사용자의 환경이 구성된다.

### 2.1 컨테이너 시작 흐름

entrypoint의 전체 시작 순서는 다음과 같다.

1. 선택한 이미지 버전, CUDA/TensorFlow version과 host NVIDIA driver를 확인한다.
2. 전달받은 UID/GID로 사용자, primary group과 supplemental group을 구성한다.
3. Kerberos ccache를 사용할 수 있도록 사용자 환경을 준비한다.
4. 홈 디렉터리의 소유권과 쓰기 가능 여부를 확인하고 초기 설정을 보완한다.
5. SSH 로그인, audit와 login message를 구성하고 SSH service를 시작한다.
6. 홈을 사용할 수 있으면 Jupyter와 선택적인 VNC/noVNC를 시작한다.
7. Kerberos ticket이 없어 홈을 쓸 수 없다면 SSH만 먼저 제공하고, 홈이 준비된
   뒤 사용자 서비스를 시작한다.

이 순서를 하나의 entrypoint에서 관리하므로 이미지 버전마다 사용자 환경을
별도로 구현하지 않는다.

**관련 코드**

- [entrypoint의 전체 실행 순서](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/container-images/entrypoint.sh%23L636-L648):
  계정, Kerberos, 홈, SSH와 사용자 service를 순서대로 호출한다.
- [`start_user_apps`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/container-images/entrypoint.sh%23L604-L609):
  사용자 shell 환경을 보완한 뒤 Jupyter와 VNC/noVNC를 시작한다.

### 2.2 계정, 그룹과 권한

container 내부 사용자 이름과 UID/GID는 image가 결정하지 않는다. `infra`가
DB·AD·NFS와 일치하는 값을 전달하면 entrypoint가 같은 값으로
사용자와 primary group을 생성하거나 기존 계정을 검증한다. 같은 이름의 사용자나
그룹이 이미 있는데 UID/GID가 다르면 조용히 덮어쓰지 않고 시작을 중단한다.

그룹은 primary group과 supplemental group으로 나뉜다. primary group은 사용자의
기본 GID이며 새 파일의 기본 group owner로 사용한다. supplemental group은 연구실이나
프로젝트 단위로 공유하는 디렉터리에 접근하기 위한 추가 membership이다. `infra`가
DB에서 membership을 조회해 `group:GID` 목록으로 전달하면 entrypoint는 각 그룹을
container 안에 같은 GID로 만들고 사용자를 추가한다. 이미 같은 이름의 그룹이 다른
GID를 사용하고 있으면 NFS 권한을 잘못 해석할 수 있으므로 container 시작을 중단한다.

예를 들어 사용자의 primary group이 `alice:12001`이고
`DECS_SUPPLEMENTAL_GROUPS=vision:13001,nlp:13002`가 전달되면, container의
사용자 프로세스는 GID `12001`을 기본 그룹으로 사용하면서 GID `13001`과 `13002`가
소유한 공유 파일에도 접근할 수 있다. NFS는 숫자 UID/GID를 기준으로 POSIX 권한을
판단하므로 host, container와 스토리지에서 이 숫자가 일치해야 한다.

Kerberos 공유 스토리지를 사용하는 container에서 사용자가 자신의 홈 아래에 그룹
공유 공간을 만들 때는 다음과 같이 `group-dir-share`를 사용한다.

```bash
group-dir-share ~/project vision
```

helper는 요청한 경로가 사용자 홈 안에 있고 사용자가 해당 그룹의 구성원인지 확인한
뒤, directory의 group owner를 바꾸고 `2770` 권한을 적용한다. setgid bit 때문에
그 안에서 새로 만든 파일과 directory는 `vision` group을 이어받는다. ACL을 사용할
수 있으면 상위 directory에는 접근에 필요한 traverse 권한을, 공유 directory에는
현재 파일과 새 파일에 적용할 group ACL을 함께 설정한다. 사용자는 자신에게 배정되지
않은 그룹이나 홈 바깥의 경로를 이 helper로 공유할 수 없다.

기본 sudo mode인 `restricted`는 package 설치에 필요한 명령은 허용하지만 사용자
전환, mount, 권한 변경, root shell과 우회 가능한 interpreter 실행은 막는다. 기존
사용자의 password는 재시작할 때 변경하지 않으며, `USER_PW`는 사용자를 처음 생성할
때만 적용한다.

`infra`가 전달하는 주요 값은 다음과 같다.

| 값 | 의미 |
| --- | --- |
| `USER_ID` | container에 생성하거나 확인할 사용자 이름 |
| `UID`, `GID` | DB·AD·NFS와 일치하는 숫자 identity |
| `USER_GROUP` | primary group 이름 |
| `DECS_SUPPLEMENTAL_GROUPS` | 추가할 `group:GID` 목록 |
| `DECS_USER_SUDO_MODE` | `disabled`, `restricted`, `allowed` 중 하나 |

`TARGET_UID`나 `TARGET_GID` 같은 두 번째 identity 체계를 만들지 않는다. 하나의
`UID`/`GID`만 사용해야 container, 공유 홈과 DB의 소유권이 서로 달라지는 오류를
시작 단계에서 찾을 수 있다.

supplemental group 구성은 전달된 그룹을 추가하는 방식이다. 기존 container에서
membership을 제거하거나 GID를 바꿔야 할 때는 남아 있는 group 정보를 재사용하지
않도록 새 입력값으로 container를 다시 생성한다.

**관련 코드**

- [`infra`의 그룹 membership 조회](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/user-lifecycle/script/uid_manager/services/create_container.py%23L207-L208):
  DB에서 사용자의 supplemental group을 가져온다.
- [`infra`의 그룹 환경 변수 구성](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/user-lifecycle/script/uid_manager/services/create_container.py%23L723-L726):
  조회한 그룹을 `group:GID` 목록으로 만들어 container에 전달한다.
- [`ensure_group_and_user`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/container-images/entrypoint.sh%23L234-L282):
  primary group과 사용자를 생성·검증하고 sudo mode를 적용한다.
- [`ensure_supplemental_groups`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/container-images/entrypoint.sh%23L154-L185):
  추가 그룹의 이름과 GID가 전달값과 일치하는지 확인한다.
- [`install_kerberos_share_helper`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/container-images/entrypoint.sh%23L91-L152):
  Kerberos 환경에서 사용자가 자신의 홈 안에 그룹 공유 디렉터리를 만들 수 있는
  helper를 설치한다.
- [`write_restricted_sudoers`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/container-images/entrypoint.sh%23L44-L69):
  제한적 sudo에서 허용하지 않을 권한 상승 경로를 정의한다.

### 2.3 홈 디렉터리와 공유 스토리지

사용자의 작업 파일과 shell 설정은 image layer가 아니라 host에 mount된 공유
스토리지에 저장한다. container를 새 image로 다시 만들더라도 같은 공유 홈을
mount하면 기존 작업 파일과 사용자 설정을 이어서 사용할 수 있다.

현재 mount 구성은 다음과 같다.

| host에서 준비하는 항목 | container 위치 | 목적 |
| --- | --- | --- |
| 사용자 홈의 상위 공유 경로 | `/home` | `/home/<USER_ID>`를 비롯한 NFS 홈을 container에 제공한다. |
| 사용자 Kerberos ccache directory | host와 같은 경로 | NFS 요청에 사용할 사용자 ticket을 shell·Jupyter·VNC에 전달한다. |
| host의 `krb5.conf` | `/etc/krb5.conf` (read-only) | container와 host가 같은 realm과 KDC 설정을 사용하게 한다. |

`infra`는 domain과 Kerberos 사용 여부에 맞는 host의 공유 경로를 선택하고, 그
상위 경로를 container의 `/home`에 bind mount한다. 따라서 container 안의 사용자
홈은 항상 `/home/<USER_ID>`가 된다. 다른 사용자 홈도 같은 mount namespace에
경로로는 나타날 수 있지만 실제 접근은 NFS 인증, 숫자 UID/GID, directory mode와
ACL에 의해 제한된다.

Kerberos를 사용하는 경우에는 ccache directory를 별도로 bind mount하고
`KRB5CCNAME`으로 정확한 ticket 파일을 지정한다. host의 root 전용 keytab은
container에 mount하지 않는다. host가 keytab으로 ticket을 갱신하고 container는
사용자 ccache만 사용하므로 장기 credential과 사용자 runtime credential의 경계를
유지할 수 있다.

entrypoint는 NFS를 직접 mount하거나 공유 홈 전체의 소유권을 변경하지 않는다.
`/home/<USER_ID>`가 없으면 생성을 시도하고, 전달받은 UID/GID의 사용자로 파일을
직접 써 보아 실제 사용 가능 여부를 확인한다. `.profile`, `.bashrc`,
`.bash_logout`은 없는 경우에만 추가하며 기존 사용자 파일을 덮어쓰지 않는다.

NFS가 `root_squash`를 사용하면 container root도 홈의 owner를 임의로 바꿀 수
없다. 따라서 홈은 NAS에서 올바른 UID/GID로 준비되어 있어야 한다. Kerberos
ccache가 설정된 상태에서 아직 홈을 쓸 수 없다면 container 전체를 종료하지 않고
SSH를 먼저 제공한다. 이후 ticket이 준비되어 홈에 쓸 수 있게 되면 홈 설정을
마치고 Jupyter와 VNC를 시작한다.

**관련 코드**

- [`infra`의 mount 경로 선택](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/user-lifecycle/script/uid_manager/services/create_container.py%23L188-L216):
  domain과 Kerberos 사용 여부에 따라 host의 공유 홈 root를 결정한다.
- [`infra`의 Docker mount 구성](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/user-lifecycle/script/uid_manager/services/create_container.py%23L705-L754):
  공유 홈을 `/home`에 연결하고 ccache directory와 `krb5.conf`를 별도로 mount한다.
- [`ensure_user_home`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/container-images/entrypoint.sh%23L284-L330):
  홈 생성, 쓰기 권한, 기본 shell 파일과 history 저장 설정을 처리한다.
- [`start_kerberos_home_watcher`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/container-images/entrypoint.sh%23L611-L634):
  Kerberos ticket을 기다리면서 홈이 쓰기 가능해지는 시점을 확인한다.

### 2.4 SSH, Jupyter와 VNC

SSH는 container가 시작될 때 사용자와 관리 계정만 로그인할 수 있도록
`AllowUsers`를 구성하고 PAM, command audit와 login message를 적용한 뒤 service를
재시작한다. 홈이 아직 Kerberos 인증을 기다리는 상태여도 SSH는 먼저 사용할 수
있으므로 사용자가 로그인하여 ticket 상태를 확인할 수 있다.

Jupyter 설정은 사용자 홈의 `.jupyter`에 둔다. 관리하는 network·notebook 경로
항목만 갱신하고 나머지 사용자 설정은 유지한다. 시작할 때 임의 token을 만들고
권한이 `0600`인 `jupyter_token.txt`에 저장한 뒤 사용자 권한으로 JupyterLab을
실행한다.

VNC/noVNC는 `ENABLE_VNC=true`일 때만 시작한다. TigerVNC는 container 내부의
localhost에 bind하고, noVNC가 지정된 web port를 통해 연결한다. 기존 홈에
`vnc_password.txt`가 있으면 재사용하므로 container 재시작만으로 password가
바뀌지 않는다.

**관련 코드**

- [`configure_system_login`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/container-images/entrypoint.sh%23L404-L445):
  SSH 접근 사용자, PAM, audit와 login message를 구성한다.
- [`ensure_jupyter_config`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/container-images/entrypoint.sh%23L447-L478):
  사용자 설정을 보존하면서 Jupyter의 공통 항목을 갱신한다.
- [`start_jupyter`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/container-images/entrypoint.sh%23L489-L509):
  접근 token을 저장하고 사용자 권한으로 JupyterLab을 시작한다.
- [`start_novnc`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/container-images/entrypoint.sh%23L511-L602):
  VNC password를 준비하고 TigerVNC와 noVNC proxy를 시작한다.

### 2.5 Kerberos 사용자 환경

container에는 Kerberos client가 포함되지만 host의 machine keytab은 전달하지
않는다. `infra`가 준비한 ccache 경로를 `KRB5CCNAME`으로 받으면
entrypoint가 사용자만 접근할 수 있는 ccache 디렉터리와 shell 환경 변수를
구성한다. 사용자는 `decs-kerberos-status`로 현재 ticket을 확인할 수 있다.

Kerberos keytab과 ccache를 분리하는 이유와 credential 경계는
[Kerberos/NFS의 keytab과 ccache 모델](../kerberos-nfs/design.md#6-keytab-ccache)을 따른다.

**관련 코드**

- [`ensure_kerberos_runtime`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/container-images/entrypoint.sh%23L332-L366):
  ccache 경로의 권한과 Kerberos 환경 변수, ticket 확인 helper를 구성한다.

## 3. 이미지 구성

사용자 실행 환경은 모든 image에서 같지만 GPU software stack은 workload에 따라
달라진다. `container-images`는 공통 image 구성과 CUDA/TensorFlow 조합만 분리해
관리한다.

### 3.1 모든 이미지 버전의 공통 build 구성

모든 이미지 버전은 하나의 `Dockerfile`을 사용하고 다음 프로그램을 공통으로
포함한다.

| 영역 | 공통 구성 |
| --- | --- |
| 기본 도구 | ACL, audit, network, certificate와 package repository 도구 |
| 원격 접근 | OpenSSH server와 Kerberos client |
| 개발 환경 | Miniforge, conda, pip, JupyterLab과 Notebook |
| GUI | Chrome, Xfce, TigerVNC, noVNC와 websockify |
| 사용자 환경 | 한국어 글꼴과 입력기, 공통 entrypoint와 Jupyter config 위치 |

이미지 버전별 Dockerfile을 복제하지 않는 이유는 보안 patch와 공통 package 변경을
한 번만 적용하기 위해서다. 실제 차이는 build argument로 전달하며 공통 설치와
시작 흐름은 모든 이미지 버전에서 동일하게 유지한다.

### 3.2 CUDA/TensorFlow 조합별 이미지

이미지 버전 간 차이는 `image-variants.json`에 정의한다.

| manifest 값 | 이미지 버전마다 달라지는 내용 |
| --- | --- |
| `base_image` | CUDA, cuDNN과 Ubuntu가 포함된 NVIDIA base image |
| `cuda_version` | image가 제공하는 CUDA major/minor version |
| `tensorflow_version`, `tensorflow_package` | CUDA 조합에 맞춰 설치할 TensorFlow version과 package 형태 |
| `python_version`, `conda_packages` | Python version과 TensorFlow/Jupyter 호환을 위한 package 제약 |
| `min_nvidia_driver` | 해당 CUDA image를 실행할 host의 최소 NVIDIA driver |
| `support` | 실장비 검증을 마친 `stable` 또는 검증 중인 `experimental` 상태 |
| `aliases` | version alias와 `stable`, `latest` 같은 권장 tag |

현재 Python은 모두 3.10, Ubuntu는 모두 22.04를 사용한다. CUDA 조합에 따라
TensorFlow package, conda 제약과 최소 host driver가 달라진다.

| CUDA | TensorFlow | 주요 package 차이 | 최소 NVIDIA driver | 지원 상태와 alias |
| --- | --- | --- | --- | --- |
| 11.8 | 2.13.0 | 구버전 Jupyter·IPython과 `typing_extensions=4.5` 제약 | 520.61.05 | `stable`, `legacy` |
| 12.2 | 2.15.0 | 기본 TensorFlow package와 공통 Jupyter package | 535.104.05 | `stable` |
| 12.3 | 2.16.1 | `tensorflow[and-cuda]` package 사용 | 545.23.08 | `stable` |
| 12.5 | 2.20.0 | TensorFlow 2.20 기준 이미지 | 555.42.06 | `stable`, `latest` |
| 12.8 | 2.20.0 | H200 대상 실험 이미지 | 570.124.06 | `experimental`, `h200-experimental` |

로컬 빌드 도구와 GitHub Actions는 같은 manifest를 읽어 build argument와 tag를
만든다. 따라서 지원 조합을 한곳에서 검토하고 로컬과 CI가 서로 다른 image를
생성하는 것을 막는다.

### 3.3 GPU 호환성 처리

image는 시작할 때 build에 기록된 최소 NVIDIA driver와 `nvidia-smi` 결과를
출력한다. 기본값은 경고 중심이며 `STRICT_CUDA_COMPAT=true`일 때만 최소
driver보다 낮은 host에서 시작을 실패시킨다.

기본을 강제 실패로 두지 않은 이유는 GPU가 없는 검증 환경이나 긴급 진단
container까지 막지 않기 위해서다. 운영 배포에서 호환성을 반드시 보장해야
하면 strict mode를 명시한다.

**관련 코드**

- [`Dockerfile`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/container-images/Dockerfile):
  공통 package를 설치하고 manifest 값을 build argument로 받는다.
- [`image-variants.json`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/container-images/image-variants.json):
  지원하는 이미지 버전별 CUDA/TensorFlow 조합, 최소 driver와 tag를 정의한다.
- [`print_image_runtime_info`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/container-images/entrypoint.sh%23L196-L232):
  image의 요구 driver와 실제 host driver를 비교한다.

## 4. 디렉터리 지도

| 경로 | 핵심 기능 |
| --- | --- |
| [`Dockerfile`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/container-images/Dockerfile) | 모든 이미지 버전이 공유하는 단일 image 정의 |
| [`image-variants.json`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/container-images/image-variants.json) | base image, CUDA/TensorFlow, 최소 driver와 alias 목록 |
| [`entrypoint.sh`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/container-images/entrypoint.sh) | 시작 시 계정·그룹·홈·SSH·Jupyter·VNC·Kerberos 환경 구성 |
| `scripts/variant_matrix.py` | manifest를 Docker/GitHub Actions build matrix로 변환 |
| `scripts/build_variants.py` | 로컬 build/push 명령 생성과 실행 |
| `scripts/test_image_variants.py` | image metadata, TensorFlow와 선택적 GPU smoke test |
| `scripts/test_uid_create_container.py` | `infra`가 전달하는 container 생성 입력값의 dry-run 계약 검증 |
| `tests/` | `root_squash`, Kerberos, sudo와 build 설정 회귀 test |
| `.github/workflows/docker-publish.yml` | PR merge 또는 수동 실행 시 matrix build/push |
