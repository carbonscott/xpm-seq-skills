# skill-xpm-seq

Claude/OpenCode skill for LCLS-II XPM timing sequence programming. Bundles a single-file PEP 723 CLI (`xpm-seq`) with three subcommands — `ratecalc`, `generate`, `validate` — for the workflow **check rates → generate → validate → deploy command**. Centrally deployed for LCLS users via the [deploy-opencode](https://github.com/carbonscott/deploy-opencode) meta-deploy script.

The bundled `bin/xpm-seq.py` is vendored from [`carbonscott/xpm-seq-tools`](https://github.com/carbonscott/xpm-seq-tools) (pinned commit `7706d60e`).

## Layout

```
claude/skills/xpm-seq/
  SKILL.md         # Workflow guidance for the LLM
  env.sh           # Adds bin/ to PATH, configures uv cache
  bin/
    xpm-seq        # Bash wrapper: exec uv run --script xpm-seq.py "$@"
    xpm-seq.py     # PEP 723 single-file CLI (vendored)
  references/
    domain-reference.md
opencode/skills/xpm-seq/
  (identical mirror of claude/skills/xpm-seq/)
README.md          # this file
```

The two top-level directories mirror the same content for Claude Code (`~/.claude/skills/xpm-seq/`) and OpenCode (`$OPENCODE_CONFIG_DIR/skills/xpm-seq/`) runtimes respectively.

## Prerequisites

- [`uv`](https://docs.astral.sh/uv/) on `PATH`
- Python 3.9+ (managed automatically by `uv`)

`numpy` is the only runtime dep; it's resolved by the PEP 723 header in `bin/xpm-seq.py` on first invocation.

## Install

At SLAC LCLS this skill is centrally deployed — set `OPENCODE_CONFIG_DIR=/sdf/group/lcls/ds/dm/apps/dev/opencode` and it loads automatically; no per-user git clone needed.

For standalone use:

**Claude Code:**
```bash
git clone https://github.com/carbonscott/skill-xpm-seq.git /tmp/skill-xpm-seq
cp -r /tmp/skill-xpm-seq/claude/skills/xpm-seq ~/.claude/skills/xpm-seq
source ~/.claude/skills/xpm-seq/env.sh
```

**OpenCode:**
```bash
git clone https://github.com/carbonscott/skill-xpm-seq.git /tmp/skill-xpm-seq
cp -r /tmp/skill-xpm-seq/opencode/skills/xpm-seq "$OPENCODE_CONFIG_DIR/skills/xpm-seq"
source "$OPENCODE_CONFIG_DIR/skills/xpm-seq/env.sh"
```

## Verify

```bash
xpm-seq ratecalc 100 --json
```

The first invocation cold-caches `numpy` (~8 s); subsequent calls are fast.

## Usage (standalone)

Source the env file once per shell, then call any subcommand:

```bash
source <skill-dir>/env.sh

# Check whether a rate is an exact sub-harmonic of the 928,571 Hz base rate
xpm-seq ratecalc 120 --json

# Generate a periodic sequence
xpm-seq generate periodic --rates 100 --descriptions "beam" -o out.py --json

# Validate the generated script against the engine simulator
xpm-seq validate out.py --engine 0 --json
```

See `claude/skills/xpm-seq/SKILL.md` for the full workflow guidance and `claude/skills/xpm-seq/references/domain-reference.md` for the timing-system constants, sub-harmonic table, event-code mapping, and XPM PV list.

`env.sh` will source `env.local` if present (gitignored) for per-deployment overrides.

## Updating the vendored script

When `xpm-seq-tools` releases a new version, re-vendor `bin/xpm-seq.py` from the new pinned commit and bump the SHA in this README.

## Meta-deploy

Deploys via `carbonscott/deploy-opencode`'s `deploy.sh` reading `skills.manifest.json` — rsyncs `opencode/skills/xpm-seq/` into `/sdf/group/lcls/ds/dm/apps/dev/opencode/skills/xpm-seq/` with ps-data group + g+rX permissions. Manifest entry has `cron: null` and `central_data: null` — no scheduled refresh.

## License

Apache-2.0
