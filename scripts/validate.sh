#!/usr/bin/env bash
# Validate the catalog and every plugin with Claude Code's own validator (strict: warnings fail).
set -euo pipefail
cd "$(dirname "$0")/.."
claude plugin validate --strict .
for plugin in plugins/*/; do
  claude plugin validate --strict "$plugin"
done
python3 -m json.tool managed-settings.json > /dev/null
for template in templates/project-settings/*.json; do
  python3 -m json.tool "$template" > /dev/null
done
echo "All plugins, catalog and settings files are valid."
