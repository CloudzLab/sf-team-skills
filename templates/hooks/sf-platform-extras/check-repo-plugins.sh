#!/usr/bin/env bash
# SessionStart hook: runs check-repo-plugins.py with the first usable Python 3.
# Exits silently when there is none, so a missing Python never blocks a session.
dir="$(cd "$(dirname "$0")" && pwd)"
for py in python3 python; do
  path="$(command -v "$py" 2>/dev/null)" || continue
  # On macOS, /usr/bin/python3 is a stub that opens an installer dialog unless the Command Line Tools are present.
  if [ "$(uname)" = "Darwin" ] && [ "$path" = "/usr/bin/python3" ] && ! xcode-select -p >/dev/null 2>&1; then
    continue
  fi
  "$path" -c 'import sys; sys.exit(sys.version_info[0] < 3)' 2>/dev/null || continue
  exec "$path" "$dir/check-repo-plugins.py"
done
exit 0
