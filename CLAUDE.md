# CLAUDE.md

CloudzLab's Claude Code plugin catalog (`cloudzlab`) for Salesforce work. It packages the skills in [forcedotcom/sf-skills](https://github.com/forcedotcom/sf-skills) that Salesforce does **not** ship in an official plugin, and holds the managed settings that switch the team's core plugins on org-wide. Public repo: https://github.com/CloudzLab/sf-team-skills. README.md is the team-facing documentation; a matching team guide page lives at https://claude.ai/artifact/KRT5bYiZz94aU8XMMDLG2p (shared with the org; republish it when the README's developer/admin content changes).

## Model

Two levels, decided with the user on 2026-10-15:

- **Core**: on for everyone via claude.ai server-managed settings (`managed-settings.json`). 14 official `@salesforce` plugins + `sf-platform-extras@cloudzlab`.
- **Specialist**: everything else. Enabled per repo (`.claude/settings.json`, templates in `templates/project-settings/`) or by the developer via `/plugin`, guided by the `sf-plugin-finder` skill.

Team skills are always recomputed as *skills in sf-skills/skills/ minus skills inside any released official plugin* (released = listed in upstream `.claude-plugin/marketplace.json`), then grouped by longest name prefix. Skills Salesforce moves into an official plugin drop out automatically.

## Layout

| Path | Edit? | Purpose |
|---|---|---|
| `config/catalog.json` | **Yes** | Source of truth: team plugins, prefixes, tiers, descriptions, finder keywords, official core/specialist lists, `ownedSkills` |
| `templates/skills/` | **Yes** | Team-written skills: `sf-plugin-finder.SKILL.md` (sync fills in `{{PLUGIN_TABLE}}` etc.) and `sf-npx-cleanup/` (copied verbatim) |
| `templates/hooks/sf-platform-extras/` | **Yes** | Team-written SessionStart hook (`ownedHooks`): notices plugins a repo's settings enable that aren't installed, and gives the install command |
| `scripts/sync.py` | Yes | Regenerates everything below and writes `SYNC_REPORT.md` (PR body, gitignored) |
| `scripts/validate.sh` | Yes | `claude plugin validate --strict` on catalog + every plugin, JSON checks |
| `plugins/`, `.claude-plugin/marketplace.json`, `managed-settings.json`, `templates/project-settings/`, `state/index.json` | **No, generated** | Re-run the sync instead |
| `.github/workflows/sync.yml` | Yes | Weekdays 05:00 UTC: sync, and if catalog files changed, validate and open/update PR `sync/salesforce-skills` |
| `.github/workflows/validate.yml` | Yes | Every PR and push to main |

## Working here

```bash
python3 scripts/sync.py                          # clones sf-skills (shallow)
python3 scripts/sync.py --source <sf-skills>     # use an existing checkout
scripts/validate.sh                              # needs the claude CLI
```

- After editing `config/` or `templates/`, re-run the sync and commit the regenerated files with it. CI warns if generated files differ from a fresh sync.
- Plugin versions are content-hashed: a plugin's patch version bumps only when its files change. Anything copied into every plugin (`NOTICE`, `LICENSE.txt`) bumps all of them.
- Our skill names must not collide with upstream; the sync exits with an error if they do.
- Test installs in a throwaway config so the real one is untouched: `CLAUDE_CONFIG_DIR=<scratch dir> claude plugin marketplace add <repo path>`, then `claude plugin install … / details …`. `claude plugin details` reports each plugin's always-on token cost.
- Skill descriptions are capped at 1024 chars; the finder's keyword list is built round-robin across plugins to fit.
- Licence: skills are Apache-2.0 from Salesforce. Keep `LICENSE.txt` and `NOTICE` in every plugin; update `NOTICE` and the README licence line when adding team-written skills.

## Git

- Never commit to `main` directly: short-lived branch (`feat/…`, `fix/…`, `docs/…`, `chore/…`) → PR → validation passes → merge commit.
- Ask the user before each commit/push unless they asked for that change to be shipped.

## Known Claude Code behaviour (tested 2026-10-18 in a sandbox config)

- Settings-file `extraKnownMarketplaces` + `enabledPlugins` at **user/managed** level: catalogs are added and plugins installed silently at session start, no prompt.
- The same in a **repo's** `.claude/settings.json`: only the trust-folder prompt. The plugin is downloaded but never registered, so its skills don't load until the developer runs `claude plugin install <p> --scope project` once. The `sf-platform-extras` SessionStart hook tells them.
- `claude plugin install --scope project` rewrites the repo settings file with `enabledPlugins` before `extraKnownMarketplaces`; the templates use that order so the file stays byte-identical.
- Starting Claude Code in `~` makes `~/.claude/settings.json` count as project settings too; don't run pilots from the home folder.

## Known upstream behaviour

- forcedotcom/sf-skills is volatile: on 2026-10-15 it released 863 skills ("headless360Mcp-only") and reverted the same day (root skills 554 → 251). The sync flags any change of more than 25% of team skills as **Large change**; check upstream history before merging such a PR.
- `sf-fsc`, `sf-health-cloud`, `sf-industries` and `sf-automotive` are configured but currently empty upstream, so they aren't built. They appear automatically if Salesforce publishes those skills.

## Status (2026-10-18)

Done: catalog built and pushed (10 team plugins, 101 skills + 2 team skills), repo public, Actions allowed to open PRs, actions on Node 24 versions (PR #1), `sf-npx-cleanup` skill (PR #2), rollout docs (PR #3). Validation and a manual sync run pass on GitHub. Sandbox pilot (2026-10-18): core install, finder and cleanup triggering verified; repo settings found not to install plugins, so the missing-plugin hook was added.

Next:
1. Org Owner pastes `managed-settings.json` into claude.ai → Organization settings → Claude Code → Managed settings.
2. Pilot on the admin's real machine (first remove their user-scope specialists: commerce-b2b, mobile-development, dx-isv-partner, salesforce-test-drive): 15 core plugins appear via claude.ai delivery; self-added catalogs still work; the missing-plugin notice shows in a repo with a project settings file. Update the team guide page's per-repo wording to match the README.
3. Announce to the team (restart, then cleanup) and add per-project settings files to specialist repos.
4. Watch the first automatic sync PR: the `create-pull-request@v8` step hasn't run yet.

Not yet verified live: managed settings delivered from claude.ai (sandbox used a local settings file), the hook's notice as displayed in the interactive UI (verified headless only).
