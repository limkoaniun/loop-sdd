#!/usr/bin/env bash
# Install the loop-sdd skill for Claude Code.
#   install.sh --user              symlink into ~/.claude/skills/loop-sdd (all projects)
#   install.sh /path/to/project    copy into <project>/.claude/skills/loop-sdd
#   add --force to replace an existing project copy
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
src="$here/.claude/skills/loop-sdd"
[ -f "$src/SKILL.md" ] || { echo "error: skill not found at $src" >&2; exit 2; }

usage() { sed -n '2,5p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2; }

next_steps() {
  cat <<EOT
Installed. Next:
  cd $1 && claude
  /loop-sdd init      # writes a starter loop.json if missing, validates, checks quota sources
  /loop-sdd status
  /loop 2m /loop-sdd tick
EOT
}

[ $# -ge 1 ] || usage
force=0
target=""
for arg in "$@"; do
  case "$arg" in
    --user) target="--user" ;;
    --force) force=1 ;;
    --*) usage ;;
    *) target="$arg" ;;
  esac
done
[ -n "$target" ] || usage

if [ "$target" = "--user" ]; then
  dest="$HOME/.claude/skills/loop-sdd"
  mkdir -p "$(dirname "$dest")"
  if [ -L "$dest" ]; then
    if [ "$(cd "$dest" && pwd -P)" = "$(cd "$src" && pwd -P)" ]; then
      echo "already linked: $dest -> $src"; next_steps "<your project>"; exit 0
    fi
    echo "refused: $dest is a symlink to somewhere else; remove it first" >&2; exit 1
  fi
  if [ -e "$dest" ]; then
    echo "refused: $dest exists and is not a symlink; move it aside first" >&2; exit 1
  fi
  ln -s "$src" "$dest"
  echo "linked: $dest -> $src"
  next_steps "<your project>"
  exit 0
fi

proj="$target"
[ -d "$proj" ] || { echo "error: not a directory: $proj" >&2; exit 2; }
[ -d "$proj/.git" ] || echo "warning: $proj is not a git repository root; the loop needs git when it runs"
dest="$proj/.claude/skills/loop-sdd"
if [ -e "$dest" ] && [ "$force" -ne 1 ]; then
  echo "refused: $dest exists; pass --force to replace it" >&2; exit 1
fi
rm -rf "$dest"
mkdir -p "$dest"
cp -R "$src/SKILL.md" "$src/actions" "$src/seats" "$src/bin" "$dest/"
find "$dest" -name '__pycache__' -type d -prune -exec rm -rf {} +
echo "copied: $dest"
next_steps "$proj"
