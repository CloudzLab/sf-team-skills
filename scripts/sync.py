#!/usr/bin/env python3
"""Rebuild the CloudzLab team plugins from forcedotcom/sf-skills.

Every run recomputes the team catalog from scratch:

    team skills = skills in sf-skills/skills/  minus  skills inside any released official plugin

so a skill Salesforce moves into an official plugin drops out of the team catalog
automatically. Each team skill is assigned to a team plugin by the longest matching
name prefix in config/catalog.json.

Outputs (all generated; do not edit by hand):
    plugins/<team-plugin>/            plugin manifest, skills, hooks, LICENSE.txt, NOTICE
    .claude-plugin/marketplace.json   the `cloudzlab` catalog
    managed-settings.json             paste into claude.ai > Admin > Claude Code > Managed settings
    templates/project-settings/*.json per-repo snippets for specialist plugins
    state/index.json                  what the last sync produced (used to diff the next run)
    SYNC_REPORT.md                    human summary; becomes the PR body (not committed)

Usage:
    scripts/sync.py                   clone sf-skills (shallow) and sync
    scripts/sync.py --source PATH     sync from an existing sf-skills checkout
"""

import argparse
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "catalog.json"
STATE = ROOT / "state" / "index.json"
FINDER_TEMPLATE = ROOT / "templates" / "skills" / "sf-plugin-finder.SKILL.md"
DESCRIPTION_LIMIT = 1024  # Agent Skills spec limit for a skill description
RETIRE_AFTER_DAYS = 30
LARGE_CHANGE_RATIO = 0.25  # flag syncs that add or remove more than this share of team skills
IGNORED_FILES = {".DS_Store"}


def load_json(path, default=None):
    if path.exists():
        return json.loads(path.read_text())
    return default


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def skill_dirs(skills_root):
    if not skills_root.is_dir():
        return {}
    return {d.name: d for d in sorted(skills_root.iterdir()) if (d / "SKILL.md").is_file()}


def read_official_plugins(source):
    """Released official plugins = those listed in the upstream marketplace.json."""
    marketplace = load_json(source / ".claude-plugin" / "marketplace.json", {})
    plugins = {}
    for entry in marketplace.get("plugins", []):
        src = entry.get("source")
        if not isinstance(src, str):
            continue
        plugin_dir = (source / src).resolve()
        plugins[entry["name"]] = {
            "description": entry.get("description", ""),
            "skills": sorted(skill_dirs(plugin_dir / "skills")),
        }
    return plugins


def assign_plugin(skill, team_plugins):
    best, best_len = None, -1
    for plugin in team_plugins:
        for prefix in plugin["prefixes"]:
            if skill.startswith(prefix) and len(prefix) > best_len:
                best, best_len = plugin["name"], len(prefix)
    if best:
        return best, False
    fallback = next(p["name"] for p in team_plugins if p.get("fallback"))
    return fallback, True


def tree_hash(path):
    digest = hashlib.sha256()
    for file in sorted(p for p in path.rglob("*") if p.is_file() and p.name not in IGNORED_FILES):
        rel = file.relative_to(path).as_posix()
        if rel == ".claude-plugin/plugin.json":
            continue
        digest.update(rel.encode())
        digest.update(file.read_bytes())
    return digest.hexdigest()


def names(items, limit=25):
    shown = ", ".join(f"`{i}`" for i in items[:limit])
    return shown + (f" and {len(items) - limit} more" if len(items) > limit else "")


def bump_patch(version):
    major, minor, patch = (int(x) for x in version.split("."))
    return f"{major}.{minor}.{patch + 1}"


def build_finder(cfg, team, official, assignments):
    """Generate the sf-plugin-finder skill from the current catalog state."""
    team_catalog = cfg["catalog"]["name"]
    upstream_catalog = cfg["upstream"]["catalog"]

    specialist_team = [p for p in cfg["teamPlugins"] if p["tier"] == "specialist" and team[p["name"]]]
    specialist_official = [n for n in cfg["officialPlugins"]["specialist"] if n in official]

    # Take keywords from each plugin in turn so every plugin gets its most important terms in
    # before the description runs out of room.
    official_keywords = cfg["officialPlugins"].get("specialistKeywords", {})
    keyword_lists = [p["keywords"] for p in specialist_team]
    keyword_lists += [official_keywords.get(n, []) for n in specialist_official]
    keywords, seen = [], set()
    for rank in range(max(map(len, keyword_lists), default=0)):
        for keyword_list in keyword_lists:
            if rank < len(keyword_list) and keyword_list[rank].lower() not in seen:
                seen.add(keyword_list[rank].lower())
                keywords.append(keyword_list[rank])
    head = (
        "Finds which CloudzLab or Salesforce plugin covers a Salesforce product, industry cloud or task "
        "the developer mentions when no enabled skill covers it, and offers to switch that plugin on. "
        "TRIGGER on: "
    )
    tail = ". Also when a named Salesforce skill is missing. NOT when an enabled skill covers it."
    room = DESCRIPTION_LIMIT - len(head) - len(tail)
    listed = []
    for keyword in keywords:
        candidate = ", ".join(listed + [keyword])
        if len(candidate) > room:
            continue  # a shorter keyword later may still fit
        listed.append(keyword)
    description = head + ", ".join(listed) + tail

    rows = ["| Plugin | Covers | Skills | Install |", "|---|---|---|---|"]
    for plugin in specialist_team:
        rows.append(
            f"| `{plugin['name']}` | {plugin['description']} | {len(team[plugin['name']])} "
            f"| `{plugin['name']}@{team_catalog}` |"
        )
    for name in specialist_official:
        desc = official[name]["description"].replace("|", "/")
        rows.append(f"| `{name}` (Salesforce) | {desc} | {len(official[name]['skills'])} | `{name}@{upstream_catalog}` |")

    index_lines = [
        "# Skill index",
        "",
        "Every skill in a specialist plugin, with the plugin that provides it. Search this file for a skill name or keyword.",
        "",
        "| Skill | Plugin | Install |",
        "|---|---|---|",
    ]
    for skill, plugin_name in sorted(assignments.items()):
        if next(p for p in cfg["teamPlugins"] if p["name"] == plugin_name)["tier"] == "specialist":
            index_lines.append(f"| `{skill}` | `{plugin_name}` | `{plugin_name}@{team_catalog}` |")
    for name in specialist_official:
        for skill in official[name]["skills"]:
            index_lines.append(f"| `{skill}` | `{name}` (Salesforce) | `{name}@{upstream_catalog}` |")

    body = FINDER_TEMPLATE.read_text()
    body = body.replace("{{DESCRIPTION}}", json.dumps(description, ensure_ascii=False))
    body = body.replace("{{PLUGIN_TABLE}}", "\n".join(rows))
    body = body.replace("{{TEAM_CATALOG}}", team_catalog)
    body = body.replace("{{UPSTREAM_CATALOG}}", upstream_catalog)
    return body, "\n".join(index_lines) + "\n", description


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", type=Path, help="existing forcedotcom/sf-skills checkout (default: shallow clone)")
    args = parser.parse_args()

    cfg = load_json(CONFIG)
    state = load_json(STATE, {"plugins": {}, "official": {}, "assignments": {}, "retired": {}})
    today = datetime.date.today()

    tmp = None
    source = args.source
    if source is None:
        tmp = tempfile.mkdtemp(prefix="sf-skills-")
        subprocess.run(
            ["git", "clone", "--quiet", "--depth", "1", "--branch", cfg["upstream"]["ref"], cfg["upstream"]["url"], tmp],
            check=True,
        )
        source = Path(tmp)
    source = source.resolve()

    try:
        upstream_sha = git("rev-parse", "HEAD", cwd=source)
        root_skills = skill_dirs(source / "skills")
        official = read_official_plugins(source)
        official_skill_owner = {s: name for name, info in official.items() for s in info["skills"]}

        team_plugin_names = [p["name"] for p in cfg["teamPlugins"]]
        finder_name = cfg["finder"]["skill"]
        owned = cfg.get("ownedSkills", [])
        for own_name in [finder_name] + [o["skill"] for o in owned]:
            if own_name in root_skills or own_name in official_skill_owner:
                sys.exit(f"error: upstream now has a skill named {own_name}; rename ours in config/catalog.json")

        # 1. Work out which skills belong in the team catalog, and where.
        assignments, unmatched = {}, []
        for skill in root_skills:
            if skill in official_skill_owner:
                continue
            plugin_name, fell_back = assign_plugin(skill, cfg["teamPlugins"])
            assignments[skill] = plugin_name
            if fell_back:
                unmatched.append(skill)
        team = {name: sorted(s for s, p in assignments.items() if p == name) for name in team_plugin_names}

        # 2. Regenerate every team plugin directory.
        plugins_dir = ROOT / "plugins"
        if plugins_dir.exists():
            shutil.rmtree(plugins_dir)
        finder_body, finder_index, finder_description = build_finder(cfg, team, official, assignments)

        report_versions, retired_now, retired_removed = [], [], []
        marketplace_plugins, new_state_plugins = [], {}
        for plugin in cfg["teamPlugins"]:
            name = plugin["name"]
            skills = list(team[name])
            is_finder_home = name == cfg["finder"]["plugin"]
            owned_here = [o for o in owned if o["plugin"] == name]
            previous = state["plugins"].get(name)

            if not skills and not is_finder_home and not owned_here:
                retired_since = state["retired"].get(name, today.isoformat())
                age = (today - datetime.date.fromisoformat(retired_since)).days
                if previous is None and name not in state["retired"]:
                    continue  # never shipped; nothing to retire
                if age >= RETIRE_AFTER_DAYS:
                    retired_removed.append(name)
                    state["retired"].pop(name, None)
                    continue
                state["retired"][name] = retired_since
                retired_now.append((name, retired_since))
            else:
                state["retired"].pop(name, None)

            plugin_dir = plugins_dir / name
            (plugin_dir / "skills").mkdir(parents=True)
            for skill in skills:
                shutil.copytree(root_skills[skill], plugin_dir / "skills" / skill,
                                ignore=shutil.ignore_patterns(*IGNORED_FILES))
            if is_finder_home:
                finder_dir = plugin_dir / "skills" / finder_name
                (finder_dir / "references").mkdir(parents=True)
                (finder_dir / "SKILL.md").write_text(finder_body)
                (finder_dir / "references" / "skill-index.md").write_text(finder_index)
            for own in owned_here:
                shutil.copytree(ROOT / own["source"], plugin_dir / "skills" / own["skill"],
                                ignore=shutil.ignore_patterns(*IGNORED_FILES))
            hooks_here = [h for h in cfg.get("ownedHooks", []) if h["plugin"] == name]
            for hooks in hooks_here:
                shutil.copytree(ROOT / hooks["source"], plugin_dir / "hooks",
                                ignore=shutil.ignore_patterns(*IGNORED_FILES))
            shutil.copy(ROOT / "LICENSE.txt", plugin_dir / "LICENSE.txt")
            shutil.copy(ROOT / "NOTICE", plugin_dir / "NOTICE")

            description = plugin["description"]
            if name in state["retired"]:
                description = (f"RETIRED: Salesforce now ships these skills in official plugins. "
                               f"Uninstall this plugin; it will be removed from the catalog.")
                readme = plugin_dir / "README.md"
                readme.write_text(f"# {name} (retired)\n\n{description}\n")

            content_hash = tree_hash(plugin_dir)
            if previous is None:
                version = "1.0.0"
            elif previous["hash"] != content_hash:
                version = bump_patch(previous["version"])
            else:
                version = previous["version"]
            if previous is None or previous["version"] != version:
                report_versions.append((name, previous["version"] if previous else None, version))

            write_json(plugin_dir / ".claude-plugin" / "plugin.json", {
                "name": name,
                "version": version,
                "description": description,
                "author": {"name": cfg["catalog"]["owner"]},
                "license": "Apache-2.0",
                "homepage": f"https://github.com/{cfg['catalog']['repo']}",
                "repository": f"https://github.com/{cfg['catalog']['repo']}.git",
                "keywords": ["salesforce"] + [k.lower() for k in plugin["keywords"][:6]],
            })
            marketplace_plugins.append({
                "name": name,
                "source": f"./plugins/{name}",
                "description": description,
                "version": version,
                "category": "salesforce",
                "keywords": ["salesforce"] + [k.lower() for k in plugin["keywords"][:6]],
            })
            new_state_plugins[name] = {"version": version, "hash": content_hash, "skills": skills}

        # 3. Catalog, managed settings and per-repo templates.
        write_json(ROOT / ".claude-plugin" / "marketplace.json", {
            "name": cfg["catalog"]["name"],
            "owner": {"name": cfg["catalog"]["owner"]},
            "metadata": {"description": cfg["catalog"]["description"]},
            "plugins": marketplace_plugins,
        })

        team_catalog, upstream_catalog = cfg["catalog"]["name"], cfg["upstream"]["catalog"]
        marketplaces = {
            upstream_catalog: {"source": {"source": "github", "repo": cfg["upstream"]["repo"]}, "autoUpdate": True},
            team_catalog: {"source": {"source": "github", "repo": cfg["catalog"]["repo"]}, "autoUpdate": True},
        }
        enabled = {f"{n}@{upstream_catalog}": True for n in cfg["officialPlugins"]["core"] if n in official}
        enabled.update({f"{p['name']}@{team_catalog}": True for p in cfg["teamPlugins"]
                        if p["tier"] == "core" and p["name"] in new_state_plugins})
        managed_path = ROOT / "managed-settings.json"
        old_managed = managed_path.read_text() if managed_path.exists() else None
        write_json(managed_path, {"extraKnownMarketplaces": marketplaces, "enabledPlugins": enabled})
        managed_changed = old_managed != managed_path.read_text()

        templates_dir = ROOT / "templates" / "project-settings"
        if templates_dir.exists():
            shutil.rmtree(templates_dir)
        specialists = [(p["name"], team_catalog) for p in cfg["teamPlugins"]
                       if p["tier"] == "specialist" and p["name"] in new_state_plugins and p["name"] not in state["retired"]]
        specialists += [(n, upstream_catalog) for n in cfg["officialPlugins"]["specialist"] if n in official]
        for name, catalog in specialists:
            # Key order matches what `claude plugin install --scope project` writes back, so running it leaves the file unchanged.
            write_json(templates_dir / f"{name}.json", {
                "enabledPlugins": {f"{name}@{catalog}": True},
                "extraKnownMarketplaces": {catalog: marketplaces[catalog]},
            })

        # 4. Diff against the previous run.
        prev_assign = state.get("assignments", {})
        moved_to_official = sorted((s, prev_assign[s], official_skill_owner[s])
                                   for s in prev_assign if s not in assignments and s in official_skill_owner)
        vanished = sorted((s, prev_assign[s]) for s in prev_assign
                          if s not in assignments and s not in official_skill_owner)
        added = sorted((s, p) for s, p in assignments.items() if s not in prev_assign)
        regrouped = sorted((s, prev_assign[s], p) for s, p in assignments.items()
                           if s in prev_assign and prev_assign[s] != p)
        configured = set(cfg["officialPlugins"]["core"]) | set(cfg["officialPlugins"]["specialist"])
        unclassified_official = sorted(n for n in official if n not in configured)
        missing_official = sorted(n for n in configured if n not in official)
        new_official = sorted(n for n in official if state.get("official") and n not in state["official"])

        state.update({
            "upstreamSha": upstream_sha,
            "plugins": new_state_plugins,
            "assignments": assignments,
            "official": {n: info["skills"] for n, info in official.items()},
        })
        write_json(STATE, state)

        # 5. Report.
        first_run = not prev_assign
        lines = [f"# Salesforce skills sync: {today.isoformat()}", "",
                 f"Upstream: `{cfg['upstream']['repo']}` @ `{upstream_sha[:12]}`", "",
                 f"- Upstream skills: {len(root_skills)}",
                 f"- In official Salesforce plugins: {len(official_skill_owner)} across {len(official)} plugins",
                 f"- In team plugins: {len(assignments)} across {sum(1 for n in new_state_plugins if new_state_plugins[n]['skills'])} plugins",
                 ""]

        actions = []
        prev_count, new_count = len(prev_assign), len(assignments)
        if prev_count and abs(new_count - prev_count) > max(10, prev_count * LARGE_CHANGE_RATIO):
            actions.append(f"**Large change: team skills went from {prev_count} to {new_count}.** Upstream sometimes "
                           "publishes and then reverts big releases. Check the recent history of "
                           f"`{cfg['upstream']['repo']}` before merging; if it looks like a mistake, close this PR.")
        if new_official:
            actions.append("**Salesforce released new official plugin(s):** " + ", ".join(f"`{n}`" for n in new_official))
        if unclassified_official:
            actions.append("**Classify official plugin(s) as core or specialist** in `config/catalog.json`, then re-run: "
                           + ", ".join(f"`{n}`" for n in unclassified_official))
        if missing_official:
            actions.append("**Official plugin(s) in config no longer exist upstream** (renamed or removed?): "
                           + ", ".join(f"`{n}`" for n in missing_official))
        if moved_to_official:
            owners = sorted({o for _, _, o in moved_to_official})
            not_core = [o for o in owners if o not in cfg["officialPlugins"]["core"]]
            if not_core:
                actions.append("Skills moved into official plugin(s) that are not core: "
                               + ", ".join(f"`{o}`" for o in not_core)
                               + ". If the team relied on them by default, add them to `officialPlugins.core`.")
        if managed_changed and not first_run:
            actions.append("**`managed-settings.json` changed.** After merging, paste it into claude.ai → Admin settings → Claude Code → Managed settings.")
        if unmatched:
            actions.append("**Skills with no matching prefix** were put in the fallback plugin; add a prefix in `config/catalog.json` if they belong elsewhere: "
                           + names(unmatched))
        if vanished:
            actions.append("**Skills gone from upstream** (renamed or deleted). Check whether a renamed copy is listed under Added: "
                           + names([s for s, _ in vanished]))
        if retired_now:
            actions.append("**Retired plugin(s)** (now empty; removed from the catalog after "
                           f"{RETIRE_AFTER_DAYS} days). Remove them from any repo `.claude/settings.json`: "
                           + ", ".join(f"`{n}` (since {d})" for n, d in retired_now))
        lines += ["## Needs a human", ""] + ([f"- {a}" for a in actions] or ["- Nothing. Merge when the checks pass."]) + [""]

        if moved_to_official:
            lines += ["## Moved into official Salesforce plugins", "", "| Skill | Was in | Now in |", "|---|---|---|"]
            lines += [f"| `{s}` | `{a}` | `{b}@{upstream_catalog}` |" for s, a, b in moved_to_official] + [""]
        if added and not first_run:
            lines += ["## Added", "", "| Skill | Plugin |", "|---|---|"]
            lines += [f"| `{s}` | `{p}` |" for s, p in added] + [""]
        if regrouped:
            lines += ["## Moved between team plugins", "", "| Skill | From | To |", "|---|---|---|"]
            lines += [f"| `{s}` | `{a}` | `{b}` |" for s, a, b in regrouped] + [""]
        if retired_removed:
            lines += ["## Removed from the catalog", ""] + [f"- `{n}` (retired {RETIRE_AFTER_DAYS}+ days ago)" for n in retired_removed] + [""]
        if report_versions:
            lines += ["## Plugin versions", "", "| Plugin | Skills | Version |", "|---|---|---|"]
            lines += [f"| `{n}` | {len(new_state_plugins[n]['skills'])} | {old + ' → ' if old else ''}{new} |"
                      for n, old, new in report_versions] + [""]
        lines += ["## Finder", "", f"`{finder_name}` description ({len(finder_description)}/{DESCRIPTION_LIMIT} chars):", "",
                  f"> {finder_description}", ""]
        (ROOT / "SYNC_REPORT.md").write_text("\n".join(lines))
        print("\n".join(lines))
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
