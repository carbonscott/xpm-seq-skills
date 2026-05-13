#!/bin/bash
# Environment for xpm-seq skill.
# Adds xpm-seq to PATH and configures uv cache.
# Override any variable via env.local or by exporting before sourcing.

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Add xpm-seq to PATH
export PATH="$SKILL_DIR/bin:$PATH"

# uv cache per user (avoids permission issues in shared deploys)
export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache-$USER}"

# User overrides last
[ -f "$SKILL_DIR/env.local" ] && source "$SKILL_DIR/env.local"
