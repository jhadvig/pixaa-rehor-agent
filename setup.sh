#!/bin/bash
set -e

echo "pixaa-rehor-agent" > /home/botuser/app/.instance-id

# Instance-specific packages and tools go here:
# dnf install -y --nodocs <package>
# pip3.12 install <package>
# npm install -g <package>

# ---------------------------------------------------------------------------
# Extra Go toolchains for the pixaa-ocpbugs-go instance
# ---------------------------------------------------------------------------
# The `go` env preset installs GOVERSIONS (default "1.24.13 1.25.13") via goenv
# at /usr/local/goenv. The OCPBUGS Go fleet needs versions beyond that default:
#   - Go 1.22.x  — openshift/cincinnati-operator (go.mod: go 1.22.0)
#   - Go 1.26.x  — OLM/operator-framework, CCO, oc, oc-mirror (go.mod: go 1.26.x)
# (Go 1.25.x for cluster-version-operator is already covered by the preset's 1.25.13.)
# Install the extra versions without changing the global default.
if [ -d /usr/local/goenv ]; then
    export GOENV_ROOT=/usr/local/goenv
    export PATH="$GOENV_ROOT/bin:$PATH"
    eval "$(goenv init -)"
    for v in 1.22.12 1.26.7; do
        goenv install -s "$v"
    done
    goenv rehash
    echo "Extra Go versions installed: $(goenv versions --bare | tr '\n' ' ')"
else
    echo "WARNING: /usr/local/goenv not found — 'go' env preset did not run; skipping extra Go installs"
fi

# ---------------------------------------------------------------------------
# Rust toolchain for openshift/cincinnati (OTA family, Cargo + Justfile)
# ---------------------------------------------------------------------------
# There is no `rust` env preset in the base engine, so install it here. The
# runtime entrypoint is a non-login shell (no ~/.bashrc / /etc/profile.d sourcing),
# so install into the botuser HOME defaults (RUSTUP_HOME=$HOME/.rustup,
# CARGO_HOME=$HOME/.cargo) — at runtime HOME=/home/botuser, so the cargo/rustc
# proxies resolve the toolchain with no env needed — and expose the binaries on
# the fixed PATH via /usr/local/bin. Ownership is fixed by the Dockerfile's final
# `chown -R botuser:0 /home/botuser`.
ARCH=$(uname -m)  # x86_64 | aarch64 — matches both rustup and just release naming

# Build deps for common Rust crates in cincinnati (openssl-sys, etc.)
dnf install -y --nodocs openssl-devel pkgconf-pkg-config
dnf clean all

export RUSTUP_HOME=/home/botuser/.rustup
export CARGO_HOME=/home/botuser/.cargo
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
    | sh -s -- -y --no-modify-path --profile minimal --default-toolchain stable

# Expose the rustup proxies on the runtime PATH (/usr/local/bin is on PATH; the
# proxies default RUSTUP_HOME/CARGO_HOME to $HOME/.rustup /.cargo at runtime).
for b in cargo cargo-clippy cargo-fmt clippy-driver rustc rustdoc rustfmt rustup; do
    ln -sf "$CARGO_HOME/bin/$b" "/usr/local/bin/$b"
done

# just — task runner used by cincinnati (self-contained binary, no rustup dependency)
JUST_VERSION=1.36.0
curl -fsSL "https://github.com/casey/just/releases/download/${JUST_VERSION}/just-${JUST_VERSION}-${ARCH}-unknown-linux-musl.tar.gz" \
    | tar -xz -C /usr/local/bin just

echo "Rust toolchain installed: $(/usr/local/bin/rustc --version), $(/usr/local/bin/just --version)"

# Override cycle timeout: 45 minutes (default is 30)
python3 -c "
import json
with open('/home/botuser/app/config.json') as f:
    cfg = json.load(f)
cfg['claude']['cycleTimeoutSeconds'] = 2700
with open('/home/botuser/app/config.json', 'w') as f:
    json.dump(cfg, f, indent=2)
"

echo "Instance setup complete: pixaa-rehor-agent"
