# CloudzLab Salesforce skills for Claude Code

One setup for every CloudzLab developer, on every machine and in every Salesforce project.

- **Salesforce's official plugins** (catalog `salesforce`) provide the core skills.
- **This repo** (catalog `cloudzlab`) packages the Salesforce skills that Salesforce publishes in [forcedotcom/sf-skills](https://github.com/forcedotcom/sf-skills) but doesn't ship in any official plugin. It groups them into team plugins and keeps them in sync automatically.
- **The claude.ai admin console** switches the core plugins on for everyone. Specialist plugins stay off until a project or developer needs them.

## How it works

There are two levels.

| Level | Who switches it on | Where it's active |
|---|---|---|
| **Core** | The org admin, once, in claude.ai managed settings | Every session, every project, every developer |
| **Specialist** | A repo's `.claude/settings.json`, or the developer with `/plugin` | Only where it was switched on |

A plugin is downloaded once per machine. Being *enabled* is what decides whether it loads. A specialist plugin that's installed but not enabled in the current project costs nothing.

### Core plugins (on for everyone)

| Plugin | Catalog | What it does |
|---|---|---|
| `salesforce-development` | salesforce | Projects, orgs, Apex and tests, SOQL, metadata, Flows, permissions, deploy and retrieve |
| `agentforce-adlc` | salesforce | Build, test, deploy and monitor Agentforce agents |
| `salesforce-code-quality` | salesforce | Code Analyzer scans and Well-Architected reviews |
| `dx-org-lifecycle` | salesforce | Dev Hubs, scratch orgs, sandboxes, trial orgs |
| `dx-devops` | salesforce | DevOps Center pipelines, work items, conflicts, test suites |
| `integration` | salesforce | Named Credentials, External Services, callouts, CDC, events |
| `platform-observability` | salesforce | Platform and Agentforce tracing |
| `platform-trust-security` | salesforce | Shield Platform Encryption, Salesforce Archive |
| `platform-lightning-widgets` | salesforce | Lightning Types and Agentforce action widgets |
| `experience-lwc` | salesforce | Lightning Web Components |
| `experience-react` | salesforce | React UI bundle apps on Salesforce |
| `experience-cms` | salesforce | Salesforce CMS content for Experience Cloud |
| `service-engagement` | salesforce | Messaging, web chat, WhatsApp, Email-to-Case, agent-to-human handoff |
| `service-omni` | salesforce | Omni-Channel routing |
| `sf-platform-extras` | cloudzlab | Docs lookup, ApexGuru, SLDS, org shapes and snapshots, data masking, Models API, plus **`sf-plugin-finder`** |

### Specialist plugins (off until needed)

| Plugin | Catalog | What it does |
|---|---|---|
| `sf-experience-extras` | cloudzlab | Experience Cloud site setup: LWR sites, portals, domains, menus |
| `sf-data360` | cloudzlab | Data 360 / Data Cloud |
| `sf-field-service` | cloudzlab | Field Service scheduling, work plans, data capture forms |
| `sf-omnistudio` | cloudzlab | OmniScripts, FlexCards, Integration Procedures, DataMappers |
| `sf-commerce` | cloudzlab | Commerce store setup and fulfilment |
| `sf-service-itsm` | cloudzlab | IT Service Management and other Service Cloud setup |
| `sf-consumer-goods` | cloudzlab | Consumer Goods Cloud |
| `sf-crm-analytics` | cloudzlab | CRM Analytics and Tableau Next |
| `sf-industries-misc` | cloudzlab | Communications, Nonprofit, Life Sciences, Insurance, Sales, Marketing |
| `commerce-b2b` | salesforce | B2B Commerce storefront components |
| `mobile-development` | salesforce | Native iOS/Android apps with the Mobile SDK |
| `dx-isv-partner` | salesforce | ISV and partner operations |
| `education-cloud` | salesforce | Education Cloud |
| `salesforce-test-drive` | salesforce | Guided demo builds |

Some team plugins are defined in `config/catalog.json` but not currently built, because Salesforce doesn't publish their skills right now: `sf-fsc`, `sf-health-cloud`, `sf-industries` and `sf-automotive`. They appear automatically if Salesforce publishes those skills. Each sync's PR lists the current skill counts.

## For developers

1. **Sign in to Claude Code with your CloudzLab claude.ai account** (`/login`). Managed settings don't reach sessions that use an API key.
2. **Remove old `npx` copies of Salesforce skills** (one time). They can override the plugin versions:
   ```bash
   scripts/cleanup-npx-salesforce-skills.sh           # shows what it would remove
   scripts/cleanup-npx-salesforce-skills.sh --apply   # backs up, then removes
   ```
3. **Restart Claude Code.** The core plugins install themselves.

When you need a specialist area, just ask. `sf-plugin-finder` recognises the product (e.g. "set up an OmniScript") and offers to switch on the right plugin. You can also run `/plugin` and browse the `cloudzlab` and `salesforce` catalogs. When switching one on, choose:

| Scope | Command flag | Effect |
|---|---|---|
| Just me, this project | `--scope local` | Nothing committed |
| Everyone in this project | `--scope project` | Writes `.claude/settings.json`; commit it |
| Me, everywhere | `--scope user` | On in all your projects |

Restart Claude Code after switching a plugin on.

## For repo owners: switch a specialist plugin on for a whole project

Copy the matching file from `templates/project-settings/` into the project's `.claude/settings.json`, or merge it into an existing one, and commit it:

```json
{
  "extraKnownMarketplaces": {
    "cloudzlab": { "source": { "source": "github", "repo": "CloudzLab/sf-team-skills" }, "autoUpdate": true }
  },
  "enabledPlugins": { "sf-omnistudio@cloudzlab": true }
}
```

Everyone who opens that repo then gets the plugin, only in that repo. Claude Code may ask them once to trust the folder and install its plugins.

## For the org admin

1. In claude.ai, go to **Organization settings → Claude Code → Managed settings** (Owner or Primary Owner role).
2. Paste the contents of [`managed-settings.json`](managed-settings.json) and save.
3. Clients pick it up at startup and refresh hourly.

When a sync PR says `managed-settings.json` changed, merge it and paste the file again.

**Repo access.** Claude Code downloads the `cloudzlab` catalog with each developer's own git credentials. If this repo is private, every developer needs read access to it and a working GitHub login (`gh auth login` or SSH). If it's public, nothing is needed. The content is Apache-2.0 skills from Salesforce plus generated manifests.

## For the catalog maintainer

`.github/workflows/sync.yml` runs every weekday:

1. Clones `forcedotcom/sf-skills`.
2. Computes the **team skills**: skills in the repo *minus* skills inside any released official Salesforce plugin.
3. Assigns each team skill to a team plugin by the longest matching name prefix in `config/catalog.json`.
4. Regenerates `plugins/`, the catalog, `managed-settings.json` and the per-project templates. A plugin's patch version goes up only when its content changed.
5. Validates everything with `claude plugin validate --strict`.
6. Opens a PR whose description lists what changed and anything that needs a person.

The PR's **Needs a human** section flags:

| Flag | What to do |
|---|---|
| **Large change** (more than 25% of team skills added or removed) | Salesforce has published and then reverted big releases on the same day, e.g. 15 Oct 2026. Check upstream history before merging. |
| **New official plugin** / **classify official plugin** | Add it to `officialPlugins.core` or `.specialist` in `config/catalog.json` and re-run. Core plugins also need the admin to re-paste managed settings. |
| **Moved into official plugins** | Nothing. The team copy is dropped automatically. If the new official plugin should be core, add it to core. |
| **Skills gone from upstream** | Renamed or deleted. Look for a renamed copy under *Added*. |
| **Skills with no matching prefix** | Add a prefix in `config/catalog.json` if the fallback plugin is the wrong home. |
| **Retired plugin** | Its skills all moved to official plugins. It stays in the catalog for 30 days marked RETIRED, then is removed. Remove it from any repo settings. |
| **`managed-settings.json` changed** | After merging, the admin re-pastes it. |

Running it locally:

```bash
python3 scripts/sync.py                         # clones sf-skills
python3 scripts/sync.py --source ../sf-skills   # or uses an existing checkout
scripts/validate.sh                             # needs the claude CLI
```

To change the grouping, edit `config/catalog.json` (plugins, prefixes, descriptions, finder keywords) and re-run the sync. Don't edit `plugins/`, `.claude-plugin/`, `managed-settings.json` or `templates/project-settings/` by hand; they are regenerated. The finder's instructions live in `templates/sf-plugin-finder.SKILL.md`.

**One-time GitHub setup.** Enable *Settings → Actions → General → Allow GitHub Actions to create and approve pull requests* so the sync can open PRs.

## Cost per session

Each enabled plugin adds its skill descriptions to every session. These figures are from `claude plugin details` on 15 Oct 2026:

| Plugin | Always-on tokens |
|---|---|
| `salesforce-development` | ~8,100 |
| `sf-service-itsm` | ~7,300 |
| `experience-lwc` | ~4,300 |
| `service-engagement` | ~4,000 |
| `sf-platform-extras` | ~3,900 |
| `sf-industries-misc` | ~2,900 |
| `agentforce-adlc` | ~2,500 |
| `sf-field-service` | ~2,000 |
| `sf-omnistudio` | ~1,400 |
| `sf-experience-extras` | ~1,200 |
| `sf-consumer-goods` | ~1,100 |
| `sf-crm-analytics`, `sf-data360`, `sf-commerce` | under 600 each |

Run `claude plugin details <plugin>` for current numbers.

## Licence

The skills under `plugins/` (except `sf-plugin-finder`) are copied unmodified from forcedotcom/sf-skills, © Salesforce, Inc., Apache-2.0. See [LICENSE.txt](LICENSE.txt) and [NOTICE](NOTICE).
