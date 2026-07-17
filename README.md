# 운영 위키

이 디렉터리는 저장소의 `MANUAL.md`를 PDF와 웹 위키로 게시하는 구성 전체를
관리한다. 공용 운영 방식은 Docker Compose이며 특정 사용자의 홈 디렉터리나
user systemd에 의존하지 않는다.

## 운영 구조

```text
관리자별 Git clone
        │ commit / push
        ▼
GitHub main
        │ 60초 간격 fetch
        ▼
wiki-sync 컨테이너 ── Markdown 동기화 + PDF/MkDocs 빌드
        │
        ▼
Docker site volume ── nginx 컨테이너 :30097 ── NAT :9397
```

관리자는 각자 쓰기 가능한 위치에 저장소를 clone해 문서를 수정한다. 공용
컨테이너는 GitHub `main`만 읽으므로 여러 관리자가 같은 서버 디렉터리의
소유권을 공유할 필요가 없다. 웹 페이지에는 인증이 없지만 수정 권한은 GitHub
저장소의 push/merge 권한으로 제한된다.

이 구성은 브라우저에서 직접 문서를 편집하는 위키가 아니라 Git-backed
documentation이다. 코드와 문서 변경을 같은 review 이력으로 관리하려는 현재
저장소에는 이 방식이 맞다.

## 원본 문서

- `/MANUAL.md` — 메인 목차
- `/container-images/MANUAL.md`
- `/kerberos-nfs/MANUAL.md`
- `/monitoring/MANUAL.md`
- `/remote-operations/MANUAL.md`
- `/server-state/MANUAL.md`
- `/user-lifecycle/MANUAL.md`

PDF나 `wiki-docs/`, `site/`를 직접 수정하지 않는다. 각 `MANUAL.md`가 원본이다.

## 디렉터리 구성

| 경로 | 역할 |
| --- | --- |
| `compose.yml` | Git 동기화 컨테이너와 Nginx 컨테이너 정의 |
| `Dockerfile` | Git, Chromium, 한글 글꼴, MkDocs 빌드 환경 |
| `docker/sync-loop.sh` | `main` 변경 감지, PDF와 사이트 재생성·배포 |
| `docker/nginx.conf` | 무인증 정적 웹 서비스와 `/healthz` |
| `mkdocs.yml` | navigation, theme, 검색과 Markdown 설정 |
| `export_manuals.py` | 개별 PDF와 통합 PDF 생성 |
| `sync_wiki_docs.py` | 분산된 원본을 MkDocs 입력 디렉터리로 동기화 |
| `wiki-assets/extra.css` | 한글 글꼴과 표·문서 폭 보정 |
| `pdf/` | 저장소에도 보관하는 PDF 산출물 |
| `systemd/`, `install_wiki_service.py` | 로컬 개발용 user service 대안 |

## 공용 서비스 기동

요구 사항은 Docker Engine과 Docker Compose plugin이다. 이 호스트에서 기존
user systemd 서비스가 `30097`을 사용 중이면 먼저 중지한다.

```bash
systemctl --user disable --now server-manage-wiki.service
cd /path/to/admin_infra_server/wiki
docker compose up -d --build
```

기본 설정은 다음과 같다.

- 저장소: `https://github.com/CSID-DGU/admin_infra_server.git`
- 배포 branch: `main`
- 확인 주기: 60초
- listen: `0.0.0.0:30097`
- HTTP 인증: 없음

기본값을 바꿀 때만 `.env.example`을 `.env`로 복사해 수정한다. `.env`는 Git에
포함되지 않는다.

```bash
cp .env.example .env
docker compose up -d --build
```

상태와 로그는 다음 명령으로 확인한다.

```bash
docker compose ps
docker compose logs -f sync
docker compose logs -f web
curl -fsS http://127.0.0.1:30097/healthz
```

컨테이너를 중지할 때는 `docker compose down`을 사용한다. `down -v`는 공용
clone cache와 마지막 site volume까지 삭제하므로 초기화가 명확히 필요할 때만
사용한다.

## 관리자 문서 수정 흐름

각 관리자는 자신의 계정과 clone에서 다음 순서로 작업한다.

```bash
git pull --ff-only
# 해당 디렉터리의 MANUAL.md 수정
git add MANUAL.md '*/MANUAL.md'
git commit
git push
```

변경이 `main`에 반영되면 sync 컨테이너가 최대 60초 안에 새 commit을 감지한다.
그 commit에서 PDF를 새로 만들고 MkDocs를 빌드한 뒤 성공한 결과만 Nginx volume에
게시한다. 빌드 실패 시에는 마지막으로 성공한 사이트를 계속 제공한다.

따라서 Markdown이 바뀌면 웹 문서와 서비스에서 내려받는 PDF가 함께 바뀐다.
저장소에 보관하는 `wiki/pdf/*.pdf`도 갱신하려면 로컬에서 exporter를 실행한 뒤
PDF 변경을 commit한다.

## 로컬 생성과 검증

```bash
cd /path/to/admin_infra_server
python3 wiki/export_manuals.py
python3 wiki/sync_wiki_docs.py
wiki/.venv/bin/mkdocs build --strict --clean -f wiki/mkdocs.yml
```

PDF exporter는 Python 3.10 이상, Chrome/Chromium, Noto CJK 계열 한글 글꼴을
사용한다. Docker image에는 이 요구 사항이 포함되어 있다.

## 접속 주소

현재 네트워크 구성에서는 다음 주소를 사용한다.

```text
http://127.0.0.1:30097/
http://210.94.179.19:9397/
```

외부 `210.94.179.19:9397`은 이 관리 호스트의 `30097`로 NAT된다. Docker를 다른
호스트로 옮기면 NAT와 firewall 대상도 함께 변경해야 한다.

## Docker Compose와 Kubernetes 선택

현재 서비스는 정적 사이트 하나와 동기화 작업 하나뿐이므로 단일 관리 호스트의
Docker Compose가 가장 단순하다. 이미 공용 Kubernetes cluster, Ingress,
persistent volume, 배포 모니터링을 운영하고 있을 때는 같은 구성을 Deployment와
동기화 sidecar/CronJob으로 옮기는 편이 맞다. 단지 여러 관리자가 수정할 수 있게
하려는 목적만으로 Kubernetes를 추가할 필요는 없다.

브라우저 편집 UI가 반드시 필요해지면 이 MkDocs 구성을 억지로 확장하기보다
Wiki.js 같은 별도 wiki 제품과 database를 도입하는 문제로 다시 판단한다.

## 로컬 user systemd 대안

Docker 없이 개인 clone을 잠깐 서비스할 때만 사용할 수 있다.

```bash
python3 wiki/install_wiki_service.py
```

installer는 `wiki/.venv`와 실행 계정의
`~/.config/systemd/user/server-manage-wiki.service`를 사용한다. 공용 운영에는
Docker Compose 구성을 사용한다.
