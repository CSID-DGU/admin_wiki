# container-images 운영

> [개요](index.md) · [설계](design.md)

## 1. 빌드와 배포 흐름

```text
image-variants.json
        |
        +--> variant_matrix.py --> GitHub Actions matrix --> build/push
        |
        +--> build_variants.py ---------------------------> local build/push
        |
        +--> test_image_variants.py ----------------------> smoke test
```

전체 명령 확인:

```bash
cd /home/jy/server_manage/container-images
python3 scripts/build_variants.py --dry-run
```

특정 variant build:

```bash
python3 scripts/build_variants.py \
  --variant cuda12.5-tf2.20-ubuntu22.04
```

registry push는 build 결과와 tag 목록을 확인한 뒤 `--push`를 추가한다. 날짜
tag는 재현 가능한 배포 지점을 만들고, `stable`/`latest` alias는 현재 권장
variant를 가리킨다. 운영 기록에는 alias보다 날짜가 포함된 tag를 남기는 것이
좋다.

## 2. 테스트 전략

빠른 정적/회귀 테스트:

```bash
cd /home/jy/server_manage/container-images
bash tests/test_image_build_config.sh
bash tests/test_entrypoint_root_squash.sh
```

이미지 smoke test:

```bash
python3 scripts/test_image_variants.py \
  --variant cuda12.5-tf2.20-ubuntu22.04
```

실제 GPU까지 확인할 때만 `--gpu`를 사용한다. 사용자 생성 계약은 실제 DB를
바꾸지 않는 dry-run/print 경로로 검증한다.

```bash
python3 scripts/test_uid_create_container.py \
  --variant cuda12.5-tf2.20-ubuntu22.04 \
  --print-only
```

## 3. 변경 가이드

### 새 variant 추가

1. `image-variants.json`에 버전, base image와 최소 driver를 추가한다.
2. `python3 scripts/variant_matrix.py` 결과의 tag를 확인한다.
3. build dry-run과 shell 회귀 테스트를 실행한다.
4. 실제 image smoke test와 가능하면 대상 GPU host test를 수행한다.
5. 검증 전에는 `support: experimental`과 명시적인 alias를 사용한다.

### 공통 런타임 변경

`Dockerfile` 변경과 `entrypoint.sh` 변경을 구분한다. package/파일은 build
시점에 넣고, 사용자 UID나 mount처럼 컨테이너마다 달라지는 항목만 entrypoint
에서 처리한다. entrypoint 변경은 재시작 시 idempotent한지, 기존 홈의 파일을
덮어쓰지 않는지, root_squash 환경에서 동작하는지를 함께 확인한다.

## 4. 운영 안전 수칙

- 실제 사용자 비밀번호를 image layer나 manifest에 넣지 않는다.
- keytab을 image 또는 container mount로 제공하지 않는다.
- `latest`만 기록하지 말고 장애 분석이 가능한 날짜 tag를 남긴다.
- experimental variant를 stable alias로 바꾸기 전에 실장비 GPU test를 한다.
- sudo 완화는 ccache와 host bind mount에 대한 우회 가능성을 먼저 검토한다.
- 로컬 source 변경과 이미 registry에 push된 image를 구분해서 진단한다.
