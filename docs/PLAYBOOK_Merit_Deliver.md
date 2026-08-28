# Playbook — Merit Deliver

**Tool 4 of 5 in the M.E.R.I.T. APP** · A friendly, no-jargon walkthrough of what this tool does and how to use it.

> Open this tool from the **M.E.R.I.T. APP** home menu, or click **"← Back to menu"** inside the app at any time to switch tools.
>
> New here? Start with the [Overview explainer](EXPLAINER_Overview.md). For where this tool sits in the monthly cycle, see the [Monthly Workflow explainer](EXPLAINER_Monthly_Workflow.md). Unfamiliar terms are in the [Glossary](EXPLAINER_Glossary.md).

---

## What this tool is for

Merit Deliver is the **last step before anything leaves the building**. It takes your finished raw file and does two jobs at once:

1. **Builds the client-facing deliverable** — the fixed 18-column file, in the right order, with the right names.
2. **Proves the deliverable is sound** — reconciles every total against the source, flags cells that hold live formulas instead of values, and classifies duplicate rows.

That second job is the point. Building the file is mechanical; the risk is that something changed on the way through and nobody noticed. Merit Deliver checks its own work and hands you the evidence.

Run it **after** corrections are applied and Merit Inspect is clean — see the [Monthly Workflow explainer](EXPLAINER_Monthly_Workflow.md).

---

## Before you start

You need **one raw Excel file** (`.xlsx` or `.xls`) — the corrected, final version. The tool reads the **first sheet**.

It must contain all 18 schema columns. If any are missing, the run stops and lists them — and where a near-match exists it suggests it (`'Media_Cost' -> did you mean 'Media Cost'?`), since a space-vs-underscore difference is the usual cause.

| The 18 deliverable columns |
|---|
| Channel · Date · Brand · Product_Line · Campaign · Prisma_Campaign_Secondary · Category · Raw_Partner · Audience · Package_Placement_Name · Daypart · Breakout · Retailer · Impressions · Clicks · Media_Cost · Video_Views · GRPs |

Two optional columns are carried into the **backup** copy if present: `Creative Name` and `Network_Name`. Missing ones come through blank with a warning rather than failing the run.

---

## Step-by-step workflow

### 1. Upload and generate

Drop in the file and click **Generate deliverable**. Everything happens in one pass — there's no separate preview step, because nothing is being changed. The tool is copying and checking, not editing.

### 2. Read the headline

The first thing you see is whether the deliverable is trustworthy:

| Message | Meaning |
|---|---|
| ✅ **"All metrics reconciled — nothing leaked"** | Every total in the deliverable matches the source exactly |
| ❌ **"Metric leak detected"** | A total doesn't match. **Do not send.** Check the reconciliation table |

Plus, where relevant: non-numeric metric cells, duplicate groups worth reviewing, and how many empty rows were excluded from the duplicate scan.

### 3. Check the reconciliation

Every metric — impressions, cost, GRPs — totalled by **Channel × Product Line**, source versus deliverable, with a status per line:

- **Green, "OK - Exact match"** — that slice came through intact.
- **Red, "CHECK: ..."** — a total moved, naming which metric.

Every line should be green. Row counts are shown too: **the deliverable must have exactly as many rows as the source.** Nothing is filtered or de-duplicated on the way through — a row that disappeared is a bug, not a feature.

### 4. Check the integrity scan

Counts cells that *look* like a number but aren't — text where a value should be. Those are delivered as blank, so a non-zero count means the deliverable is missing data the source appeared to have.

### 5. Check the formula scan

Flags cells holding a **live formula** (`=SUM(A1:A2)`) rather than a plain value.

> **Why this matters.** Excel shows you the *calculated result*, so a formula cell looks perfectly normal on screen. But if the file is re-saved without recalculating, or opened somewhere the linked source isn't available, those cells can silently go stale or blank — on the client's machine, after you've sent it. The scan reads the raw workbook to see the formula text itself, which is the only way to catch this.

You get a per-column summary and, on request, every flagged cell with its row number.

### 6. Review the duplicate groups

Rows identical across all 18 deliverable columns, sorted into three verdicts:

| Verdict | Meaning | Usual response |
|---|---|---|
| 🟢 **EXPECTED** | Identical in the deliverable, but they differ in a *benign* column that isn't part of it — Creative Name, CCD JTBD, Network_Name | Fine. Two creatives on the same placement legitimately collapse to identical delivery rows |
| 🟠 **REVIEW** | They differ in a column that **isn't** on the benign list | Look at it. Something meaningful distinguishes these rows and the deliverable doesn't carry it |
| 🔴 **TRUE DUP** | Identical across **every** column in the source, benign ones included | Genuinely the same row twice. Almost always a data problem |

Each group names the differentiating columns and the source Excel row numbers.

> Rows with **zero impressions and zero spend** are excluded from this scan — empty rows match each other trivially and would bury the real findings. The count of what was excluded is always shown.

### 7. Download

One `.zip` containing three files:

| File | What it's for |
|---|---|
| **RROI Delivery `{Brand} {Period}.xlsx`** | The deliverable. This is what goes to the client |
| **Backup RROI Delivery `{...}.xlsx`** | The same rows plus Creative Name and Network_Name — for your own diagnostics, not for sending |
| **RROI Delivery QA `{...}.xlsx`** | The evidence: summary, integrity scan, reconciliation, and every duplicate group |

Names are derived from the data — the brand (or "Multi-Brand") and the period the dates actually span.

---

## Important rules & restrictions

- **Every row is preserved.** The deliverable has exactly as many rows as the source. Nothing is dropped, merged or de-duplicated — duplicates are *reported*, never removed.
- **Nothing is recalculated.** Values are copied as they are. This tool does not correct data; that's [RROI Manual Backfill](PLAYBOOK_RROI_Manual_Backfill.md).
- **A reconciliation failure means stop.** A red line is the tool telling you the deliverable doesn't represent the source. Sending it anyway defeats the point of running this.
- **Missing columns fail the run.** No silent blank column — an empty column in a client file is worse than an error you can see.
- **Only the first sheet is read.**
- **Dates are normalized** to `m/d/yyyy` in the output.
- **Your session lives only in the browser tab.** Download the `.zip` before closing or reloading.

---

## What the messages mean

| Message | What it means | What to do |
|---|---|---|
| "These columns are in DELIVERABLE_SCHEMA but missing from the file" | A required column isn't there | Check the suggestion — it's usually a space-vs-underscore mismatch |
| "Metric leak detected — check the reconciliation table" | A total differs between source and deliverable | Don't send. Find the red line and investigate |
| "N non-numeric metric cell(s) — delivered as blank" | Text where a number should be | Fix upstream; those cells are empty in the deliverable |
| "N cell(s) hold a formula, not a plain value" | Live formulas found | Paste-as-values at source and re-run |
| "Backup column 'X' not found -> blank" | An optional backup column is absent | Harmless — only affects the backup copy |
| "These benign differentiators aren't real columns" | A configured benign column doesn't exist in this file | Check the spelling; duplicate classification may be stricter than intended |

---

## Quick recap

1. Upload the final corrected file → **Generate deliverable**.
2. Confirm **"All metrics reconciled — nothing leaked."** If not, stop and investigate.
3. Check the reconciliation is green throughout, and row counts match.
4. Check the integrity and formula scans.
5. Review duplicates — resolve every **REVIEW** and **TRUE DUP**.
6. Download the `.zip`; send the **deliverable**, keep the **backup** and **QA report**.
