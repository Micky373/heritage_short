# Costs and usage

## Current evidence

The `runs.jsonl` snapshot used for this report contains 31 logical call records
dated 2026-11-26. A record wraps one call including its internal retry sequence;
it is not necessarily one network attempt.

| Model | Records | Successful | Errors | Median recorded latency | p95 recorded latency | `cost_usd_est` |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `gemini-2.5-flash` | 3 | 0 | 3 | 3.75 s | 4.00 s | null |
| `gemini-3.8-flash` | 4 | 0 | 4 | 26.94 s | 30.79 s | null |
| `gemini-3.8-flash-tts` | 24 | 19 | 5 | 5.32 s | 9.29 s | null |

All 31 records have `cost_usd_est: null`; these figures do **not** establish a
zero-dollar total. The actual billed amount depends on the account's plan,
current provider pricing, and whether requests were covered by free quota.
Check the provider's current usage/billing page before reporting a dollar
figure. Do not infer price from this log.

## Local stages

The reference sheet and keyframes are rendered locally from SVG; moving shots
and assembly use FFmpeg; the placeholder score is synthesized locally. These
stages make no Gemini calls. They have no model API charge, although this report
does not estimate electricity, hardware, or engineering time.

## Improving cost accounting

The pipeline should only populate `cost_usd_est` when a source and method for
the estimate are recorded (for example, provider usage export or a dated,
documented price table). Preserve `null` when the cost cannot be verified.
Record model, stage, attempt policy, and usage units without logging API keys.
The current request records include prompt parameters, so review them for
personal or confidential text before sharing the tracked `runs.jsonl`.
