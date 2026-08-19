#!/usr/bin/env python3
"""Preflight: find MODIFIED bugs needing backports and dry-run cherry-pick.

Queries Jira for OCPBUGS bugs that:
  - status = MODIFIED (fix merged on master)
  - have Target Backport Versions set
  - component = Management Console
  - assigned to RH konflux Platform Experience services

Uses repo: labels on the bug to determine which repo (console or console-operator).

For each bug, finds the merged PR, determines which versions still need
backporting, and dry-runs cherry-pick to classify as CLEAN or CONFLICTS.

Outputs "start" with structured prompt data if actionable work is found.
"""

import json
import os
import re
import subprocess
import sys
import tempfile

from common import (
    get_capacity,
    get_tasks,
    load_project_repos,
    output_result,
    upstream_repo,
)
from jira_mcp import jira_call, jira_cleanup

# --- Configuration ---

JIRA_COMPONENT = "Management Console"
JIRA_ASSIGNEE = "RH konflux Platform Experience services"

REPO_LABEL_MAP = {
    "repo:console": "console",
    "repo:console-operator": "console-operator",
}

BACKPORT_TASK_PREFIX = "backport:"

DEFAULT_BRANCHES = {
    "console": "main",
    "console-operator": "main",
}

TARGET_BACKPORT_VERSIONS_FIELD = "customfield_10878"

BOT_LABEL = os.environ.get("BOT_LABEL", "rehor-ai-pixaa")


def pod_log(msg):
    """Write directly to pod log, bypassing subprocess capture."""
    try:
        with open("/proc/1/fd/2", "w") as f:
            f.write(f"[backport-preflight] {msg}\n")
    except OSError:
        pass


# --- Version helpers ---

def normalize_version(version_str):
    """Normalize version string to release branch name.

    4.22.z / 4.22 / 4.22.0 -> release-4.22
    5.0.z / 5.0 / 5.0.0 -> release-5.0
    """
    v = version_str.strip()
    # Strip only the third segment (.z, .x, .0) if present: 4.22.z -> 4.22, 5.0.0 -> 5.0
    v = re.sub(r"(\d+\.\d+)\.[zx0]$", r"\1", v)
    if not v.startswith("release-"):
        v = "release-" + v
    return v


def version_sort_key(branch_name):
    """Sort key for release branches, newest first.

    release-5.0 > release-4.22 > release-4.21
    """
    m = re.match(r"release-(\d+)\.(\d+)", branch_name)
    if not m:
        return (0, 0)
    return (int(m.group(1)), int(m.group(2)))


# --- GitHub helpers ---

def gh_json(args, timeout=30):
    """Run gh CLI command and parse JSON output."""
    try:
        proc = subprocess.run(
            ["gh"] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if proc.returncode != 0:
            print(
                f"  gh {' '.join(args[:3])}... failed: {proc.stderr[:200]}",
                file=sys.stderr,
            )
            return None
        return json.loads(proc.stdout) if proc.stdout.strip() else None
    except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
        print(f"  gh error: {e}", file=sys.stderr)
        return None


def find_merged_pr(repo, bug_key):
    """Find the merged PR for a bug by searching PR titles."""
    prs = gh_json([
        "pr", "list", "--repo", repo,
        "--state", "merged", "--search", bug_key,
        "--json", "number,url,title",
        "--limit", "5",
    ])
    if not prs:
        return None
    for pr in prs:
        title = pr.get("title", "")
        if title.startswith(bug_key + ":") or title.startswith(bug_key + " "):
            return pr
    return None


def get_pr_commits(repo, pr_number):
    """Get all commit SHAs from a PR, in order."""
    data = gh_json([
        "pr", "view", str(pr_number), "--repo", repo,
        "--json", "commits",
    ])
    if not data or "commits" not in data:
        return []
    return [c["oid"] for c in data["commits"]]


def find_existing_backport_pr(repo, bug_key, release_branch):
    """Check if a backport PR already exists for this bug+branch."""
    prs = gh_json([
        "pr", "list", "--repo", repo,
        "--base", release_branch,
        "--search", bug_key,
        "--state", "all",
        "--json", "number,url,title,state",
        "--limit", "5",
    ])
    if not prs:
        return None
    for pr in prs:
        if bug_key in pr.get("title", ""):
            return pr
    return None


def check_branch_exists(repo, branch):
    """Check if a branch exists on the upstream repo."""
    proc = subprocess.run(
        ["gh", "api", f"repos/{repo}/branches/{branch}", "--jq", ".name"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    return proc.returncode == 0


# --- Cherry-pick dry-run ---

def dry_run_cherry_pick(upstream, release_branch, source_branch, commit_shas):
    """Dry-run cherry-pick commits onto release branch in a temp clone.

    Returns dict with:
        result: "clean" | "conflicts" | "error"
        conflicting_files: list of file paths (if conflicts)
        error: error message (if error)
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = os.path.join(tmpdir, "repo")
        try:
            subprocess.run(
                [
                    "git", "clone", "--no-checkout", "--filter=blob:none",
                    f"https://github.com/{upstream}.git", repo_dir,
                ],
                capture_output=True, text=True, timeout=120, check=True,
            )
            subprocess.run(
                ["git", "-C", repo_dir, "fetch", "origin", release_branch],
                capture_output=True, text=True, timeout=60, check=True,
            )
            subprocess.run(
                ["git", "-C", repo_dir, "fetch", "origin", source_branch],
                capture_output=True, text=True, timeout=60, check=True,
            )
            subprocess.run(
                ["git", "-C", repo_dir, "checkout", f"origin/{release_branch}"],
                capture_output=True, text=True, timeout=30, check=True,
            )
            subprocess.run(
                ["git", "-C", repo_dir, "config", "user.email", "bot@test.com"],
                capture_output=True, text=True, check=True,
            )
            subprocess.run(
                ["git", "-C", repo_dir, "config", "user.name", "bot"],
                capture_output=True, text=True, check=True,
            )

            result = subprocess.run(
                ["git", "-C", repo_dir, "cherry-pick", "--no-commit"] + commit_shas,
                capture_output=True, text=True, timeout=60,
            )

            if result.returncode == 0:
                subprocess.run(
                    ["git", "-C", repo_dir, "reset", "--hard"],
                    capture_output=True, text=True,
                )
                return {"result": "clean", "conflicting_files": []}

            diff_result = subprocess.run(
                ["git", "-C", repo_dir, "diff", "--name-only", "--diff-filter=U"],
                capture_output=True, text=True, timeout=10,
            )
            conflicting = (
                diff_result.stdout.strip().split("\n")
                if diff_result.stdout.strip()
                else []
            )
            subprocess.run(
                ["git", "-C", repo_dir, "cherry-pick", "--abort"],
                capture_output=True, text=True,
            )
            return {"result": "conflicts", "conflicting_files": conflicting}

        except subprocess.CalledProcessError as e:
            msg = e.stderr[:200] if e.stderr else str(e)
            print(f"  git error during dry-run: {msg}", file=sys.stderr)
            return {"result": "error", "conflicting_files": [], "error": msg}
        except subprocess.TimeoutExpired:
            return {
                "result": "error",
                "conflicting_files": [],
                "error": "timeout",
            }


# --- Jira helpers ---

def search_modified_bugs():
    """Search for bugs with merged fixes that need backporting."""
    data = jira_call(
        "jira_search",
        {
            "jql": (
                f'project = OCPBUGS AND status IN (MODIFIED, "Release Pending") '
                f'AND component = "{JIRA_COMPONENT}" '
                f'AND assignee = "{JIRA_ASSIGNEE}" '
                f'AND "Target Backport Versions" IS NOT EMPTY '
                f'ORDER BY priority DESC, updated DESC'
            ),
            "limit": 20,
            "fields": f"summary,status,labels,components,assignee,{TARGET_BACKPORT_VERSIONS_FIELD}",
        },
    )
    if not data:
        return []
    if isinstance(data, list):
        return data
    return data.get("issues", data.get("results", []))


def get_backport_versions(issue):
    """Extract Target Backport Versions from issue fields."""
    fields = issue.get("fields", issue)
    versions_raw = fields.get(TARGET_BACKPORT_VERSIONS_FIELD, [])
    if not versions_raw:
        return []
    # MCP returns {"value": [...]} wrapper — unwrap it
    if isinstance(versions_raw, dict):
        versions_raw = versions_raw.get("value", [])
    if not versions_raw:
        return []
    versions = []
    for v in versions_raw:
        if isinstance(v, dict):
            versions.append(v.get("name", ""))
        elif isinstance(v, str):
            versions.append(v)
    return [v for v in versions if v]


def get_repo_from_labels(issue):
    """Determine repo from issue's repo: labels."""
    fields = issue.get("fields", issue)
    labels = fields.get("labels", [])
    for label in labels:
        label_str = label if isinstance(label, str) else label.get("name", "")
        if label_str in REPO_LABEL_MAP:
            return REPO_LABEL_MAP[label_str]
    return None


# --- Main logic ---

def process_bug(bug, repos, tasks):
    """Process a single bug and return (actionable_item, skip_reason).

    Returns (dict, None) if actionable, or (None, "reason string") if skipped.
    """
    bug_key = bug.get("key", "")
    fields = bug.get("fields", bug)
    summary = fields.get("summary", bug.get("summary", ""))

    raw_labels = fields.get("labels", [])
    bug_labels = [
        (l if isinstance(l, str) else l.get("name", "")) for l in raw_labels
    ]

    components = fields.get("components", [])
    bug_component = ""
    if components:
        bug_component = (
            components[0].get("name", "")
            if isinstance(components[0], dict)
            else str(components[0])
        )

    repo_name = get_repo_from_labels(bug)
    if not repo_name:
        return None, "no_repo_label"

    repo_cfg = repos.get(repo_name)
    if not repo_cfg:
        return None, f"repo_{repo_name}_not_in_config"

    up, host = upstream_repo(repo_name)
    if not up or host != "github":
        return None, "non_github_repo"

    versions = get_backport_versions(bug)
    if not versions:
        return None, "no_backport_versions"

    pr = find_merged_pr(up, bug_key)
    if not pr:
        return None, "no_merged_pr"

    pr_number = pr["number"]
    pr_url = pr["url"]
    commit_shas = get_pr_commits(up, pr_number)
    if not commit_shas:
        return None, "no_commits_in_pr"

    version_branches = []
    for v in versions:
        branch = normalize_version(v)
        version_branches.append({"version": v, "branch": branch})
    version_branches.sort(key=lambda x: version_sort_key(x["branch"]), reverse=True)

    default_branch = DEFAULT_BRANCHES.get(repo_name, "main")

    all_versions = []
    next_actionable = None
    prev_completed_branch = None

    for vb in version_branches:
        version = vb["version"]
        branch = vb["branch"]
        status_info = {"version": version, "branch": branch, "status": "unknown"}

        if not check_branch_exists(up, branch):
            status_info["status"] = "branch_missing"
            all_versions.append(status_info)
            continue

        existing_pr = find_existing_backport_pr(up, bug_key, branch)
        if existing_pr:
            pr_state = existing_pr.get("state", "").upper()
            if pr_state == "MERGED":
                status_info["status"] = "done"
                prev_completed_branch = branch
                status_info["pr"] = existing_pr
                all_versions.append(status_info)
                continue
            elif pr_state == "CLOSED":
                status_info["status"] = "skipped"
                status_info["pr"] = existing_pr
                all_versions.append(status_info)
                continue
            else:
                # PR open — cascade must wait for it to merge
                status_info["status"] = "pr_open"
                status_info["pr"] = existing_pr
                all_versions.append(status_info)
                break

        status_info["status"] = "pending"
        all_versions.append(status_info)

        if next_actionable is None:
            source = prev_completed_branch if prev_completed_branch else default_branch
            next_actionable = {
                "version": version,
                "branch": branch,
                "source_branch": source,
            }
            # Only process one version — block cascade after first actionable
            break

    if next_actionable is None:
        statuses = ",".join(f"{v['branch']}={v['status']}" for v in all_versions)
        return None, f"all_handled({statuses})"

    cherry_pick = dry_run_cherry_pick(
        upstream=up,
        release_branch=next_actionable["branch"],
        source_branch=next_actionable["source_branch"],
        commit_shas=commit_shas,
    )

    if cherry_pick["result"] == "error":
        return None, f"cherrypick_error({cherry_pick.get('error', '?')})"

    return {
        "bug_key": bug_key,
        "bug_summary": summary,
        "bug_labels": bug_labels,
        "bug_component": bug_component,
        "repo": repo_name,
        "upstream": up,
        "fork_url": repo_cfg.get("url", ""),
        "default_branch": default_branch,
        "original_pr": {
            "number": pr_number,
            "url": pr_url,
            "commits": commit_shas,
        },
        "target_version": next_actionable["version"],
        "release_branch": next_actionable["branch"],
        "source_branch": next_actionable["source_branch"],
        "cherry_pick": cherry_pick,
        "all_versions": all_versions,
    }, None


def format_output(item):
    """Format actionable item as structured prompt content."""
    lines = ["## Backport Preflight", ""]
    lines.append(f"### {item['bug_key']}: {item['bug_summary']}")
    lines.append("")
    lines.append("**Cascade task metadata** (use these exact values for task_add/task_update):")
    lines.append(f"- original_bug: {item['bug_key']}")
    lines.append(f"- repo: {item['repo']}")
    lines.append(f"- bug_summary: {item['bug_summary']}")
    lines.append(f"- bug_component: {item['bug_component']}")
    lines.append(f"- bug_labels: {', '.join(item['bug_labels'])}")
    all_version_strs = [v["version"] for v in item["all_versions"]]
    lines.append(f"- target_versions: {', '.join(all_version_strs)}")
    lines.append("")
    lines.append("**Git context:**")
    lines.append(f"- upstream: {item['upstream']}")
    lines.append(f"- fork: {item['fork_url']}")
    lines.append(f"- default_branch: {item['default_branch']}")
    lines.append(f"- original_pr: #{item['original_pr']['number']} ({item['original_pr']['url']})")
    lines.append(f"- commits: {', '.join(item['original_pr']['commits'])}")
    lines.append("")
    lines.append(
        f"**Target: {item['target_version']}** -> {item['release_branch']}"
    )
    lines.append(f"- source: {item['source_branch']}")
    lines.append(
        f"- cherry-pick: **{item['cherry_pick']['result'].upper()}**"
    )
    if item["cherry_pick"].get("conflicting_files"):
        lines.append(
            f"- conflicting files: {', '.join(item['cherry_pick']['conflicting_files'])}"
        )
    if item.get("cascade_task_key"):
        lines.append(f"- cascade_task_key: {item['cascade_task_key']}")
    if item.get("metadata_healed"):
        lines.append("- metadata_healed: true (update cascade task metadata with current values)")
    if item.get("clone_keys"):
        for ver, key in item["clone_keys"].items():
            lines.append(f"- clone_key[{ver}]: {key}")
    lines.append("")
    lines.append("All versions:")
    for v in item["all_versions"]:
        extra = ""
        if v.get("pr"):
            extra = f" (PR #{v['pr'].get('number', '?')})"
        lines.append(f"  {v['branch']}: {v['status']}{extra}")
    lines.append("")
    return "\n".join(lines)


def process_cascade_task(task, repos, tasks):
    """Process an existing cascade task to continue backporting.

    The task stores the original bug key and target versions.
    Returns an actionable item or None.
    """
    meta = task.get("metadata") or {}
    bug_key = meta.get("original_bug", "")
    target_versions = meta.get("target_versions", [])
    completed = set(meta.get("completed", []))
    delegated = set(meta.get("delegated", []))
    clone_keys = meta.get("clone_keys", {})
    repo_name = meta.get("repo", "")
    bug_summary = meta.get("bug_summary", "")
    bug_labels = meta.get("bug_labels", [])
    bug_component = meta.get("bug_component", "")

    if not bug_key or not target_versions:
        pod_log(f"  Cascade {task.get('external_key', '?')}: missing critical metadata (bug={bug_key}, versions={len(target_versions)})")
        return None

    # Self-heal: look up missing fields from Jira
    if not repo_name or not bug_labels or not bug_component:
        pod_log(f"  Cascade {bug_key}: missing metadata (repo={repo_name}), looking up from Jira")
        issue = jira_call(
            "jira_get_issue",
            {"issue_key": bug_key, "fields": "summary,labels,components"},
        )
        if issue:
            fields = issue.get("fields", issue)
            if not repo_name:
                repo_name = get_repo_from_labels(issue)
            if not bug_summary:
                bug_summary = fields.get("summary", issue.get("summary", ""))
            if not bug_labels:
                raw = fields.get("labels", [])
                bug_labels = [(l if isinstance(l, str) else l.get("name", "")) for l in raw]
            if not bug_component:
                comps = fields.get("components", [])
                if comps:
                    bug_component = comps[0].get("name", "") if isinstance(comps[0], dict) else str(comps[0])
            pod_log(f"  Cascade {bug_key}: healed metadata (repo={repo_name}, component={bug_component})")

    if not repo_name:
        pod_log(f"  Cascade {bug_key}: repo still missing after Jira lookup")
        return None

    repo_cfg = repos.get(repo_name)
    if not repo_cfg:
        pod_log(f"  Cascade {bug_key}: repo {repo_name} not in project-repos.json")
        return None

    up, host = upstream_repo(repo_name)
    if not up or host != "github":
        pod_log(f"  Cascade {bug_key}: upstream_repo failed (up={up}, host={host})")
        return None

    # Find the original merged PR
    pr = find_merged_pr(up, bug_key)
    if not pr:
        pod_log(f"  Cascade {bug_key}: no merged PR found on {up}")
        return None

    pr_number = pr["number"]
    pr_url = pr["url"]
    commit_shas = get_pr_commits(up, pr_number)
    if not commit_shas:
        pod_log(f"  Cascade {bug_key}: no commits in PR #{pr_number}")
        return None

    pod_log(f"  Cascade {bug_key}: PR #{pr_number}, {len(commit_shas)} commits, versions={target_versions}")

    default_branch = DEFAULT_BRANCHES.get(repo_name, "main")

    # Build version list and check status
    version_branches = []
    for v in target_versions:
        branch = normalize_version(v)
        version_branches.append({"version": v, "branch": branch})
    version_branches.sort(key=lambda x: version_sort_key(x["branch"]), reverse=True)

    all_versions = []
    next_actionable = None
    prev_completed_branch = None

    for vb in version_branches:
        version = vb["version"]
        branch = vb["branch"]
        status_info = {"version": version, "branch": branch, "status": "unknown"}

        if version in completed:
            clone_key = clone_keys.get(version, "")
            existing_pr = find_existing_backport_pr(up, clone_key, branch) if clone_key else None
            if not existing_pr:
                existing_pr = find_existing_backport_pr(up, bug_key, branch)
            if existing_pr and existing_pr.get("state", "").upper() == "MERGED":
                status_info["status"] = "done"
                prev_completed_branch = branch
                status_info["pr"] = existing_pr
                all_versions.append(status_info)
                pod_log(f"  {branch}: done (PR #{existing_pr.get('number', '?')} merged)")
                continue
            # Marked completed but PR not merged — cascade is blocked
            status_info["status"] = "pr_open"
            if existing_pr:
                status_info["pr"] = existing_pr
            all_versions.append(status_info)
            pod_log(f"  {branch}: completed but PR not merged — cascade blocked")
            break

        if version in delegated:
            clone_key = clone_keys.get(version, "")
            existing_pr = find_existing_backport_pr(up, clone_key, branch) if clone_key else None
            if not existing_pr:
                existing_pr = find_existing_backport_pr(up, bug_key, branch)
            if existing_pr and existing_pr.get("state", "").upper() == "MERGED":
                status_info["status"] = "done"
                prev_completed_branch = branch
                status_info["pr"] = existing_pr
                all_versions.append(status_info)
                pod_log(f"  {branch}: delegated, PR #{existing_pr.get('number', '?')} merged")
                continue
            # Delegated but PR not merged — cascade must wait
            status_info["status"] = "delegated_waiting"
            if existing_pr:
                status_info["pr"] = existing_pr
            all_versions.append(status_info)
            pod_log(f"  {branch}: delegated, PR not merged — cascade blocked")
            break

        if not check_branch_exists(up, branch):
            status_info["status"] = "branch_missing"
            all_versions.append(status_info)
            pod_log(f"  {branch}: branch missing")
            continue

        clone_key = clone_keys.get(version, "")
        existing_pr = find_existing_backport_pr(up, clone_key, branch) if clone_key else None
        if not existing_pr:
            existing_pr = find_existing_backport_pr(up, bug_key, branch)
        if existing_pr:
            pr_state = existing_pr.get("state", "").upper()
            if pr_state == "MERGED":
                status_info["status"] = "done"
                prev_completed_branch = branch
                status_info["pr"] = existing_pr
                all_versions.append(status_info)
                pod_log(f"  {branch}: done (PR #{existing_pr.get('number', '?')} merged)")
                continue
            elif pr_state == "CLOSED":
                status_info["status"] = "skipped"
                status_info["pr"] = existing_pr
                all_versions.append(status_info)
                pod_log(f"  {branch}: skipped (PR #{existing_pr.get('number', '?')} closed)")
                continue
            else:
                # PR open — cascade must wait
                status_info["status"] = "pr_open"
                status_info["pr"] = existing_pr
                all_versions.append(status_info)
                pod_log(f"  {branch}: pr_open — cascade blocked")
                break

        status_info["status"] = "pending"
        all_versions.append(status_info)
        pod_log(f"  {branch}: pending")

        if next_actionable is None:
            source = prev_completed_branch if prev_completed_branch else default_branch
            next_actionable = {
                "version": version,
                "branch": branch,
                "source_branch": source,
            }
            # Only process one version at a time
            break

    if next_actionable is None:
        return None

    pod_log(f"  Dry-run cherry-pick {next_actionable['source_branch']} -> {next_actionable['branch']}...")
    cherry_pick = dry_run_cherry_pick(
        upstream=up,
        release_branch=next_actionable["branch"],
        source_branch=next_actionable["source_branch"],
        commit_shas=commit_shas,
    )

    if cherry_pick["result"] == "error":
        pod_log(f"  {bug_key}: dry-run error: {cherry_pick.get('error')}")
        return None

    # Check if metadata was healed and needs updating
    metadata_healed = (
        repo_name != meta.get("repo", "")
        or bug_summary != meta.get("bug_summary", "")
        or bug_labels != meta.get("bug_labels", [])
        or bug_component != meta.get("bug_component", "")
    )

    return {
        "bug_key": bug_key,
        "bug_summary": bug_summary,
        "bug_labels": bug_labels,
        "bug_component": bug_component,
        "repo": repo_name,
        "upstream": up,
        "fork_url": repo_cfg.get("url", ""),
        "default_branch": default_branch,
        "original_pr": {
            "number": pr_number,
            "url": pr_url,
            "commits": commit_shas,
        },
        "target_version": next_actionable["version"],
        "release_branch": next_actionable["branch"],
        "source_branch": next_actionable["source_branch"],
        "cherry_pick": cherry_pick,
        "all_versions": all_versions,
        "cascade_task_key": task.get("external_key", ""),
        "clone_keys": clone_keys,
        "metadata_healed": metadata_healed,
    }


def main():
    active_n, max_n = get_capacity()
    pod_log(f"Capacity: {active_n}/{max_n}")
    if active_n >= max_n:
        pod_log("At capacity, skipping")
        output_result("skip", f"At capacity ({active_n}/{max_n})")
        jira_cleanup()
        return

    repos = load_project_repos()
    tasks = get_tasks()
    pod_log(f"Tasks: {len(tasks)}")

    # Query 2: Check existing cascade tasks first (ongoing work has priority)
    cascade_tasks = [
        t for t in tasks
        if (t.get("external_key") or "").startswith(BACKPORT_TASK_PREFIX)
        and t.get("status") not in ("done", "archived")
    ]
    pod_log(f"Cascade tasks: {len(cascade_tasks)}")
    for task in cascade_tasks:
        item = process_cascade_task(task, repos, tasks)
        if item:
            pod_log(f"Cascade actionable: {item['bug_key']} -> {item['release_branch']}")
            content = format_output(item)
            output_result("start", content)
            jira_cleanup()
            return

    # Query 1: Search for new MODIFIED bugs with Target Backport Versions
    pod_log("Querying Jira...")
    bugs = search_modified_bugs()
    pod_log(f"Jira returned: {len(bugs) if bugs else 0} bugs")
    if not bugs:
        jira_cleanup()
        if not cascade_tasks:
            output_result("skip", f"Jira returned 0 bugs (capacity {active_n}/{max_n}, tasks {len(tasks)})")
        else:
            output_result("skip", "Cascade tasks exist but no versions are actionable")
        return

    # Skip bugs that already have a cascade task (active OR done)
    all_cascade_tasks = [
        t for t in tasks
        if (t.get("external_key") or "").startswith(BACKPORT_TASK_PREFIX)
    ]
    existing_bug_keys = {
        k for t in all_cascade_tasks
        if (k := (t.get("metadata") or {}).get("original_bug"))
    }

    skip_reasons = []
    for bug in bugs:
        bug_key = bug.get("key", "")
        if bug_key in existing_bug_keys:
            skip_reasons.append(f"{bug_key}:has_cascade_task")
            pod_log(f"Skip {bug_key}: has_cascade_task")
            continue
        item, reason = process_bug(bug, repos, tasks)
        if item:
            pod_log(f"Actionable: {bug_key} -> {item['release_branch']} ({item['cherry_pick']['result']})")
            content = format_output(item)
            output_result("start", content)
            jira_cleanup()
            return
        skip_reasons.append(f"{bug_key}:{reason}")
        pod_log(f"Skip {bug_key}: {reason}")

    jira_cleanup()
    output_result(
        "skip", f"Checked {len(bugs)} bugs: {'; '.join(skip_reasons)}"
    )


if __name__ == "__main__":
    main()
