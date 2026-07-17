#!/bin/sh
case "$1" in
  *Username*) printf '%s\n' "${WIKI_GIT_USERNAME:-x-access-token}" ;;
  *Password*) printf '%s\n' "${WIKI_GITHUB_TOKEN:-}" ;;
  *) exit 1 ;;
esac
