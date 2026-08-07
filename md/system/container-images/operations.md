# container-images 운영

> [개요](index.md) · [설계](design.md)

> **GitHub 코드 링크:** `admin_infra_server`는 비공개 저장소다. 코드 링크를
> 누르면 GitHub 로그인 화면을 거쳐 원래 파일과 line으로 이동한다. 조직 저장소에
> 접근 권한이 있는 계정으로 로그인해야 한다.

## 1. 개요

이 문서의 목표는 `container-images`를 변경하고 검증하여 Docker registry에
배포한 뒤, 운영 container에서 사용할 수 있게 만드는 전체 절차를 제공하는 것이다.
새 CUDA/TensorFlow 조합을 추가하는 경우뿐 아니라 공통 package, 사용자 실행 환경,
tag 정책이나 build 도구를 변경할 때 확인해야 할 범위도 함께 다룬다.

하나의 변경은 다음 순서로 운영한다.

1. 변경 목적에 맞는 파일을 선택한다.
2. manifest와 shell 회귀 test로 build 입력과 runtime 계약을 확인한다.
3. 새로운 날짜 tag로 image를 build한다.
4. CPU smoke test와 대상 GPU host test를 수행한다.
5. 검증한 image를 registry에 push한다.
6. 날짜 tag를 지정하여 신규 container를 생성하거나 기존 container를 교체한다.

`stable`과 `latest`는 고정된 release가 아니라 다른 image를 가리킬 수 있는 alias다.
build, 배포, 장애 분석 기록에는 `cuda12.5-tf2.20-ubuntu22.04-260706`처럼 날짜가
포함된 전체 tag를 사용한다.

## 2. 목적별 수정 위치

변경하려는 목적을 먼저 정한 뒤 그 목적을 소유하는 파일을 수정한다. 하나의 변경이
image 구성, 시작 동작과 검증에 함께 영향을 주면 표의 관련 파일도 같이 변경한다.

| 변경 목적 | 주로 수정할 위치 | 함께 확인하거나 수정할 위치 |
| --- | --- | --- |
| 새로운 CUDA·TensorFlow·Python·Ubuntu 조합을 제공한다. | [`image-variants.json`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/container-images/image-variants.json) | [`README.md`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/container-images/README.md)의 image·alias 목록, matrix 출력과 GPU smoke test |
| 모든 이미지 버전에 package나 공통 파일을 추가·갱신한다. | [`Dockerfile`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/container-images/Dockerfile) | [`test_image_build_config.sh`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/container-images/tests/test_image_build_config.sh), 전체 이미지 버전 build |
| container 시작 시 계정·그룹·홈·Kerberos·SSH·Jupyter·VNC를 구성하는 동작을 바꾼다. | [`entrypoint.sh`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/container-images/entrypoint.sh) | [`test_entrypoint_root_squash.sh`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/container-images/tests/test_entrypoint_root_squash.sh), 기존 홈과 재시작 동작 |
| image repository, 날짜 tag, alias 또는 지원 상태를 바꾼다. | [`image-variants.json`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/container-images/image-variants.json), [`variant_matrix.py`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/container-images/scripts/variant_matrix.py) | [`build_variants.py`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/container-images/scripts/build_variants.py)의 dry-run tag |
| 로컬 build 명령이나 build argument 전달 방식을 바꾼다. | [`build_variants.py`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/container-images/scripts/build_variants.py) | `variant_matrix.py`, `Dockerfile`의 `ARG`, 배포 workflow의 build argument |
| image에서 확인할 package·TensorFlow·GPU 항목을 추가한다. | [`test_image_variants.py`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/container-images/scripts/test_image_variants.py) | CPU test와 대상 GPU host test 결과 |
| Docker Hub build/push를 자동화하거나 trigger를 변경한다. | [`docker-publish.yml`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/container-images/.github/workflows/docker-publish.yml) | workflow 위치, build context, Docker Hub secret과 release tag |

특정 사용자의 UID/GID, group membership, 홈 mount나 port를 변경하는 것은
`container-images` 변경 목적이 아니다. 외부에서 전달된 값을 container 내부에서
처리하는 방식 자체를 바꿀 때만 `entrypoint.sh`를 수정한다.

## 3. 새 이미지 버전 추가

### 3.1 조합 결정

새 이미지 버전은 CUDA 숫자만 추가하는 작업이 아니다. 다음 항목을 하나의 호환
조합으로 결정해야 한다.

- NVIDIA base image의 CUDA, cuDNN과 Ubuntu version
- TensorFlow version과 설치 package 표현
- Python version과 conda package 제약
- 해당 CUDA를 실행할 host의 최소 NVIDIA driver
- 실장비 검증 여부를 나타내는 `support`
- 날짜 tag 외에 제공할 alias

검증을 시작하는 단계에서는 `support`를 `experimental`로 두고 `stable`이나
`latest` alias를 부여하지 않는다. CPU와 대상 GPU test를 통과한 뒤에 지원 상태와
권장 alias를 변경한다.

### 3.2 manifest 항목 추가

[`image-variants.json`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/container-images/image-variants.json)의
`variants`에 다음 형태의 항목을 추가한다.

```json
{
  "id": "cudaX.Y-tfA.B-ubuntu22.04",
  "base_image": "nvidia/cuda:<CUDA-cuDNN-Ubuntu tag>",
  "cuda_version": "X.Y",
  "tensorflow_version": "A.B.C",
  "tensorflow_package": "tensorflow==A.B.C",
  "conda_packages": "ipywidgets jupyterlab micromamba notebook pip",
  "python_version": "3.10",
  "ubuntu_version": "22.04",
  "min_nvidia_driver": "<minimum driver>",
  "support": "experimental",
  "aliases": [
    "cudaX.Y-tfA.B-experimental"
  ]
}
```

`id`에는 날짜를 넣지 않는다. `build_variants.py`가 `default_date_tag` 또는
`--date-tag` 값을 붙여 실제 배포 tag를 만든다. `aliases`에는 날짜 없이 계속
사용할 이름만 둔다. 기존 `stable`이나 `latest`를 새 항목으로 옮기면 다음 push부터
그 alias가 새 image를 가리키므로 별도의 승격 변경으로 검토한다.

정적 목록을 제공하는 `container-images/README.md`의 이미지 표와 alias 표도 함께
갱신한다. 그다음 manifest가 만드는 matrix와 tag를 확인한다.

```bash
cd /home/jy/server_manage/container-images
python3 scripts/variant_matrix.py \
  --variant cudaX.Y-tfA.B-ubuntu22.04 \
  --date-tag YYMMDD
```

출력의 `base_image`, build argument와 `docker_tags`가 추가한 항목과 일치해야 한다.

## 4. 기존 구성 변경

### 4.1 공통 package와 build 환경 변경

apt package, Miniforge·conda, Python package 설치 순서와 image에 포함할 공통 파일은
`Dockerfile`에서 변경한다. 모든 이미지 버전이 하나의 Dockerfile을 공유하므로 이
변경은 특정 CUDA 조합에만 국한되지 않는다.

변경 후에는 최소한 현재 권장 이미지와 package 제약이 가장 강한 legacy 이미지를
각각 build한다. release 전에는 전체 이미지 버전의 build와 smoke test를 확인한다.
build 순서나 필수 package 계약이 달라졌다면
[`test_image_build_config.sh`](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/container-images/tests/test_image_build_config.sh)도
같이 수정한다.

### 4.2 사용자 실행 환경 변경

계정과 그룹 생성, 홈 초기화, Kerberos credential, SSH, Jupyter와 VNC 동작은
`entrypoint.sh`에서 변경한다. 다음 조건을 유지해야 한다.

- 같은 입력으로 container를 재시작해도 계정과 설정이 중복되거나 손상되지 않는다.
- 기존 공유 홈의 `.bashrc`, Jupyter 설정과 password 파일을 임의로 덮어쓰지 않는다.
- NFS `root_squash` 환경에서 공유 홈 전체를 `chown`하지 않는다.
- 홈과 사용자 application에 쓰는 파일은 실제 사용자 UID/GID로 생성한다.
- Kerberos keytab을 container에 전달하지 않고 ccache만 사용한다.
- restricted sudo의 identity 전환, mount와 권한 변경 차단을 유지한다.

`entrypoint.sh`는 image 안에 복사되므로 source만 수정하거나 실행 중인 container를
재시작해도 변경 내용이 적용되지 않는다. 새 날짜 tag로 image를 다시 build·push하고,
운영 container도 그 tag로 다시 생성해야 한다.

### 4.3 tag, alias와 지원 상태 변경

지원 상태와 alias는 `image-variants.json`에서 변경한다. `experimental`을
`stable`로 승격할 때는 해당 날짜 image의 CPU·GPU smoke 결과와 대상 server의 최소
driver 충족 여부를 먼저 확인한다. `stable`과 `latest`는 한 이미지 버전에만 두어
운영자가 어떤 조합이 권장 버전인지 판단할 수 있게 한다.

이미 배포 기록에 사용한 날짜 tag는 같은 이름으로 다시 build하지 않는다. source가
달라졌다면 새로운 `YYMMDD` tag를 사용한다. 같은 tag를 덮어쓰면 target host에 남아
있는 image cache와 registry image가 서로 달라질 수 있다.

### 4.4 build와 test 도구 변경

manifest field를 추가하거나 tag 규칙을 바꾸면 `variant_matrix.py`,
`build_variants.py`, `test_image_variants.py`가 같은 field와 tag를 사용하는지 함께
확인한다. 로컬 build와 배포 workflow가 서로 다른 image를 만들지 않도록 한쪽에만
build argument를 추가하지 않는다.

## 5. 로컬 build

모든 명령은 `container-images` directory에서 실행한다.

```bash
cd /home/jy/server_manage/container-images
```

먼저 실제 build 없이 Docker 명령과 생성될 tag를 확인한다.

```bash
python3 scripts/build_variants.py \
  --variant cuda12.5-tf2.20-ubuntu22.04 \
  --date-tag YYMMDD \
  --dry-run
```

확인한 이미지 버전을 build한다.

```bash
python3 scripts/build_variants.py \
  --variant cuda12.5-tf2.20-ubuntu22.04 \
  --date-tag YYMMDD
```

`--variant`를 생략하면 manifest의 모든 이미지 버전을 순서대로 build한다. Docker
cache 때문에 package 갱신이 반영되지 않았는지 확인해야 할 때만 `--no-cache`를
추가한다.

## 6. 검증

### 6.1 source 회귀 test

```bash
bash tests/test_image_build_config.sh
bash tests/test_entrypoint_root_squash.sh
```

첫 번째 test는 Dockerfile의 version pin, 필수 package와 설치 순서를 확인한다.
두 번째 test는 entrypoint 문법과 UID/GID, 그룹, sudo, NFS 홈, Kerberos, Jupyter와
VNC의 runtime 계약을 확인한다.

### 6.2 image smoke test

build한 날짜와 동일한 tag를 지정해 CPU 환경을 확인한다.

```bash
python3 scripts/test_image_variants.py \
  --variant cuda12.5-tf2.20-ubuntu22.04 \
  --date-tag YYMMDD
```

이 test는 image에 기록된 TensorFlow version, Python, Jupyter, micromamba와
entrypoint 포함 여부를 확인한다. 실제 NVIDIA runtime과 TensorFlow GPU 인식은 대상
GPU host에서 `--gpu`를 추가하여 확인한다.

```bash
python3 scripts/test_image_variants.py \
  --variant cuda12.5-tf2.20-ubuntu22.04 \
  --date-tag YYMMDD \
  --gpu
```

### 6.3 container 생성 계약 확인

image tag가 `infra`의 container 생성 입력으로 올바르게 전달되는지 실제 DB나
container를 변경하지 않고 확인한다.

```bash
python3 scripts/test_uid_create_container.py \
  --variant cuda12.5-tf2.20-ubuntu22.04 \
  --date-tag YYMMDD \
  --print-only
```

출력된 명령에서 repository 이름과 날짜가 포함된 version tag를 확인한다.

## 7. registry 배포

### 7.1 로컬 build와 push

Docker Hub 로그인에 사용할 관리자 계정은
[관리자 계정 통합관리문서](https://docs.google.com/spreadsheets/d/10sNMctmhgjY1GeCX8jRZuzM0vpt6DfJ3V4ah2Tfgr1Q/edit?pli=1&gid=0#gid=0)에서
확인한다. 인증과 test가 완료된 환경에서 `--push`를 추가한다.

```bash
docker login
python3 scripts/build_variants.py \
  --variant cuda12.5-tf2.20-ubuntu22.04 \
  --date-tag YYMMDD \
  --push
```

이 명령은 날짜 tag와 해당 이미지 버전에 선언된 alias를 모두 push한다. 따라서
`stable`이나 `latest`가 포함된 항목은 alias 변경까지 승인된 뒤 실행한다. push 후
대상 GPU host에서 날짜 tag를 pull하고 6.2의 GPU smoke test를 다시 수행한다.

### 7.2 GitHub Actions 상태

build/push workflow 정의에는 `main` 대상 PR merge와 수동 `workflow_dispatch`가
trigger로 작성되어 있다. 그러나 현재 파일은 모노레포 최상위 `.github/workflows/`가
아니라 `container-images/.github/workflows/docker-publish.yml`에 있으므로 GitHub가
자동 workflow로 등록하지 않는다.

workflow를 최상위 위치로 옮기고 working directory, Docker build context와
`DOCKERHUB_USERNAME`·`DOCKERHUB_TOKEN` secret을 확인하기 전까지는 PR merge를 image
배포 완료로 간주하지 않는다. 현재 배포 기준은 7.1의 로컬 build/push다.

## 8. 운영 container 실행과 교체

### 8.1 신규 container 실행

운영 container는 긴 `docker run` 명령을 직접 작성하지 않고 `infra`의 생성 명령을
사용한다. 그래야 UID/GID, 그룹 membership, port, GPU, 공유 홈과 Kerberos ccache가
같은 기준으로 준비된다.

먼저 날짜 tag를 넣고 `--dry-run`으로 계획과 Docker 명령을 확인한다.

```bash
uidctl create-container \
  --name "사용자 이름" \
  --username username \
  --server-id LAB10 \
  --expiration-date YYYY-MM-DD \
  --image decs \
  --version cuda12.5-tf2.20-ubuntu22.04-YYMMDD \
  --created-by operator \
  --email user@example.com \
  --phone 000-0000-0000 \
  --dry-run
```

계획의 target server, GPU, host port, mount source와 최종 image tag를 검토한 뒤 같은
명령에서 `--dry-run`만 제거하여 실행한다. Kerberos 또는 VNC가 필요한 경우 각각
`--enable-kerberos`, `--enable-vnc`를 추가한다.

[`infra`의 container 생성 구현](https://github.com/login?return_to=%2FCSID-DGU%2Fadmin_infra_server/blob/main/user-lifecycle/script/uid_manager/services/create_container.py%23L279-L366)은
target host에 image가 없으면 pull하고, storage와 credential을 준비한 뒤 Docker
container와 DB record를 생성한다.

### 8.2 기존 container에 새 image 적용

`docker restart`는 기존 container가 참조하는 image를 그대로 다시 실행하므로 새로
push한 image를 적용하지 않는다. 공유 홈을 보존한 상태에서 새 날짜 tag를 지정해
container를 교체해야 한다.

교체 전에는 기존 container의 사용자, server, GPU, port, 만료일, VNC·Kerberos
option을 기록하고 새 생성 계획과 비교한다. DB와 port record가 함께 관리되므로
운영 container를 `docker rm`만으로 직접 교체하지 않는다. 새 container에서 SSH,
Jupyter, 선택적인 VNC, 홈 쓰기와 GPU 인식을 확인한 뒤 이전 container를 정리한다.

## 9. 배포 확인과 rollback

배포가 끝나면 다음을 확인한다.

- registry와 target host가 동일한 날짜 tag를 사용하는가?
- 시작 log의 image 버전, CUDA/TensorFlow와 최소 driver가 manifest와 일치하는가?
- TensorFlow가 할당된 GPU를 인식하는가?
- 사용자 UID/GID와 primary·supplemental group이 공유 스토리지 권한과 일치하는가?
- 공유 홈에서 읽기·쓰기, SSH와 Jupyter가 동작하는가?
- Kerberos 사용 시 ccache가 보이고 keytab은 container에 없는가?

문제가 발견되면 `stable`이나 `latest`의 과거 의미를 추측하지 않고, 마지막으로
검증한 날짜 tag를 지정하여 container를 다시 생성한다. 문제가 있는 날짜 tag는
덮어쓰지 않고 manifest의 `support`와 alias를 수정하여 신규 사용을 막은 뒤 원인을
수정한 새 날짜 tag를 배포한다.

## 10. 운영 안전 수칙

- 실제 사용자 password를 image layer나 manifest에 넣지 않는다.
- keytab을 image 또는 container mount로 제공하지 않는다.
- source 변경, local image, registry image와 실행 중인 container를 구분해 진단한다.
- 실제 push 전에는 `--dry-run`의 전체 tag 목록을 확인한다.
- `experimental` 이미지 버전을 `stable`로 승격하기 전에 대상 GPU test를 수행한다.
- 기존 공유 홈을 사용하는 test는 파일과 권한을 변경할 수 있으므로 별도 test 사용자와
  경로에서 수행한다.
