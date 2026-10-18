---
name: sf-setup-reset
description: "Resets the developer's Salesforce Claude Code setup to the team baseline: uninstalls Salesforce plugins installed outside the team setup (from the salesforce or cloudzlab catalogs, or same-named copies from other catalogs), clears old Salesforce entries from their user settings, and removes old npx copies of Salesforce skills. Everything is backed up first; the org's core plugins stay. TRIGGER when the user asks to reset, start fresh, do a clean or fresh install, or match the team setup for Salesforce plugins or skills. DO NOT TRIGGER for removing only npx skills (use sf-npx-cleanup), for one specific plugin (use /plugin), or for non-Salesforce plugins."
---

# Reset the Salesforce setup to the team baseline

The org's managed settings switch on the team's core Salesforce plugins for everyone, but they only add things: plugins a developer installed earlier stay. This skill removes those, so the machine matches the team setup. Afterwards the developer switches specialist plugins back on only where they need them.

What it changes:
- **Uninstalls** Salesforce plugins installed for the user (`user` scope) or for one repo (`local` scope): anything from the `salesforce` or `cloudzlab` catalogs, and same-named copies from other catalogs (e.g. `agentforce-adlc` from the Claude directory).
- **Clears old entries** for Salesforce plugins from `~/.claude/settings.json`. Core plugins stay on through the org settings.
- **Removes npx copies** of Salesforce skills, using the `sf-npx-cleanup` script.

What it leaves alone: the core plugins, plugins a repo enables in its committed settings (`project` scope), other catalogs' own plugins (e.g. B2C Commerce tooling, Agentforce Mobile SDK), and downloaded plugin files.

The script is in this skill's base directory at `scripts/reset-salesforce-setup.py`. Run it with `python3` and its full path.

## Steps

1. **Preview.** Run the script with no arguments. It changes nothing.
   ```bash
   python3 "<this skill's base directory>/scripts/reset-salesforce-setup.py"
   ```
   - If it says the team settings haven't reached this machine, tell the developer to sign in with their claude.ai account (`/login`), restart Claude Code and try again. Stop there.
   - If it finds nothing to remove and no npx skills, tell them their setup already matches the team baseline and stop.
2. **Show the developer what will change:** the plugins to uninstall, the old settings entries, and how many npx skills. Point out any plugin they may still want (a specialist they use daily) and say they can switch it back on afterwards with `claude plugin install <plugin> --scope local` or by asking. Say that everything is backed up first.
3. **Ask for confirmation.** Do not apply without a clear yes.
4. **Apply.**
   ```bash
   python3 "<this skill's base directory>/scripts/reset-salesforce-setup.py" --apply
   ```
5. **Report the result** in a few lines: what was removed, the backup folders from the output, and tell them to **restart Claude Code**.
   - If a step failed, show its output and the backup path. Do not remove anything by other means without asking.

## Undo

The backup folder (`~/.claude/backup-sf-reset-<timestamp>/`) holds the previous `settings.json` and `installed_plugins.json`, and `reinstall-commands.txt` with one install command per removed plugin. The npx backup is restored as described in the `sf-npx-cleanup` skill.
