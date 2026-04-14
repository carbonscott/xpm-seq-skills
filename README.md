# xpm-seq-skills

Claude/OpenCode skill for LCLS-II XPM timing sequence programming. Bundles a single-file PEP 723 CLI (`xpm-seq`) with three subcommands — `ratecalc`, `generate`, `validate` — for the workflow **check rates → generate → validate → deploy command**.

The bundled `bin/xpm-seq.py` is vendored from [`carbonscott/xpm-seq-tools`](https://github.com/carbonscott/xpm-seq-tools) (pinned commit `7706d60e`).

## Prerequisites

- [`uv`](https://docs.astral.sh/uv/) on your `PATH`
- Python 3.9+ (managed automatically by `uv`)

`numpy` is the only runtime dep; it's resolved by the PEP 723 header in `bin/xpm-seq.py` on first invocation.

## Install

**Claude Code:**
```bash
git clone https://github.com/carbonscott/xpm-seq-skills.git ~/.claude/skills/xpm-seq
```

**OpenCode:**
```bash
git clone https://github.com/carbonscott/xpm-seq-skills.git "$OPENCODE_CONFIG_DIR/skills/xpm-seq"
```

## Verify

```bash
source ~/.claude/skills/xpm-seq/env.sh
xpm-seq ratecalc 100 --json
```

The first invocation cold-caches `numpy` (~8 s); subsequent calls are fast.

## Usage (standalone)

Source the env file once per shell, then call any subcommand:

```bash
source ~/.claude/skills/xpm-seq/env.sh

# Check whether a rate is an exact sub-harmonic of the 928,571 Hz base rate
xpm-seq ratecalc 120 --json

# Generate a periodic sequence
xpm-seq generate periodic --rates 100 --descriptions "beam" -o out.py --json

# Validate the generated script against the engine simulator
xpm-seq validate out.py --engine 0 --json
```

See `SKILL.md` for the full workflow guidance and `references/domain-reference.md` for the timing-system constants, sub-harmonic table, event-code mapping, and XPM PV list.

## Layout

```
xpm-seq-skills/
├── SKILL.md              # Workflow guidance for the LLM
├── env.sh                # Adds bin/ to PATH, configures uv cache
├── bin/
│   ├── xpm-seq           # Bash wrapper: exec uv run --script xpm-seq.py "$@"
│   └── xpm-seq.py        # PEP 723 single-file CLI (vendored)
└── references/
    └── domain-reference.md
```

`env.sh` will source `env.local` if present (gitignored) for per-deployment overrides.

## Updating the vendored script

When `xpm-seq-tools` releases a new version, re-vendor `bin/xpm-seq.py` from the new pinned commit and bump the SHA in this README.

## License

Apache-2.0
