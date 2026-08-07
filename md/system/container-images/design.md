# container-images 설계

> [개요](index.md) · [운영](operations.md)

## 1. 개요

GPU workload마다 필요한 CUDA, TensorFlow, Python과 Ubuntu 조합이 다르다. 조합별
이미지를 서로 다른 Dockerfile과 빌드 절차로 관리하면 공통 package나 보안 설정의
반영 시점이 달라지고, 같은 이름의 이미지를 로컬과 CI에서 다르게 만들 수 있다.
variant가 늘어날수록 어떤 조합을 지원하는지와 host NVIDIA driver가 호환되는지도
일관되게 확인하기 어려워진다.

컨테이너가 시작된 뒤 필요한 환경도 이미지마다 같아야 한다. SSH, Jupyter와
선택적인 VNC 구성이 동일하게 동작하면서도, UID/GID, 홈 디렉터리, Kerberos
ccache처럼 사용자와 실행 host에 따라 달라지는 값은 시작 시점에 반영되어야 한다.
이 값을 image layer에 고정하면 사용자나 특정 서버마다 이미지를 다시 만들어야
하고, 공유 스토리지의 identity와 컨테이너 계정이 어긋날 수 있다.

`container-images`는 이 문제를 다음 방식으로 해결한다.

1. 지원하는 CUDA/TensorFlow 조합과 image tag를 하나의 variant manifest에서
   관리한다.
2. 모든 variant가 단일 Dockerfile을 사용하여 공통 package와 보안 설정을 같은
   방식으로 포함한다.
3. 사용자와 host별 값은 공통 entrypoint가 컨테이너 시작 시 반영한다.
4. 로컬 빌드와 CI가 같은 manifest를 사용하고, 정적 검사와 smoke test로 image와
   런타임 구성을 검증한다.

따라서 새로운 GPU software 조합을 추가하더라도 빌드 정의를 복제하지 않고,
모든 variant에서 동일한 런타임 동작과 검증 기준을 유지할 수 있다.

## 2. 이미지 구성

### 2.1 모든 variant의 공통 구성

모든 variant는 같은 `Dockerfile`과 `entrypoint.sh`를 사용한다. CUDA와
TensorFlow 버전이 달라도 사용자가 접하는 개발 환경, 시작 절차와 권한 정책은
동일하게 유지한다.

| 구성 시점 | 모든 variant에 공통으로 적용하는 내용 |
| --- | --- |
| image build | SSH server, Kerberos client, ACL·audit·network 도구, 한국어 글꼴과 입력기, Chrome 설치 |
| 개발 환경 | Miniforge 기반 Python 환경, conda, pip, JupyterLab과 Notebook 구성 |
| 원격 GUI | Xfce, TigerVNC, noVNC와 websockify 설치. 실행 여부는 시작 시 선택 |
| 사용자 환경 | 전달받은 UID/GID로 사용자·그룹 구성, supplemental group과 홈 디렉터리 확인 |
| 접근과 권한 | SSH·Jupyter 설정, sudo mode 적용, 그룹 디렉터리 공유 helper 제공 |
| Kerberos | 전달받은 ccache 경로와 realm 정보를 사용자 환경에 연결 |
| 시작과 검증 | image variant와 host driver 표시, Jupyter 시작, 요청된 경우 VNC/noVNC 시작 |

공통 package와 파일은 image build 시 넣고, 사용자 identity나 mount처럼
컨테이너마다 달라지는 값은 시작 시 `entrypoint.sh`가 적용한다. 이 구분을 통해
사용자마다 이미지를 다시 만들지 않고 같은 image를 서로 다른 UID/GID와 실행
환경에서 사용할 수 있다.

entrypoint는 다음 순서로 공통 런타임을 구성한다.

1. image variant와 실제 host driver 정보를 출력한다.
2. `USER_ID`, `UID`, `GID`, `USER_GROUP`을 검증하고 사용자와 그룹을 구성한다.
3. supplemental group, sudo 정책과 홈 디렉터리 접근을 확인한다.
4. SSH, Jupyter와 Kerberos ccache 환경을 구성한다.
5. Jupyter를 시작하고 요청된 경우에만 VNC/noVNC를 시작한다.

호스트 mount가 `root_squash`인 환경에서는 root가 사용자 홈을 임의로 `chown`
할 수 없다. 따라서 이미 결정된 UID/GID로 사용자를 실행하고 홈에서 root 권한이
필요한 작업을 최소화한다. 사용자 홈의 기존 비밀번호와 VNC password 파일도
재시작할 때 덮어쓰지 않는다.

기본 `DECS_USER_SUDO_MODE=restricted`는 package 설치에 필요한 제한된 sudo를
허용하지만 UID 전환, mount, 권한 변경, root shell과 우회 가능한 interpreter
실행을 막는다. 사용자 그룹 공유는 관리자 sudo 대신 `group-dir-share` helper로
제공하며, 사용자 권한으로 디렉터리에 `2770`과 default ACL을 설정한다.

Kerberos keytab과 ccache를 분리한 이유와 container credential 경계는
[Kerberos/NFS의 keytab과 ccache 모델](../kerberos-nfs/design.md#6-keytab-ccache)을 따른다.

### 2.2 variant마다 달라지는 구성

variant 간의 차이는 `image-variants.json`에만 정의하고, 각 값을 단일
`Dockerfile`의 build argument로 전달한다.

| manifest 값 | variant마다 달라지는 내용 |
| --- | --- |
| `base_image` | CUDA, cuDNN과 Ubuntu가 포함된 NVIDIA base image |
| `cuda_version` | image가 제공하는 CUDA major/minor version |
| `tensorflow_version`, `tensorflow_package` | CUDA 조합에 맞춰 설치할 TensorFlow version과 package 형태 |
| `python_version`, `conda_packages` | Python version과 TensorFlow/Jupyter 호환을 위한 package 제약 |
| `min_nvidia_driver` | 해당 CUDA image를 실행할 host의 최소 NVIDIA driver |
| `support` | 실장비 검증을 마친 `stable` 또는 검증 중인 `experimental` 상태 |
| `aliases` | 사용자가 선택하는 version alias와 `stable`, `latest` 같은 권장 tag |

현재 variant별 차이는 다음과 같다. Python은 모두 3.10, Ubuntu는 모두 22.04를
사용하지만 이후 변경을 독립적으로 표현할 수 있도록 manifest에 명시한다.

| CUDA | TensorFlow | 주요 package 차이 | 최소 NVIDIA driver | 지원 상태와 alias |
| --- | --- | --- | --- | --- |
| 11.8 | 2.13.0 | 구버전 Jupyter·IPython과 `typing_extensions=4.5` 제약 | 520.61.05 | `stable`, `legacy` |
| 12.2 | 2.15.0 | 기본 TensorFlow package와 공통 Jupyter package | 535.104.05 | `stable` |
| 12.3 | 2.16.1 | `tensorflow[and-cuda]` package 사용 | 545.23.08 | `stable` |
| 12.5 | 2.20.0 | TensorFlow 2.20 기준 variant | 555.42.06 | `stable`, `latest` |
| 12.8 | 2.20.0 | H200 대상 experimental variant | 570.124.06 | `experimental`, `h200-experimental` |

variant별 Dockerfile을 복제하지 않는 이유는 보안 patch와 공통 package 변경을
한 번만 적용하고, 버전 차이는 manifest의 데이터로 비교하기 위해서다. 로컬 빌드
도구와 GitHub Actions도 같은 manifest를 읽으므로 서로 다른 조합이나 tag를
생성하지 않는다.

### 2.3 GPU 호환성 처리

이미지는 시작할 때 build에 기록된 최소 NVIDIA driver와 `nvidia-smi` 결과를
출력한다. 기본값은 경고 중심이며 `STRICT_CUDA_COMPAT=true`일 때만 최소
driver보다 낮은 host에서 시작을 실패시킨다.

기본을 강제 실패로 두지 않은 이유는 GPU가 없는 검증 환경이나 긴급 진단
container까지 막지 않기 위해서다. 운영 배포에서 호환성을 반드시 보장해야
하면 strict mode를 명시한다.

## 3. 사용자 생명주기와의 계약

`uidctl create-container`는 image 이름과 version tag, 최종 UID/GID, 포트와
home mount를 Docker 환경변수/옵션으로 전달한다. 이미지가 기대하는 주요 값은
다음과 같다.

| 값 | 의미 |
| --- | --- |
| `USER_ID` | 컨테이너 사용자 이름 |
| `UID`, `GID` | DB·AD·NFS와 이미 일치가 검증된 숫자 identity |
| `USER_GROUP` | primary group 이름 |
| `ENABLE_VNC` | VNC/noVNC opt-in |
| `KRB5CCNAME` | 컨테이너에 보이는 ccache 경로 |
| `DECS_KERBEROS_HOST_KEYTAB` | 호스트 관리 ticket을 기다리는 모드 |
| `DECS_USER_SUDO_MODE` | `disabled`, `restricted`, `allowed` 중 하나 |

`TARGET_UID`나 `TARGET_GID` 같은 두 번째 identity 체계를 만들지 않는다. 하나의
`UID`/`GID`만 사용해야 container, NFS와 DB가 어긋나는 오류를 조기에 발견할
수 있다.

## 4. 디렉터리 지도

| 경로 | 핵심 기능 |
| --- | --- |
| `Dockerfile` | 모든 variant가 공유하는 단일 이미지 정의 |
| `image-variants.json` | base image, CUDA/TensorFlow, 최소 driver, alias의 권위 있는 목록 |
| `entrypoint.sh` | 실행 시 사용자·그룹·SSH·Jupyter·VNC·Kerberos 환경 구성 |
| `scripts/variant_matrix.py` | manifest를 Docker/GitHub Actions build matrix로 변환 |
| `scripts/build_variants.py` | 로컬 build/push 명령 생성과 실행 |
| `scripts/test_image_variants.py` | 이미지 메타데이터, TensorFlow와 선택적 GPU smoke test |
| `scripts/test_uid_create_container.py` | `user-lifecycle` CLI와의 dry-run 계약 검증 |
| `tests/` | root_squash, Kerberos, sudo와 build 설정 회귀 테스트 |
| `.github/workflows/docker-publish.yml` | PR merge 또는 수동 실행 시 matrix build/push |
