"""Reset a developer's Salesforce Claude Code setup to the team baseline.

Removes Salesforce plugins installed outside the team setup, so only the core plugins from the
org's managed settings remain, then runs the npx cleanup. Everything it changes is backed up first.

    python3 reset-salesforce-setup.py            show what would change
    python3 reset-salesforce-setup.py --apply    back up, then change

"Salesforce plugin" means any plugin from a team catalog (the catalogs the org's managed settings
register: `salesforce`, `cloudzlab`, `b2c-developer-tooling`, ...), plus a plugin with the same name
from another catalog (for example agentforce-adlc from the Claude directory).
It never touches project-scope installs (those come from a repo's committed settings), other
catalogs' own plugins, or downloaded plugin files.
"""
import datetime
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

FALLBACK_CATALOGS = ("salesforce", "cloudzlab")
MANAGED_FILES = (
    Path("/Library/Application Support/ClaudeCode/managed-settings.json"),
    Path("/etc/claude-code/managed-settings.json"),
)
NPX_CLEANUP = Path(__file__).resolve().parents[2] / "sf-npx-cleanup" / "scripts" / "cleanup-npx-salesforce-skills.sh"


def load(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def main():
    apply = "--apply" in sys.argv[1:]
    config = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    user_settings_path = config / "settings.json"
    installed_path = config / "plugins" / "installed_plugins.json"

    managed, team_catalogs = {}, set()
    for path in (config / "remote-settings.json",) + MANAGED_FILES:
        settings = load(path)
        managed.update({k: v for k, v in (settings.get("enabledPlugins") or {}).items() if v is True})
        team_catalogs.update(settings.get("extraKnownMarketplaces") or {})
    team_catalogs = tuple(sorted(team_catalogs)) or FALLBACK_CATALOGS
    core = sorted(k for k in managed if k.rsplit("@", 1)[-1] in team_catalogs)
    if not core:
        print("The team settings haven't reached this machine yet, so there is no baseline to reset to.")
        print("Sign in with your claude.ai account (/login), restart Claude Code, and run this again.")
        sys.exit(2)

    team_names = set()
    for catalog in team_catalogs:
        manifest = load(config / "plugins" / "marketplaces" / catalog / ".claude-plugin" / "marketplace.json")
        team_names.update(p.get("name") for p in manifest.get("plugins") or [])

    def is_salesforce(key):
        name, _, catalog = key.rpartition("@")
        return catalog in team_catalogs or name in team_names

    uninstalls, kept_project = [], []
    for key, entries in sorted((load(installed_path).get("plugins") or {}).items()):
        if not is_salesforce(key):
            continue
        for entry in entries:
            scope = entry.get("scope")
            if scope in ("user", "local"):
                uninstalls.append((key, scope, entry.get("projectPath")))
            elif scope == "project":
                kept_project.append((key, entry.get("projectPath")))

    uninstalling_user = {k for k, s, _ in uninstalls if s == "user"}
    leftovers = sorted(k for k in (load(user_settings_path).get("enabledPlugins") or {})
                       if is_salesforce(k) and k not in uninstalling_user)

    print(f"Team core plugins (kept, set by your org): {len(core)}")
    if uninstalls:
        print(f"\nSalesforce plugins to uninstall ({len(uninstalls)}):")
        for key, scope, project in uninstalls:
            print(f"  {key}  [{scope}{' in ' + project if project else ''}]")
    if leftovers:
        print(f"\nOld entries to remove from {user_settings_path} ({len(leftovers)}):")
        print("  (core ones stay on through the org settings)")
        for key in leftovers:
            print(f"  {key}")
    if kept_project:
        print("\nLeft alone (enabled by a repo's committed settings):")
        for key, project in kept_project:
            print(f"  {key}  in {project}")
    if not uninstalls and not leftovers:
        print("\nNo Salesforce plugins outside the team setup.")

    if not apply:
        print("\nDry run, nothing changed. Re-run with --apply to back up and apply.")
        if NPX_CLEANUP.exists():
            print("\n--- npx skills ---", flush=True)
            subprocess.run(["bash", str(NPX_CLEANUP)])
        return

    failed = []
    if uninstalls or leftovers:
        backup = config / f"backup-sf-reset-{datetime.datetime.now():%Y-%m-%d-%H%M%S}"
        backup.mkdir(parents=True)
        for path in (user_settings_path, installed_path):
            if path.exists():
                shutil.copy2(path, backup / path.name)
        restore = [f"claude plugin install {k} --scope {s}" + (f"   # run in {p}" if p else "") for k, s, p in uninstalls]
        (backup / "reinstall-commands.txt").write_text("\n".join(restore) + "\n")
        print(f"\nBacked up to {backup}")

        sys.stdout.flush()
        for key, scope, project in uninstalls:
            result = subprocess.run(["claude", "plugin", "uninstall", key, "--scope", scope],
                                    cwd=project if project and os.path.isdir(project) else None,
                                    capture_output=True, text=True)
            ok = result.returncode == 0
            print(f"  {'removed' if ok else 'FAILED '} {key} [{scope}]")
            if not ok:
                failed.append(key)
                print("    " + (result.stderr or result.stdout).strip().replace("\n", "\n    "))

        settings = load(user_settings_path)
        enabled = settings.get("enabledPlugins") or {}
        removed = [k for k in enabled if is_salesforce(k)]
        for key in removed:
            del enabled[key]
        if removed:
            user_settings_path.write_text(json.dumps(settings, indent=2, ensure_ascii=False) + "\n")
            print(f"  cleared {len(removed)} old entr{'y' if len(removed) == 1 else 'ies'} from {user_settings_path.name}")

    npx_failed = False
    if NPX_CLEANUP.exists():
        print("\n--- npx skills ---", flush=True)
        npx_failed = subprocess.run(["bash", str(NPX_CLEANUP), "--apply"]).returncode != 0

    if failed or npx_failed:
        print("\nSome steps failed (see above). Nothing else was changed.")
        sys.exit(1)
    print("\nDone. Restart Claude Code: the core plugins stay, everything else Salesforce is gone.")


if __name__ == "__main__":
    main()
