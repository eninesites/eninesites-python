#!/usr/bin/env bash
# Install system dependencies that cannot be pip-installed.
# Idempotent: checks presence before installing.
# Called by `make system-deps` (which `make install` depends on).
#
# Usage: add one install_if_missing call per dependency.
# Example:
#   install_if_missing pdftotext poppler poppler-utils
#
# Arguments: <command-to-check> <brew-package> <linux-package>
set -euo pipefail

# Root for a package install. Already root (container build, CI) needs no sudo binary at
# all; otherwise defer to sudo. Resolved per call rather than once at the top, because it
# is only consulted when a package is missing -- a fully provisioned machine should never
# be told it lacks sudo.
sudo_prefix() {
    if [ "$(id -u)" -eq 0 ]; then return; fi
    if command -v sudo >/dev/null 2>&1; then echo sudo; return; fi
    echo "ERROR: package install needs root, but this is not root and sudo is absent." >&2
    exit 1
}

linux_install() {
    local pkg=$1 sudo
    sudo=$(sudo_prefix)
    if command -v apt-get >/dev/null 2>&1; then
        echo "→ $sudo apt-get install -y $pkg"
        $sudo apt-get install -y "$pkg"
    elif command -v pacman >/dev/null 2>&1; then
        # --needed skips an already-installed package instead of reinstalling it, which is
        # what keeps a re-run idempotent the way the apt-get branch is.
        echo "→ $sudo pacman -S --needed --noconfirm $pkg"
        $sudo pacman -S --needed --noconfirm "$pkg"
    elif command -v dnf >/dev/null 2>&1; then
        echo "→ $sudo dnf install -y $pkg"
        $sudo dnf install -y "$pkg"
    else
        echo "ERROR: no supported package manager (apt-get / pacman / dnf) found." >&2
        echo "       Install '$pkg' manually and re-run." >&2
        exit 1
    fi
}

install_if_missing() {
    local cmd=$1 brew_pkg=$2 linux_pkg=$3
    if command -v "$cmd" >/dev/null 2>&1; then
        echo "✓ $cmd present ($(command -v "$cmd"))"
        return
    fi
    case "$(uname -s)" in
        Darwin)
            if ! command -v brew >/dev/null 2>&1; then
                echo "ERROR: Homebrew required but not found. Install from https://brew.sh" >&2
                exit 1
            fi
            echo "→ brew install $brew_pkg"
            brew install "$brew_pkg"
            ;;
        Linux)
            linux_install "$linux_pkg"
            ;;
        *)
            echo "WARNING: unsupported platform $(uname -s); install $linux_pkg manually" >&2
            ;;
    esac
}

# racecar-shipped: gitleaks backs the `gitleaks` pre-commit hook (secret scan).
# Homebrew carries it; Debian/Ubuntu do NOT package it in the default repos, so the
# Linux branch below will fail loudly there. Install from the GitHub release binary
# or via `go install github.com/gitleaks/gitleaks/v8@latest`, then rerun `make install`.
install_if_missing gitleaks gitleaks gitleaks

# Add project-specific system dependencies below.
# Format: install_if_missing <command> <brew-package> <linux-package>
#
# One Linux package name is assumed to serve apt-get, pacman, and dnf alike. That holds
# for gitleaks; it does not hold in general (poppler-utils is `poppler` on Arch, and
# libreoffice is `libreoffice-fresh`/`-still` there). Fix the dispatch with a single Linux
# name for now; add a fourth optional argument when a shipped package actually disagrees
# across managers, not before.
