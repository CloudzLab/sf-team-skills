---
name: sf-npx-cleanup
description: "Removes old copies of Salesforce skills installed with `npx skills add forcedotcom/sf-skills`, so only the team's plugin versions load. TRIGGER when the user asks to clean up, remove or fix old, duplicate or npx-installed Salesforce skills, or when the same Salesforce skill appears both with and without a plugin prefix (e.g. `agentforce-generate` and `agentforce-adlc:agentforce-generate`). DO NOT TRIGGER for removing plugins (use /plugin) or for non-Salesforce skills."
---

# Clean up old npx Salesforce skills

Developers who once ran `npx skills add forcedotcom/sf-skills` have loose copies of Salesforce skills in `~/.agents/skills`, linked into `~/.claude/skills`. They never update, and they sit next to the plugin versions, so Claude can pick an outdated copy. This skill removes them after backing them up. It only touches skills that `npx skills` recorded as coming from `forcedotcom/sf-skills`; other npx skills are left alone.

The script is in this skill's base directory at `scripts/cleanup-npx-salesforce-skills.sh`. Run it with `bash` and its full path.

## Steps

1. **Preview.** Run the script with no arguments. It changes nothing and lists what it found.
   ```bash
   bash "<this skill's base directory>/scripts/cleanup-npx-salesforce-skills.sh"
   ```
   - If it reports nothing to clean up, tell the developer their machine is already clean and stop.
2. **Show the developer what will be removed:** how many skills, and a short sample of names. Say that everything is backed up first to `~/.agents/backup-sf-skills-<timestamp>/`, and that the same skills are provided by the team's plugins.
3. **Ask for confirmation.** Do not apply without a clear yes.
4. **Apply.**
   ```bash
   bash "<this skill's base directory>/scripts/cleanup-npx-salesforce-skills.sh" --apply
   ```
   It needs `npx` (Node.js), which is present on any machine where these skills were installed with npx.
5. **Report the result** in one or two lines, including the backup folder from the output, and tell them to **restart Claude Code** so the removed skills stop loading.
   - If the script says some skills were not removed, show those names and the backup path; do not delete anything by other means without asking.

## Undo

To restore a skill, copy it from the backup's `skills/` folder back into `~/.agents/skills/`, and its link from the backup's `links/` folder into `~/.claude/skills/`.
