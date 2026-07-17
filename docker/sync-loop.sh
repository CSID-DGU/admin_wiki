#!/bin/sh
set -eu

repository_url=${WIKI_REPOSITORY_URL:-https://github.com/CSID-DGU/admin_infra_server.git}
branch=${WIKI_BRANCH:-main}
interval=${WIKI_SYNC_INTERVAL_SECONDS:-60}
repo_dir=/repo
site_dir=/site
next_site=/tmp/server-manage-wiki-next

case "$interval" in
  ''|*[!0-9]*)
    echo "WIKI_SYNC_INTERVAL_SECONDS must be a positive integer" >&2
    exit 2
    ;;
  0)
    echo "WIKI_SYNC_INTERVAL_SECONDS must be greater than zero" >&2
    exit 2
    ;;
esac

export GIT_TERMINAL_PROMPT=0

update_repository() {
  if [ ! -d "$repo_dir/.git" ]; then
    find "$repo_dir" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
    git clone --depth 1 --branch "$branch" --single-branch "$repository_url" "$repo_dir"
    return
  fi

  git -C "$repo_dir" remote set-url origin "$repository_url"
  git -C "$repo_dir" fetch --prune --depth 1 origin "$branch"
  git -C "$repo_dir" checkout --detach --force FETCH_HEAD
}

build_site() {
  revision=$(git -C "$repo_dir" rev-parse HEAD)
  deployed_revision=$(cat "$site_dir/.source-revision" 2>/dev/null || true)
  if [ "$revision" = "$deployed_revision" ] && [ -s "$site_dir/index.html" ]; then
    return
  fi

  echo "building wiki from ${revision}"
  python3 "$repo_dir/wiki/export_manuals.py"
  python3 "$repo_dir/wiki/sync_wiki_docs.py"

  rm -rf "$next_site"
  mkdocs build \
    --clean \
    --strict \
    --config-file "$repo_dir/wiki/mkdocs.yml" \
    --site-dir "$next_site"
  printf '%s\n' "$revision" > "$next_site/.source-revision"

  find "$site_dir" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
  cp -a "$next_site"/. "$site_dir"/
  echo "published wiki revision ${revision}"
}

while :; do
  if update_repository && build_site; then
    :
  else
    echo "wiki sync failed; keeping the last successful site" >&2
  fi
  sleep "$interval"
done
