"""SessionStart hook: tell the developer about plugins this repo enables that aren't installed.

A repo's .claude/settings.json can enable a plugin, but Claude Code doesn't install it from there:
each developer has to run `claude plugin install` once. Until they do, the plugin's skills
silently don't load. This hook lists those plugins with the command to run, shows the developer
a one-line notice and tells Claude, so it can offer to run the install. It never installs anything
itself, and prints nothing when every enabled plugin is installed.
"""
import json
import os
import sys


def load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def main():
    try:
        hook_input = json.load(sys.stdin)
    except ValueError:
        hook_input = {}
    project = os.environ.get("CLAUDE_PROJECT_DIR") or hook_input.get("cwd") or os.getcwd()
    project = os.path.realpath(project)
    config = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")

    # Plugins the repo enables, and the scope to install each at (local wins over project).
    wanted = {}
    for name, scope in (("settings.json", "project"), ("settings.local.json", "local")):
        enabled = load(os.path.join(project, ".claude", name)).get("enabledPlugins") or {}
        for plugin, on in enabled.items():
            if on is True:
                wanted[plugin] = scope
            elif on is False:
                wanted.pop(plugin, None)
    if not wanted:
        return

    installed = load(os.path.join(config, "plugins", "installed_plugins.json")).get("plugins") or {}

    def is_installed(plugin):
        for entry in installed.get(plugin) or []:
            if entry.get("scope") in ("user", "managed"):
                return True
            path = entry.get("projectPath")
            if path and os.path.realpath(path) == project:
                return True
        return False

    missing = sorted(p for p in wanted if not is_installed(p))
    if not missing:
        return

    commands = [f"claude plugin install {p} --scope {wanted[p]}" for p in missing]
    names = ", ".join(p.split("@")[0] for p in missing)
    if len(missing) == 1:
        notice = f"This repo uses the {names} plugin, but it isn't installed on this machine. Run: {commands[0]}"
    else:
        notice = f"This repo uses plugins that aren't installed on this machine ({names}). Run: " + " && ".join(commands)
    notice += " (then start a new session), or ask Claude to do it."
    context = (
        "This repo's .claude settings enable these plugins, but they are not installed on this machine, "
        f"so their skills are not loaded in this session: {', '.join(missing)}. "
        "If the user's work needs them, or they ask, offer to install them with: "
        + "; ".join(commands)
        + ". Run it only after the user agrees. The skills load in the next session, so tell them to start one afterwards."
    )
    print(json.dumps({
        "systemMessage": notice,
        "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": context},
    }))


if __name__ == "__main__":
    main()
