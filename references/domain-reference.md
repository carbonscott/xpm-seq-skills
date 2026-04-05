# XPM Timing System Domain Reference

## Timing Constants

| Constant | Value |
|----------|-------|
| Buckets per frame | 910,000 |
| Frame period | 0.98 seconds |
| Base rate | 928,571.43 Hz |
| Factorization | 2^4 x 5^4 x 7 x 13 |
| Exact sub-harmonic count | 100 (divisors of 910,000) |

## Fixed-Rate Markers (LCLS-II)

| Marker | Name | Interval (buckets) | Rate |
|--------|------|--------------------|------|
| 0 | 1H | 910,000 | ~1.02 Hz |
| 1 | 10H | 91,000 | ~10.2 Hz |
| 2 | 100H | 9,100 | ~102 Hz |
| 3 | 1kH | 910 | ~1.02 kHz |
| 4 | 10kH | 91 | ~10.2 kHz |
| 5 | 70kH | 13 | ~71.4 kHz |
| 6 | 910kH | 1 | ~929 kHz |

The default sync marker for generated sequences is `910kH` (marker 6, every bucket).

## All 100 Exact Sub-Harmonic Rates

Every rate that divides evenly into 910,000 buckets per frame:

| Period | Rate (Hz) | | Period | Rate (Hz) | | Period | Rate (Hz) |
|-------:|----------:|-|-------:|----------:|-|-------:|----------:|
| 1 | 928,571.43 | | 175 | 5,306.12 | | 3,640 | 255.10 |
| 2 | 464,285.71 | | 182 | 5,102.04 | | 4,375 | 212.24 |
| 4 | 232,142.86 | | 200 | 4,642.86 | | 4,550 | 204.08 |
| 5 | 185,714.29 | | 208 | 4,464.29 | | 5,000 | 185.71 |
| 7 | 132,653.06 | | 250 | 3,714.29 | | 5,200 | 178.57 |
| 8 | 116,071.43 | | 260 | 3,571.43 | | 6,500 | 142.86 |
| 10 | 92,857.14 | | 280 | 3,316.33 | | 7,000 | 132.65 |
| 13 | 71,428.57 | | 325 | 2,857.14 | | 7,280 | 127.55 |
| 14 | 66,326.53 | | 350 | 2,653.06 | | 8,125 | 114.29 |
| 16 | 58,035.71 | | 364 | 2,551.02 | | 8,750 | 106.12 |
| 20 | 46,428.57 | | 400 | 2,321.43 | | 9,100 | 102.04 |
| 25 | 37,142.86 | | 455 | 2,040.82 | | 10,000 | 92.86 |
| 26 | 35,714.29 | | 500 | 1,857.14 | | 11,375 | 81.63 |
| 28 | 33,163.27 | | 520 | 1,785.71 | | 13,000 | 71.43 |
| 35 | 26,530.61 | | 560 | 1,658.16 | | 14,000 | 66.33 |
| 40 | 23,214.29 | | 625 | 1,485.71 | | 16,250 | 57.14 |
| 50 | 18,571.43 | | 650 | 1,428.57 | | 17,500 | 53.06 |
| 52 | 17,857.14 | | 700 | 1,326.53 | | 18,200 | 51.02 |
| 56 | 16,581.63 | | 728 | 1,275.51 | | 22,750 | 40.82 |
| 65 | 14,285.71 | | 875 | 1,061.22 | | 26,000 | 35.71 |
| 70 | 13,265.31 | | 910 | 1,020.41 | | 32,500 | 28.57 |
| 80 | 11,607.14 | | 1,000 | 928.57 | | 35,000 | 26.53 |
| 91 | 10,204.08 | | 1,040 | 892.86 | | 36,400 | 25.51 |
| 100 | 9,285.71 | | 1,250 | 742.86 | | 45,500 | 20.41 |
| 104 | 8,928.57 | | 1,300 | 714.29 | | 56,875 | 16.33 |
| 112 | 8,290.82 | | 1,400 | 663.27 | | 65,000 | 14.29 |
| 125 | 7,428.57 | | 1,456 | 637.76 | | 70,000 | 13.27 |
| 130 | 7,142.86 | | 1,625 | 571.43 | | 91,000 | 10.20 |
| 140 | 6,632.65 | | 1,750 | 530.61 | | 113,750 | 8.16 |
| | | | 1,820 | 510.20 | | 130,000 | 7.14 |
| | | | 2,000 | 464.29 | | 182,000 | 5.10 |
| | | | 2,275 | 408.16 | | 227,500 | 4.08 |
| | | | 2,500 | 371.43 | | 455,000 | 2.04 |
| | | | 2,600 | 357.14 | | 910,000 | 1.02 |
| | | | 2,800 | 331.63 | | | |
| | | | 3,250 | 285.71 | | | |
| | | | 3,500 | 265.31 | | | |

## Engine to Event Code Mapping

Each XPM has 8 sequence engines (0-7). Each engine controls 4 event codes.
Formula: `event_code = 256 + (engine * 4) + bit` where bit is 0-3.

| Engine | Event Codes | Notes |
|--------|-------------|-------|
| 0 | 256-259 | |
| 1 | 260-263 | |
| 2 | 264-267 | |
| 3 | 268-271 | |
| 4 | 272-275 | Often reserved for laser triggers on SXR XPM |
| 5 | 276-279 | Often reserved for laser triggers on SXR XPM |
| 6 | 280-283 | Often reserved for laser triggers on SXR XPM |
| 7 | 284-287 | Often reserved for laser triggers on SXR XPM |

Event codes 0-255 are TPG-level (not per-engine).

## Instruction Set

| Instruction | Purpose | Key Constraints |
|-------------|---------|-----------------|
| `FixedRateSync(marker, occ)` | Wait for `occ` occurrences of fixed-rate marker | `occ` max 4095 (12-bit) |
| `ACRateSync(timeslotm, marker, occ)` | Wait for AC-rate marker occurrences | `occ` max 4095 |
| `ControlRequest(codes)` | Assert event codes (list of bit indices) | |
| `BeamRequest(charge_pC)` | Request beam with specified charge | |
| `Branch.unconditional(target)` | Jump to instruction index | |
| `Branch.conditional(counter, target, count)` | Loop: decrement counter, branch if > 0 | 4 counters (0-3) per engine |
| `CheckPoint` | Allows sequence restart from this point | |

**Macros** (expand to multiple instructions):
- `Wait(marker, occ)` — expands `occ` into nested loops using FixedRateSync
- `WaitA(marker, occ)` — same for AC-rate markers

**Limits**: 2048 instructions per engine cache. 4 conditional counters (0-3) per engine.

## Common XPM PVs

| PV | Location | Notes |
|----|----------|-------|
| `DAQ:NEH:XPM:0` | SXR hutch | Engines 4-7 often reserved for laser triggers |
| `DAQ:NEH:XPM:2` | NEH hutch | |

Always ask the user which PV and engine to use. Do not assume.

## seqprogram.py Deployment

Runs on **S3DF only** (requires EPICS PVA access to the timing system).

```bash
# Single engine
python seqprogram.py --seq <ENGINE>:<SCRIPT>.py --pv <XPM_PV>

# Multiple engines
python seqprogram.py --seq 4:script1.py --seq 5:script2.py --pv DAQ:NEH:XPM:0
```

Generated scripts use `from psdaq.seq.seq import *` which is available in the
S3DF psdaq environment where `seqprogram.py` runs.
