#!/usr/bin/env bash
# reposync-verify.sh
#
# 1. Mirror the COPR hyprland repo locally with reposync.
# 2. Verify every mirrored package still resolves its dependencies with a
#    dry-run install, so a hyprutils soname/ABI bump doesn't leave broken
#    dependents behind (the exact failure the update-versions.py cascade fixes).
#
# A genuine breakage shows up as "nothing provides libhyprutils.so.X()(64bit)"
# for some dependent, meaning that dependent still needs to be rebuilt.
#
# Env overrides: OWNER PROJECT FEDORA ARCH OUTDIR
set -euo pipefail

OWNER="${OWNER:-hermitfeather}"
PROJECT="${PROJECT:-hyprland}"
FEDORA="${FEDORA:-$(rpm -E %fedora 2>/dev/null || echo 43)}"
ARCH="${ARCH:-$(uname -m)}"
OUTDIR="${OUTDIR:-$(pwd)/testdir/reposync}"
REPONAME="localcheck"
BASEURL="https://download.copr.fedorainfracloud.org/results/${OWNER}/${PROJECT}/fedora-${FEDORA}-${ARCH}"

mkdir -p "$OUTDIR"

echo "==> Mirroring ${OWNER}/${PROJECT} (fedora-${FEDORA}-${ARCH}) -> $OUTDIR"
reposync \
  --repofrompath="$REPONAME,$BASEURL" \
  --repo="$REPONAME" \
  -p "$OUTDIR" \
  --download-metadata \
  --newest-only \
  --setopt="$REPONAME.gpgcheck=0"

LOCAL_REPO="$OUTDIR/$REPONAME"
echo "==> Mirror ready: $LOCAL_REPO"

echo "==> Verifying dependency solvability (dry-run install per package)..."
fail=0
log="$(mktemp)"
while IFS= read -r rpm; do
  name="$(rpm -qp --qf '%{name}' "$rpm" 2>/dev/null || true)"
  [ -z "$name" ] && continue
  if ! dnf --quiet \
        --repofrompath="$REPONAME,file://$LOCAL_REPO" \
        --repo="$REPONAME" --setopt="$REPONAME.gpgcheck=0" \
        install --assumeno --setopt=install_weak_deps=False "$name" >"$log" 2>&1; then
    if grep -qiE 'nothing provides|problem:|conflict with' "$log"; then
      echo "  [BROKEN] $name"
      grep -iE 'nothing provides|problem:|conflict with' "$log" | sed 's/^/      /'
      fail=1
    fi
  fi
done < <(find "$LOCAL_REPO" -name '*.rpm' | sort)

rm -f "$log"
if [ "$fail" -ne 0 ]; then
  echo "==> VERIFY FAILED: broken dependencies listed above."
  exit 1
fi
echo "==> VERIFY OK: every mirrored package resolves its dependencies."
