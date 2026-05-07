#!/bin/bash
set -e

if [ $# -ne 2 ]; then
    echo "Usage: $0 <package-directory> <spec-file>"
    exit 1
fi

PKG_DIR="$1"
SPEC_FILE="$2"

if [ ! -d "$PKG_DIR" ]; then
    echo "Error: Package directory '$PKG_DIR' does not exist"
    exit 1
fi

if [ ! -f "$PKG_DIR/$SPEC_FILE" ]; then
    echo "Error: Spec file '$PKG_DIR/$SPEC_FILE' does not exist"
    exit 1
fi

echo "Installing build dependencies..."
dnf builddep "$PKG_DIR/$SPEC_FILE"

echo "Building RPM (not installing)..."
rpmbuild -bb "$PKG_DIR/$SPEC_FILE"

echo "Build complete."
