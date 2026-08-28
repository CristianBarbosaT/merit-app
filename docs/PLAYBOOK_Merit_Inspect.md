# Playbook — Merit Inspect

**Tool 1 of 5 in the M.E.R.I.T. APP** · A friendly, no-jargon walkthrough of what this tool does and how to use it.

> Open this tool from the **M.E.R.I.T. APP** home menu, or click **"← Back to menu"** inside the app at any time to switch tools.
>
> New here? Start with the [Overview explainer](EXPLAINER_Overview.md). For where this tool sits in the monthly cycle, see the [Monthly Workflow explainer](EXPLAINER_Monthly_Workflow.md). Unfamiliar terms are in the [Glossary](EXPLAINER_Glossary.md).

---

## What this tool is for

Merit Inspect is the **monthly QA pass**. You give it the raw delivery file; it tells you everything that looks wrong with it, ranked by what to deal with first.

It's a diagnosis, not a repair. Nothing in your file is modified — the tool reads it and reports. What you do about each finding is your call, and the [Monthly Workflow explainer](EXPLAINER_Monthly_Workflow.md#step-2--route-each-finding) covers how to route them.

It replaces the pass an analyst used to do by eye across tens of thousands of rows: checking that required fields are filled, that placement names line up with the taxonomy, that money spent actually delivered something, and that no metric landed in the wrong column.

---

## Before you start

You need **one raw delivery file** (`.xlsx` or `.xls`). The tool reads the **first sheet**.

It must contain these columns. If any are missing, the run stops and names them:

`Channel` · `Brand` · `Product_Line` · `Category` · `Raw_Partner` · `Audience` · `Retailer` · `Breakout` · `Campaign` · `Prisma_Campaign_Secondary` · `Package_Placement_Name` · `Media_Cost` · `Impressions` · `GRPs` · `Daypart` · `Network_Name` · `Date`

Two optional columns unlock extra checks when present: **`Creative Name`** (used by the Knorr Breakout rules) and **`Team`** (carried into the delivery analysis).

You don't need to supply an audience catalog — one is built in. See [Editing the reference data](#editing-the-reference-data) if you need a different one.

---

## Step-by-step workflow

### 1. Upload the file

Drop in the raw `.xlsx`. If you want to know what's about to be checked before running it, open **"What checks does this run?"** — the full reference is in the app itself, and mirrored in [The checks in full](#the-checks-in-full) below.

### 2. Run the checks

Click **Run QA checks**. A live status panel shows each stage as it goes — loading, row-level rules, delivery analysis, summary tables, writing the report — with timings. On a large file the rules pass is the slowest part.

### 3. Read the verdict first

The headline is one of three:

| Verdict | Meaning |
|---|---|
| 🔴 **ACTION REQUIRED** | At least one ERROR fired — something is definitely wrong |
| 🟠 **REVIEW SUGGESTED** | No ERRORs, but at least one REVIEW — worth a look, not necessarily wrong |
| 🟢 **ALL CLEAR** | Nothing fired |

Under it: how many rows need attention, how many delivery incidences there are, and the single **top cause**.

> **Missing required fields are counted separately** and don't drive the "top cause". They're filled in manually upstream, so they're a different kind of problem from a value that's actively wrong — mixing them would drown out the findings you can act on here.

### 4. Work the "What to fix first" list

Findings grouped and ranked by how much they matter. Start at the top. This is the list to work from — the detailed tables underneath are for looking up specifics once you know what you're chasing.

### 5. Review the detail

- **Row-level findings** — every flagged row, with its severity, the reason, and its **original Excel row number** so you can find it in your source file.
- **Delivery vs. spend** — one row per unit (a placement, a TV daypart+network, or an offline partner) per month, with what it spent and what it delivered.
- **Channel summary** — rows, cost, impressions and GRPs by channel and month. A sanity check on shape.
- **Offline presence** — whether Print / OOH / DOOH / Cinema showed up each month. A "missing" flag is expected if a brand doesn't buy those channels.
- **Coverage check** — how many rows each analysis path covered versus the file's total, confirming nothing silently fell through.
- **Checklist** — earliest and latest data date by Brand + Category + Master Channel.

### 6. Download the report

One Excel workbook with every table above on its own sheet, colour-coded, ready to share or attach to a ticket.

---

## The checks in full

### Layer 1 — Missing required fields

Counted, not listed row by row. All are **ERROR**.

`Channel` · `Brand` · `Product_Line` · `Category` · `Raw_Partner` · `Audience` · `Retailer` · `Breakout` are always required.

`Campaign` · `Prisma_Campaign_Secondary` · `Package_Placement_Name` are required **except on TV rows**, which legitimately don't carry them.

### Layer 2 — Value-level rules

Listed row by row, so you can go and look at each one.

| Check | What it catches | Severity |
|---|---|---|
| **Negative cost** | `Media_Cost` is below zero | ERROR |
| **Audience mismatch** | The placement's audience code, per the catalog, contradicts the `Audience` column | ERROR |
| **'Other Say' outside Social** | `Breakout` = "Other Say" on a channel that isn't Digital Social | ERROR |
| **TV audience incorrect** | On TV, `Audience` isn't what's expected for that brand (Hellmann's → A2564, Knorr → P2+) | ERROR |
| **Channel/format conflict** | Placement name mixes "Audio" and "Video" in the same block | ERROR |
| **X Corp partner missing** | The inventory code is Twitter/X but `Raw_Partner` doesn't end in "- X CORP" | ERROR |
| **Knorr Product_Line incorrect** | Product_Line should be Bouillon or Sides based on the evidence, and isn't | ERROR |
| **Knorr Breakout incorrect** | On Knorr + Social, the Creative Name implies a different Breakout than the row carries | ERROR |
| **Social channel mismatch** | The placement's inventory code implies Social but `Channel` doesn't say Digital Social, or vice versa | REVIEW |
| **Unexpected placement structure** | The placement name doesn't match the standardized block, so channel/audience couldn't be derived from it | REVIEW |
| **Placeholder placement** | Placement name contains "Dummy", "DELETE", "DO NOT USE" or "DNU" — possibly a row that should have been removed | REVIEW |
| **Audience code issue** | The code isn't in the catalog, or isn't a 4-digit code | REVIEW |
| **Partner missing companion** | Digital FEP + "THE TRADE DESK INC" without its expected companion partner row | REVIEW |
| **Knorr Product_Line / Breakout — needs review** | The evidence is missing or ambiguous, so the tool won't call it either way | REVIEW |

> **Why some Knorr rules are "needs review" rather than errors.** Where the Creative Name is absent or its keywords are ambiguous, the tool cannot determine the right answer — so it says so instead of guessing. That distinction is deliberate throughout the app: an ERROR means *this is wrong*, a REVIEW means *this needs a human*.

### Layer 3 — Delivery vs. spend

The most valuable layer, and the one hardest to do by eye.

Rows are grouped into **units**, and each unit is aggregated **by month**:

| Unit type | Grouped by | Expected metric |
|---|---|---|
| **Placement** (digital) | Placement name | Impressions |
| **TV** | Brand + Daypart + Network | Depends on brand — Knorr → Impressions, Hellmann's → GRPs |
| **Offline (Print)** | Channel + Raw_Partner | GRPs |
| **Offline (OOH / DOOH / Cinema)** | Channel + Raw_Partner | Impressions |

Each unit is then checked against the metric it's *supposed* to be measured by:

| Check | What it catches | Severity |
|---|---|---|
| **Spend but 0 delivery** | The unit had spend and delivered nothing that month | ERROR |
| **Delivery but 0 spend** | Delivered with no money behind it — often legitimate Added Value | REVIEW |
| **Metric cross-contamination** | A GRP-measured unit carrying impressions, or vice versa | REVIEW |
| **Unmapped TV metric** | A TV brand with no metric defined for it | REVIEW |
| **High CPM** | Above $50 per thousand impressions | REVIEW |

> **Why "expected metric" matters.** TV bought against GRPs and digital bought against impressions are not comparable, and a number in the wrong column is invisible if you only check that *something* is populated. Deciding up front what each unit should be measured by is what makes "spend with no delivery" a meaningful test rather than a guess.

### Layer 4 — Informational summaries

Not pass/fail — context to sanity-check the file's shape. Channel summary, offline presence, coverage check, and the delivery checklist.

---

## Reading severities

| | Meaning | What to do |
|---|---|---|
| **ERROR** | Definitely wrong by the rules as written | Fix it, or consciously decide it's an accepted exception |
| **REVIEW** | Might be fine, might not — the tool won't call it | Look at it. Many are legitimate (Added Value, an intentional placeholder) |

A file with zero REVIEW findings is unusual. The goal isn't an empty list — it's that **everything on the list was seen by someone who decided what it meant**.

---

## Editing the reference data

**Audience catalog** — `tools/config/audience_codes.csv`, two columns: `Code` (4 digits) and `Audience`. The built-in catalog carries 586 codes. To use a different approved list for one run, upload it under **"Advanced: use a different audience catalog"** — that override applies to that run only and doesn't change the bundled file.

If no catalog is available at all, the audience checks are **skipped** and the tool says so — it doesn't fail, and it doesn't pretend they passed.

**Brand-specific rules** (TV audience per brand, TV delivery metric per brand, the Knorr taxonomy keywords, the CPM threshold) live at the top of `tools/merit_inspect.py`, grouped and commented for editing. Changing a threshold or adding a brand is a one-line edit; it needs a developer only in the sense that it's in a `.py` file.

---

## Things worth knowing

- **Nothing is modified.** Your file is read, never written. Re-running is always safe.
- **Only the first sheet is read.** If your workbook has staging tabs, make sure the data is first.
- **Rows can fire several rules.** A row is listed once with its reasons joined, taking the most severe.
- **Severity ranking drives ordering**, not row order — the worst findings surface first.
- **Excel row numbers are given** for every row-level finding, so you can navigate straight to it.
- **The delivery analysis works on monthly totals**, so a unit that overspent one week and underdelivered the next won't be flagged if the month nets out.
- **Your session lives only in the browser tab.** Download the report before closing or reloading.

---

## What the messages mean

| Message | What it means | What to do |
|---|---|---|
| "Missing expected columns: [...]" | The file doesn't carry a column the checks need | Check you uploaded the right file and that headers weren't renamed |
| "No audience catalog found — audience checks skipped" | Neither a bundled nor an uploaded catalog was available | Restore `tools/config/audience_codes.csv`, or upload one |
| "TV brand has no defined delivery metric" | A TV brand isn't in the brand→metric map | Add it, so its delivery can actually be checked |
| "High CPM: $X per 1,000 impressions" | Cost per thousand is above the threshold | Usually a data problem — check impressions weren't under-reported |
| "Measured by GRPs but has impressions" | A GRP-measured unit carries impressions too | Check whether the metric landed in the wrong column upstream |

---

## Quick recap

1. Upload the raw delivery file → **Run QA checks**.
2. Read the **verdict** and the **top cause**.
3. Work the **"What to fix first"** list top-down.
4. Use the detail tables to look up specific rows (they carry Excel row numbers).
5. Download the report.
6. Route each finding: fix at source, backfill, or caveat — see the [Monthly Workflow explainer](EXPLAINER_Monthly_Workflow.md#step-2--route-each-finding).
7. After corrections, **run it again** to confirm they landed and introduced nothing new.
