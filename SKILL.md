---
name: xpm-seq
description: >-
  Assist with LCLS-II XPM timing sequence programming. Use when: creating timing
  sequences, calculating beam rates or bucket periods, generating sequence scripts,
  validating sequences, programming XPM engines, working with event codes, or
  deploying via seqprogram.py. Trigger on: XPM, timing sequence, rate calculation,
  bucket period, sub-harmonic, event code, sequence engine, xpm-ratecalc,
  xpm-generate, xpm-validate, seqprogram, LCLS-II triggers, beam rate.
argument-hint: "<rates in Hz or natural language request>"
user-invocable: true
---

# XPM Timing Sequence Workflow

Three CLI tools: `xpm-ratecalc`, `xpm-generate`, `xpm-validate`.
Always follow the workflow: **check rates → generate → validate → deploy command**.

## Step 1: Prerequisites

Verify the tools are installed:

```bash
which xpm-ratecalc 2>/dev/null || echo "NOT_INSTALLED"
```

If not installed, tell the user:

> The xpm-seq tools are not on your PATH. Install with:
> ```
> uv tool install git+https://github.com/carbonscott/xpm-seq-tools.git
> ```

Do not proceed until the tools are available.

## Step 2: Understand the Request

Parse the user's input into structured parameters:

- **Rates** (Hz) or **periods** (bucket counts)
- **Pattern type**: periodic (steady repeating rates) or train/burst (grouped pulses)
- **Engine/XPM** preferences (if mentioned)
- **Description labels** for each event code

If unclear, ask:
- "What rates do you need?" (if no rates given)
- "Periodic pattern or burst/train?" (if ambiguous)
- Defer engine/XPM questions to the deployment step

## Step 3: Rate Feasibility

Always run ratecalc first, always with `--json`:

```bash
xpm-ratecalc <rate1_hz> <rate2_hz> ... --json
```

Parse the JSON output and check each rate:

- **`exact_subharmonic: true`** and **`error_pct < 1%`** → proceed
- **`error_pct > 1%`** → warn the user. Show the actual achievable rate and error.
  Ask if they want to proceed or pick a nearby exact sub-harmonic.
- To show alternatives: `xpm-ratecalc --list --json` or read
  [references/domain-reference.md](references/domain-reference.md) for the full table

For period-based requests, use reverse lookup:

```bash
xpm-ratecalc --period <p1> <p2> ... --json
```

## Step 4: Generate Script

### Periodic patterns

```bash
xpm-generate periodic --rates <r1> <r2> \
  --descriptions "<desc1>" "<desc2>" \
  -o <filename>.py --json
```

Additional flags when needed:
- `--periods <p1> <p2>` instead of `--rates` (mutually exclusive)
- `--start <offset1> <offset2>` for bucket offsets (default all 0)
- `--merge` to put all triggers on one event code
- `--no-resync` to disable resync marker
- `--repeat N` (-1 = infinite, default)

### Train/burst patterns

```bash
xpm-generate train --train-spacing <N> --bunch-spacing <M> \
  --bunches-per-train <K> --description "<desc>" \
  -o <filename>.py --json
```

Additional flags: `--start-bucket`, `--charge`, `--repeat`, `--notify`.

### After generation

The `--json` flag emits a summary to **stderr** (not stdout). Parse it for:
- `instruction_count` — warn if > 1500, error if > 2048
- `actual_rates_hz` — confirm they match expectations
- `lcm_period` — the combined repeat period

Name output files descriptively: `33k_35k.py`, `burst_100x1.py`.

## Step 5: Validate

Always validate after generating:

```bash
xpm-validate <filename>.py --engine <N> --json
```

Use `--engine 0` as default if the user hasn't specified an engine yet.

Check the JSON output:
- `valid: true` — good to deploy
- `valid: false` — show warnings, explain the issue
- Verify `rate_hz` values match what ratecalc reported
- Common warnings:
  - **Instruction count > 2048** — script cannot be deployed; reduce complexity
  - **Counter conflicts** — overlapping loops on same conditional counter (0-3)

## Step 6: Deployment Command

**Do NOT execute this.** Provide the command for the user to run on S3DF:

```bash
python seqprogram.py --seq <ENGINE>:<script>.py --pv <XPM_PV>
```

If the user hasn't specified engine or XPM PV, ask:
- Which hutch/XPM? Common PVs:
  - `DAQ:NEH:XPM:0` — SXR hutch
  - `DAQ:NEH:XPM:2` — NEH hutch
- Which engine (0-7)? Warn: **engines 4-7 on SXR XPM (DAQ:NEH:XPM:0) are often
  reserved for laser triggers** (event codes 272-287). Don't reassign without confirming.

Engine N controls event codes `256 + 4*N` through `259 + 4*N`.

Multiple engines in one command:
```bash
python seqprogram.py --seq 4:script1.py --seq 5:script2.py --pv DAQ:NEH:XPM:0
```

Remind the user: this must run on S3DF where `seqprogram.py` and EPICS PVA are available.

## Step 7: Error Recovery

| Problem | Fix |
|---------|-----|
| `xpm-ratecalc` returns no results | Check that rates are positive numbers |
| `xpm-generate` exits with error | Check `--rates`/`--periods` mutual exclusivity; `--descriptions` count must match |
| Instruction count > 2048 | Reduce number of rates, or use `--merge` for periodic |
| Validation rates don't match ratecalc | Likely a bug — report the discrepancy |
| Counter conflict warning | Restructure loops to use different counters (max 4) |

## Quick Reference

For domain lookup tables (sub-harmonic rates, event code mapping, instruction set,
marker table, XPM PVs), read [references/domain-reference.md](references/domain-reference.md).

$ARGUMENTS
