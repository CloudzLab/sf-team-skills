#!/usr/bin/env bash
# One-time cleanup: remove Salesforce skills installed with `npx skills add forcedotcom/sf-skills`,
# so Claude Code uses only the plugin versions. Everything removed is backed up first.
#
#   scripts/cleanup-npx-salesforce-skills.sh            show what would be removed
#   scripts/cleanup-npx-salesforce-skills.sh --apply    back up, then remove
set -euo pipefail

LOCK="$HOME/.agents/.skill-lock.json"
SKILLS_DIR="$HOME/.agents/skills"
CLAUDE_SKILLS="$HOME/.claude/skills"
SOURCE="forcedotcom/sf-skills"

if [[ ! -f "$LOCK" ]]; then
  echo "No npx skills lockfile at $LOCK. Nothing to clean up."
  exit 0
fi

names=$(python3 - "$LOCK" "$SOURCE" <<'EOF'
import json, sys
lock = json.load(open(sys.argv[1])).get("skills", {})
print("\n".join(sorted(n for n, v in lock.items() if v.get("source") == sys.argv[2])))
EOF
)

if [[ -z "$names" ]]; then
  echo "No skills from $SOURCE are installed with npx. Nothing to clean up."
  exit 0
fi

count=$(printf '%s\n' "$names" | wc -l | tr -d ' ')
echo "Found $count skill(s) installed with npx from $SOURCE:"
printf '  %s\n' $names

if [[ "${1:-}" != "--apply" ]]; then
  echo
  echo "Dry run. Re-run with --apply to back them up and remove them."
  exit 0
fi

backup="$HOME/.agents/backup-sf-skills-$(date +%Y-%m-%d-%H%M%S)"
mkdir -p "$backup/skills" "$backup/links"
cp "$LOCK" "$backup/"
printf '%s\n' "$names" > "$backup/names.txt"
for name in $names; do
  [[ -e "$SKILLS_DIR/$name" ]] && cp -R "$SKILLS_DIR/$name" "$backup/skills/"
  [[ -L "$CLAUDE_SKILLS/$name" || -e "$CLAUDE_SKILLS/$name" ]] && cp -RP "$CLAUDE_SKILLS/$name" "$backup/links/"
done
echo "Backed up to $backup"

# shellcheck disable=SC2086
npx --yes skills remove --global --yes $names

left=0
for name in $names; do
  if [[ -e "$SKILLS_DIR/$name" || -L "$CLAUDE_SKILLS/$name" ]]; then
    echo "Still present: $name"
    left=1
  fi
done
if [[ $left -eq 0 ]]; then
  echo "Done. Restart Claude Code to load only the plugin versions."
else
  echo "Some skills were not removed; delete them by hand (a backup is in $backup)."
  exit 1
fi
