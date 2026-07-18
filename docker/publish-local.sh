#!/bin/sh
set -eu

source_dir=/source
work_dir=/tmp/admin-wiki-source
next_site=/tmp/admin-wiki-local
site_dir=/site

test -d "$source_dir/md"
rm -rf "$work_dir" "$next_site"
mkdir -p "$work_dir"
cp -R "$source_dir"/. "$work_dir"/

python3 "$work_dir/export_manuals.py"
python3 "$work_dir/sync_wiki_docs.py"
mkdocs build \
  --clean \
  --strict \
  --config-file "$work_dir/mkdocs.yml" \
  --site-dir "$next_site"

revision=$(git -c safe.directory="$source_dir" -C "$source_dir" rev-parse HEAD 2>/dev/null || printf 'local')
printf '%s\n' "$revision" > "$next_site/.source-revision"
find "$site_dir" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
cp -a "$next_site"/. "$site_dir"/
if [ "$(id -u)" -eq 0 ]; then
  chown -R wiki:wiki "$site_dir"
fi
echo "published local wiki revision ${revision}"
