#!/usr/bin/env python3
"""
Pull the latest upstream release tag for every package and report (or apply)
version bumps, so you no longer have to check each project's git repo by hand.

For each spec it:
  1. Finds the upstream git repo (from `URL:`, `%global forgeurl`, or
     `%global goipath`).
  2. Lists tags with `git ls-remote --tags` and picks the newest semver tag.
  3. Compares it with the semver at the start of the spec's `Version:` line.
  4. Prints a report; with --apply it rewrites the Version line.

Snapshot-only packages whose Version has no fixed release (e.g. astal's
`0~%{bumpver}.git...`) are skipped. Git-snapshot packages that still carry a
release base (e.g. hyprland-git `0.55.2^...`, eww-git `0.6.0^...`) are tracked
by that base release and the trailing macro is preserved on update.

Usage:
    python3 update-versions.py            # dry-run report
    python3 update-versions.py --apply     # rewrite Version: where newer
    python3 update-versions.py --apply aquamarine hyprutils
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

SEMVER = re.compile(r'(\d+\.\d+(?:\.\d+)*)')
URL_HOST = re.compile(r'https?://([^/]+)(/[^?\s]*)?')
GITHUB_PATH = re.compile(r'^/([^/]+)/([^/#?]+)')


def find_specs(repo_dir):
    specs = []
    for root, dirs, files in os.walk(repo_dir):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'rpmbuild']
        for f in files:
            if f.endswith('.spec'):
                specs.append(os.path.join(root, f))
    return sorted(specs)


def parse_spec(path):
    text = Path(path).read_text(errors='replace')
    info = {"path": path, "name": None, "version_line": None,
            "version_raw": None, "semver": None, "semver_span": None,
            "repo": None}
    for line in text.splitlines():
        if info["name"] is None:
            m = re.match(r'^Name:\s*(.+)$', line)
            if m:
                info["name"] = m.group(1).strip()
        if info["version_line"] is None:
            m = re.match(r'^Version:\s*(.+)$', line)
            if m:
                info["version_line"] = line
                raw = m.group(1).strip()
                info["version_raw"] = raw
                sm = SEMVER.match(raw)
                if sm:
                    info["semver"] = sm.group(1)
                    info["semver_span"] = sm.span(1)
    info["repo"] = detect_repo(text)
    return info


def detect_repo(text):
    """Return the upstream git repo URL (host/owner/repo) or None."""
    # 1. forgeurl macro
    m = re.search(r'%global\s+forgeurl\s+(\S+)', text)
    if m:
        return normalize_repo(m.group(1))
    # 2. goipath -> github.com/owner/repo
    m = re.search(r'%global\s+goipath\s+(\S+)', text)
    if m:
        p = m.group(1)
        mm = re.match(r'github\.com/([^/]+)/([^/]+)', p)
        if mm:
            return f"https://github.com/{mm.group(1)}/{mm.group(2)}"
    # 3. URL: literal
    m = re.search(r'^URL:\s*(\S+)', text, re.MULTILINE)
    if m:
        url = m.group(1)
        if url.startswith('http') and '%{' not in url:
            return normalize_repo(url)
    return None


def normalize_repo(url):
    m = URL_HOST.match(url)
    if not m:
        return None
    host, path = m.group(1), (m.group(2) or '')
    mm = GITHUB_PATH.match(path)
    if mm:
        owner, repo = mm.group(1), mm.group(2)
        # strip a trailing .git and any subpath
        repo = re.sub(r'\.git$', '', repo)
        return f"https://{host}/{owner}/{repo}"
    return None


def get_latest_tag(repo):
    try:
        out = subprocess.run(
            ["git", "ls-remote", "--tags", repo],
            capture_output=True, text=True, timeout=30)
    except Exception:
        return None, "git error"
    if out.returncode != 0:
        return None, out.stderr.strip().splitlines()[0] if out.stderr.strip() else "no tags"
    tags = set()
    for line in out.stdout.splitlines():
        # format: <hash>\trefs/tags/<name>  (plus optional ^{} peeled refs)
        if '\t' not in line:
            continue
        ref = line.split('\t', 1)[1]
        name = ref.replace('refs/tags/', '').replace('^{}', '')
        tags.add(name)
    cands = []
    for t in tags:
        norm = t
        if norm.lower().startswith('v'):
            norm = norm[1:]
        # Only consider stable numeric releases (no alpha/beta/rc suffixes),
        # which is what "latest release number" means here.
        if re.fullmatch(r'\d+(?:\.\d+)*', norm):
            cands.append((norm, t))
    if not cands:
        return None, "no stable release tags"
    best = cands[0]
    for c in cands[1:]:
        if vercmp(c[0], best[0]) > 0:
            best = c
    return best[0], best[1]


def version_key(v):
    return [int(x) for x in v.split('.')]


def vercmp(a, b):
    try:
        r = subprocess.run(["rpmdev-vercmp", a, b],
                           capture_output=True, text=True, timeout=5)
        o = r.stdout.strip()
        if 'first' in o and 'newer' in o:
            return 1
        if 'second' in o and 'newer' in o:
            return -1
        return 0
    except Exception:
        ka, kb = version_key(a), version_key(b)
        return (ka > kb) - (ka < kb)


def apply_update(info, new_version):
    path = Path(info["path"])
    text = path.read_text()
    line = info["version_line"]
    raw = info["version_raw"]
    s, e = info["semver_span"]
    new_raw = raw[:s] + new_version + raw[e:]
    new_line = re.sub(r'Version:\s*.+', f"Version:        {new_raw}", line, count=1)
    text = text.replace(line, new_line, 1)
    path.write_text(text)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true",
                    help="Rewrite Version: lines where upstream is newer")
    ap.add_argument("packages", nargs="*", help="Limit to these package names")
    args = ap.parse_args()

    repo_dir = Path(__file__).resolve().parent.parent
    specs = find_specs(repo_dir)
    if args.packages:
        wanted = set(args.packages)
        specs = [s for s in specs
                 if parse_spec(s)["name"] in wanted or
                 os.path.basename(os.path.dirname(s)) in wanted]

    print(f"{'PACKAGE':<32} {'CURRENT':<14} {'LATEST':<14} STATUS")
    print("-" * 78)
    changed = []
    for spec in specs:
        info = parse_spec(spec)
        if not info["semver"]:
            print(f"{info['name'] or spec:<32} {'-':<14} {'-':<14} snapshot (no fixed release)")
            continue
        if not info["repo"]:
            print(f"{info['name'] or spec:<32} {info['semver']:<14} {'-':<14} no upstream repo found")
            continue
        latest, raw = get_latest_tag(info["repo"])
        if latest is None:
            print(f"{info['name'] or spec:<32} {info['semver']:<14} {'-':<14} {raw}")
            continue
        cmp = vercmp(latest, info["semver"])
        if cmp > 0:
            status = f"NEW -> {latest} (from {raw})"
            if args.apply:
                apply_update(info, latest)
                status += " [updated]"
                changed.append(info["name"])
            else:
                status += " [dry-run]"
        elif cmp < 0:
            status = f"local ahead ({latest})"
        else:
            status = "up to date"
        print(f"{info['name'] or spec:<32} {info['semver']:<14} {latest:<14} {status}")

    if changed:
        print(f"\nUpdated {len(changed)} spec(s): {', '.join(changed)}")


if __name__ == "__main__":
    main()
