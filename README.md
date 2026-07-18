# 운영 위키

이 저장소는 Markdown 원본, PDF 산출물, Docker 배포 구성을 한곳에서 관리한다.
공용 서비스는 Docker Compose로 실행하며 특정 사용자의 홈 디렉터리, `.venv`,
user systemd에 의존하지 않는다.

## 디렉터리 구조

```text
.
├── md/
│   ├── system/      현재 서버 관리 문서 원본
│   ├── backend/     backend 문서
│   ├── frontend/    frontend 문서
│   ├── infra/       infra 문서
│   └── user/        user 문서
├── pdf/
│   ├── system/      현재 서버 관리 PDF
│   ├── backend/
│   ├── frontend/
│   ├── infra/
│   └── user/
├── docker/          Git 동기화와 Nginx 설정
├── compose.yml
├── Dockerfile
├── manage.py        호스트 전용 관리 진입점
├── export_manuals.py
├── sync_wiki_docs.py
└── mkdocs.yml
```

현재 작성된 문서는 모두 `md/system/`에 있고 대응 PDF는 `pdf/system/`에 있다.
다른 분류의 문서를 추가할 때 같은 이름의 `md/<분류>/`와 `pdf/<분류>/`를
사용한다.

## 운영 구조

```text
관리자별 Git clone
        │ commit / push
        ▼
GitHub main
        │ 주기적 fetch
        ▼
sync 컨테이너 ── PDF 생성 ── MkDocs build
        │
        ▼
site volume ── Nginx :30097 ── NAT :9397
```

각 관리자는 자기 계정의 clone에서 `md/`를 수정해 push한다. 공용 컨테이너는
GitHub `main`만 읽기 때문에 여러 관리자가 동일한 호스트 디렉터리의 소유권을
공유할 필요가 없다. 웹 HTTP에는 인증이 없지만 문서 수정은 GitHub push/merge
권한이 있어야 가능하다.

## 호스트 관리 명령

호스트에서는 `manage.py`만 진입점으로 사용한다. Python 표준 라이브러리만
사용하므로 `.venv`가 필요 없다.

```bash
python3 manage.py up
python3 manage.py status
python3 manage.py logs sync --follow
python3 manage.py sync-now
python3 manage.py publish-local
python3 manage.py down
```

`down`은 container만 중지하고 Git clone cache와 마지막 site volume은 보존한다.
volume까지 지우는 명령은 관리 스크립트에서 의도적으로 제공하지 않는다.

## GitHub 저장소 접근

저장소가 public이면 별도 설정이 없다. private이면 `.env.example`을
`.env`로 복사하고 Contents read-only 권한의 fine-grained token을 넣는다.
`.env`는 Git에서 제외된다.

```bash
cp .env.example .env
# .env의 WIKI_GITHUB_TOKEN 설정
python3 manage.py up
```

현재 컨테이너의 익명 clone 요청에는 GitHub 자격증명이 필요하므로, 저장소를
public으로 전환하지 않는다면 위 read-only token 설정이 필요하다. token은 wiki
HTTP 인증과 무관하며 컨테이너가 문서 원본을 읽을 때만 사용한다.

`manage.py up`은 token 유무와 관계없이 현재 host checkout으로 site volume을 먼저
만들어 서비스 공백을 막는다. token을 아직 넣지 않았다면 다른 관리자의 `main`
변경은 자동으로 가져오지 못하므로, host에서 pull한 뒤 다음 명령으로 게시한다.

```bash
git pull --ff-only
python3 manage.py publish-local
```

## 문서 수정

`md/` 아래의 Markdown만 직접 수정한다.

```bash
git pull --ff-only
# md/system/*.md 등 수정
git add md
git commit
git push
```

변경이 `main`에 반영되면 sync 컨테이너가 기본 60초 안에 새 commit을 감지한다.
새 PDF를 만들고 MkDocs build가 성공한 경우에만 Nginx가 읽는 volume을 교체한다.
빌드 실패 시 마지막 성공 사이트를 계속 제공한다.

## PDF export

공용 서비스에서는 `sync_wiki_docs.py`와 `export_manuals.py`가 컨테이너 내부에서
실행된다. Chromium과 한글 글꼴도 image에 포함되어 있어 Markdown 변경 시 웹용
PDF가 자동으로 갱신된다.

저장소의 `pdf/`에도 새 PDF를 남기고 싶을 때만 호스트 명령을 실행한다.

```bash
python3 manage.py export
git add pdf
git commit
git push
```

호스트 export에는 로컬 Chrome/Chromium과 Noto CJK 계열 글꼴이 필요하지만
MkDocs나 `.venv`는 필요 없다.

## 컨테이너 내부 스크립트

- `sync_wiki_docs.py`: `md/`를 MkDocs 입력 tree로 변환하고 PDF를 복사한다.
- `export_manuals.py`: `md/system/`의 현재 문서를 `pdf/system/`에 내보낸다.
- `docker/sync-loop.sh`: Git 변경 감지, 위 두 스크립트 실행, 성공한 site 게시.

`wiki-docs/`와 `site/`는 생성물이므로 Git에 포함하지 않는다.

## 설정

`.env`에서 다음 값을 바꿀 수 있다.

| 변수 | 기본값 | 역할 |
| --- | --- | --- |
| `WIKI_REPOSITORY_URL` | GitHub origin | 읽을 저장소 |
| `WIKI_BRANCH` | `main` | 배포 branch |
| `WIKI_SYNC_INTERVAL_SECONDS` | `60` | 변경 확인 주기 |
| `WIKI_GITHUB_TOKEN` | 빈 값 | private 저장소 read token |
| `WIKI_BIND_ADDRESS` | `0.0.0.0` | listen 주소 |
| `WIKI_PORT` | `30097` | 호스트 port |

설정 렌더링만 확인하려면 다음 명령을 쓴다.

```bash
python3 manage.py config
```

## 접속 주소

```text
http://127.0.0.1:30097/
http://210.94.179.19:9397/
```

외부 `210.94.179.19:9397`은 현재 관리 호스트의 `30097`로 NAT된다. 서비스를 다른
호스트로 옮기면 NAT와 firewall 대상도 변경해야 한다.

## 편집 방식과 Kubernetes

이 위키는 브라우저 편집형이 아니라 Git-backed documentation이다. 코드와 문서의
review 이력을 같이 관리하는 현재 목적에 맞는다. 브라우저 편집 UI가 필요하면
Wiki.js 같은 database 기반 제품을 별도로 검토해야 한다.

현재는 정적 웹 service와 sync worker 하나이므로 Docker Compose가 충분하다.
기존 Kubernetes cluster, Ingress, persistent volume, 배포 모니터링을 이미 공용으로
운영하는 경우에만 같은 구성을 Deployment와 sync sidecar/CronJob으로 옮긴다.
