#!/usr/bin/env python3
"""
Check which packages need rebuilding by comparing local spec versions
against what's already built in COPR.

Usage: python3 check-copr-versions.py [fedora_version]
Output: JSON object with package lists by tier
"""

import json
import os
import re
import subprocess
import sys
import urllib.request
import gzip
import xml.etree.ElementTree as ET
from pathlib import Path

COPR_OWNER = "hermitfeather"
COPR_PROJECT = "hyprland"

# Build order tiers
TIERS = [
    ["hyprutils", "hyprwayland-scanner", "glaze", "hyprland-protocols", "aylurs-gtk-shell", "xcur2png", "uwsm", "waybar-git", "swww", "swaylock-effects", "satty", "python-screeninfo", "mpvpaper", "python-imageio-ffmpeg", "pyprland", "matugen", "kitty", "material-icons-fonts", "hyprnome", "hellwal", "hyprdim", "eww-git", "appmenu-glib-translator", "astal-io", "cliphist", "hyprland-autoname-workspaces"],
    ["hyprwire", "hyprgraphics", "aquamarine", "hyprpicker", "nwg-look"],
    ["hyprlang"],
    ["hyprqt6engine", "hypridle", "hyprsunset", "hyprcursor", "hyprland-qt-support", "hyprtoolkit", "xdg-desktop-portal-hyprland", "hyprlock", "hyprpolkitagent"],
    ["hyprpaper", "hyprsysteminfo", "hyprpwcenter", "hyprlauncher", "hyprland-guiutils", "nwg-clipman"],
    ["hyprland-git", "astal", "astal-gtk4"],
    ["astal-libs", "astal-gjs"],
    ["astal-lua", "hyprpanel", "waypaper"],
    ["hyprshot", "hyprland-contrib"],
]

def find_spec_files(repo_dir):
    """Find all .spec files in the repository."""
    spec_files = {}
    for root, dirs, files in os.walk(repo_dir):
        # Skip hidden dirs and rpmbuild
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'rpmbuild']
        for f in files:
            if f.endswith('.spec'):
                spec_path = os.path.join(root, f)
                spec_files[f] = spec_path
    return spec_files

def get_dependency_set(repo_dir=None):
    """Return the set of package names that are depended upon by at least one
    other package's (Build)Requires.

    A package in this set is a *dependency* of others: if its build fails,
    downstream packages cannot build, so the rebuild pipeline should stop.
    Leaf applications that nothing else depends on are not included, so their
    failures can be tolerated without cancelling later tiers.

    Matching is done by package-name substring against (Build)Requires lines,
    which also catches ``-devel`` subpackages and ``pkgconfig(name)`` provides.
    """
    if repo_dir is None:
        repo_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    spec_files = find_spec_files(repo_dir)
    names = sorted({n.replace('.spec', '') for n in spec_files},
                   key=len, reverse=True)

    depended_on = set()
    dep_re = re.compile(r'^(?:Build)?Requires\s*:', re.IGNORECASE)
    for spec_name, spec_path in spec_files.items():
        pkg = spec_name.replace('.spec', '')
        with open(spec_path, 'r') as f:
            for line in f:
                if not dep_re.match(line):
                    continue
                for name in names:
                    if name == pkg:
                        continue
                    if re.search(r'\b' + re.escape(name) + r'(?:\b|-)', line):
                        depended_on.add(name)
    return depended_on


def parse_spec_version(spec_path):
    """Parse version and release from a spec file."""
    version = ""
    release = ""
    with open(spec_path, 'r') as f:
        for line in f:
            if line.startswith('Version:'):
                version = line.split(':', 1)[1].strip()
            elif line.startswith('Release:'):
                release = line.split(':', 1)[1].strip()
            if version and release:
                break
    return version, release

def get_copr_versions(fedora_version):
    """Fetch package versions from COPR repodata."""
    repo_url = f"https://download.copr.fedorainfracloud.org/results/{COPR_OWNER}/{COPR_PROJECT}/fedora-{fedora_version}-x86_64"
    
    try:
        # Fetch repomd.xml to find primary.xml.gz location
        repomd_url = f"{repo_url}/repodata/repomd.xml"
        with urllib.request.urlopen(repomd_url, timeout=30) as response:
            repomd_content = response.read().decode('utf-8')
        
        # Find primary.xml.gz location
        match = re.search(r'<location href="([^"]*primary\.xml\.gz)"', repomd_content)
        if not match:
            print(f"Warning: Could not find primary.xml.gz in repodata", file=sys.stderr)
            return {}
        
        primary_path = match.group(1)
        primary_url = f"{repo_url}/{primary_path}"
        
        # Download and parse primary.xml.gz
        with urllib.request.urlopen(primary_url, timeout=60) as response:
            gz_content = response.read()
        
        xml_content = gzip.decompress(gz_content).decode('utf-8')
        
        # Parse XML
        root = ET.fromstring(xml_content)
        versions = {}
        
        for package in root.findall('.//{http://linux.duke.edu/metadata/common}package'):
            name_elem = package.find('{http://linux.duke.edu/metadata/common}name')
            version_elem = package.find('{http://linux.duke.edu/metadata/common}version')
            
            if name_elem is not None and version_elem is not None:
                name = name_elem.text
                ver = version_elem.get('ver', '')
                rel = version_elem.get('rel', '')
                versions[name] = f"{ver}-{rel}"
        
        return versions
    
    except Exception as e:
        print(f"Warning: Could not fetch COPR versions: {e}", file=sys.stderr)
        return {}

def compare_versions(local_ver, copr_ver):
    """Compare versions. Returns True if local is newer or different."""
    if local_ver == copr_ver:
        return False
    
    # Try rpmdev-vercmp if available
    try:
        result = subprocess.run(
            ['rpmdev-vercmp', local_ver, copr_ver],
            capture_output=True, text=True, timeout=5
        )
        output = result.stdout.strip()
        if 'newer' in output:
            return True
        return False
    except:
        # Fallback: if versions differ, assume rebuild needed
        return True

def main():
    fedora_version = sys.argv[1] if len(sys.argv) > 1 else "42"
    repo_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    print(f"Checking COPR versions for Fedora {fedora_version}...", file=sys.stderr)
    
    # Get COPR versions
    copr_versions = get_copr_versions(fedora_version)
    print(f"Found {len(copr_versions)} packages in COPR", file=sys.stderr)
    
    # Get local spec versions
    spec_files = find_spec_files(repo_dir)
    local_versions = {}
    
    for spec_name, spec_path in spec_files.items():
        version, release = parse_spec_version(spec_path)
        if version:
            pkg_name = spec_name.replace('.spec', '')
            local_versions[pkg_name] = f"{version}-{release}"
    
    print(f"Found {len(local_versions)} local packages", file=sys.stderr)
    
    # Compare and find packages that need rebuilding
    needs_rebuild = {}
    
    for pkg_name, local_ver in local_versions.items():
        copr_ver = copr_versions.get(pkg_name, "")
        
        if not copr_ver:
            print(f"  {pkg_name}: not in COPR -> needs build", file=sys.stderr)
            needs_rebuild[pkg_name] = True
        elif compare_versions(local_ver, copr_ver):
            print(f"  {pkg_name}: {local_ver} > {copr_ver} -> needs build", file=sys.stderr)
            needs_rebuild[pkg_name] = True
        else:
            print(f"  {pkg_name}: {local_ver} == {copr_ver} -> skip", file=sys.stderr)
    
    # Organize by tiers
    result = {"fedora_version": fedora_version, "tiers": []}
    
    for i, tier in enumerate(TIERS):
        tier_packages = [pkg for pkg in tier if pkg in needs_rebuild]
        if tier_packages:
            result["tiers"].append({
                "tier": i,
                "packages": tier_packages
            })
    
    # Output JSON
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
