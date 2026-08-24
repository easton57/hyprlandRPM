#!/usr/bin/env python3
"""
Kick off COPR rebuilds in dependency order (tier-by-tier), rebuilding only
packages whose local spec version is newer than what's already in COPR.

This reuses check-copr-versions.py to decide what is outdated, then submits
each outdated package to COPR with `copr-cli build-package` (the package must
already be defined in COPR, pointing at this git repo).

Packages within a tier are submitted in parallel; the script waits for a whole
tier to finish before starting the next, so inter-package dependencies are
always available in the repo.

Usage:
    python3 rebuild-copr.py                 # rebuild outdated pkgs, fedora 42
    python3 rebuild-copr.py --fedora 41     # different release
    python3 rebuild-copr.py --dry-run       # show what would be submitted
    python3 rebuild-copr.py --continue-on-failure

A failed build only halts later tiers when the failing package is a
dependency of others (e.g. hyprutils). Failures of leaf packages that
nothing else depends on (e.g. swww) are reported but do not stop the run.
 """

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

# Single source of truth for build order: load check-copr-versions.py by path
# (hyphenated filename is not a valid module identifier).
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
_spec = importlib.util.spec_from_file_location(
    "check_copr_versions", SCRIPT_DIR / "check-copr-versions.py")
_check_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_check_mod)
TIERS = _check_mod.TIERS
DEPENDENCY_SET = _check_mod.get_dependency_set()

DEFAULT_OWNER = "hermitfeather"
DEFAULT_PROJECT = "hyprland"
DEFAULT_FEDORA = "43"


def get_outdated(fedora):
    """Return a set of package names that need rebuilding (from check script)."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "check-copr-versions.py"), fedora],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        sys.exit(f"check-copr-versions.py failed (exit {result.returncode})")

    data = json.loads(result.stdout)
    outdated = set()
    for tier in data.get("tiers", []):
        outdated.update(tier.get("packages", []))
    return outdated


def submit_batch(packages, project, copr_cli, dry_run):
    """Submit one tier of packages in parallel and wait for all to finish.

    Returns dict {pkg: ("ok"|"fail", detail)}.
    """
    if not packages:
        return {}

    procs = {}
    for pkg in packages:
        if dry_run:
            print(f"  [dry-run] would submit: copr-cli build-package "
                  f"--name {pkg} {project}")
            continue
        cmd = [copr_cli, "build-package", "--name", pkg, project]
        log = open(REPO_ROOT / "logs" / f"{pkg}.log", "w")
        p = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
        procs[pkg] = p

    results = {}
    for pkg, p in procs.items():
        rc = p.wait()
        results[pkg] = ("ok" if rc == 0 else "fail", f"exit {rc}")
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fedora", default=DEFAULT_FEDORA,
                        help=f"Fedora release to check versions against "
                             f"(default {DEFAULT_FEDORA})")
    parser.add_argument("--owner", default=DEFAULT_OWNER)
    parser.add_argument("--project", default=DEFAULT_PROJECT)
    parser.add_argument("--copr-cli", default="copr-cli")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be submitted without doing it")
    parser.add_argument("--continue-on-failure", action="store_true",
                        help="Keep going to next tier even if a dependency build fails")
    args = parser.parse_args()

    project = f"{args.owner}/{args.project}"

    if not args.dry_run:
        if not subprocess.run([args.copr_cli, "--help"],
                              capture_output=True).returncode == 0:
            sys.exit(f"copr-cli not found ('{args.copr_cli}'). Install it or use --dry-run.")

    if not args.dry_run:
        (REPO_ROOT / "logs").mkdir(exist_ok=True)

    outdated = get_outdated(args.fedora)
    if not outdated:
        print("Nothing to rebuild - all package versions match COPR.")
        return

    print(f"Rebuilding {len(outdated)} outdated package(s) against "
          f"{project} (fedora {args.fedora})")

    blocking_failed = False
    any_failed = False
    for i, tier in enumerate(TIERS):
        tier_pkgs = [p for p in tier if p in outdated]
        if not tier_pkgs:
            continue
        print(f"\n=== Tier {i}: {', '.join(tier_pkgs)} ===")
        results = submit_batch(tier_pkgs, project, args.copr_cli, args.dry_run)
        for pkg, (status, detail) in sorted(results.items()):
            mark = "OK  " if status == "ok" else "FAIL"
            print(f"  [{mark}] {pkg} ({detail})")
            if status == "fail":
                any_failed = True
                if pkg in DEPENDENCY_SET:
                    blocking_failed = True

        if blocking_failed and not args.continue_on_failure:
            print("\nA build for a dependency failed; stopping before next "
                  "tier so dependents are not built against a broken dep. "
                  "Use --continue-on-failure to push through.")
            sys.exit(1)

    if any_failed:
        print("\nDone, but some builds failed - see logs/ for details.")
        sys.exit(1)
    print("\nAll rebuilds submitted and finished successfully.")


if __name__ == "__main__":
    main()
