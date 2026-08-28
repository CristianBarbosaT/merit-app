# M.E.R.I.T. APP — The Monthly Workflow

A high-level explainer of **how the five tools fit together** across one monthly reporting cycle: what comes in, what each step decides, and what reaches the client.

> For what each tool *is*, see the [Overview](EXPLAINER_Overview.md). For how to operate one, see its playbook. Terms are defined in the [Glossary](EXPLAINER_Glossary.md).

---

## The cycle at a glance

```
   TV team files ──► 2 · TV Data Standardization ──┐
                                                    │
   Partner / platform delivery data ────────────────┴──► ONE RAW FILE
                                                              │
                                                              ▼
                                            1 · MERIT INSPECT  (what's wrong?)
                                                              │
                                        ┌─────────────────────┼─────────────────────┐
                                        ▼                     ▼                     ▼
                                 fixable at source     known total, missing    real gap, not
                                 (go fix the data)       rows to fill           fixable
                                                              │                     │
                                                              ▼                     ▼
                                              3 · RROI MANUAL BACKFILL    5 · DATA CAVEATS
                                                              │              GENERATOR
                                                              │                     │
                                                              ▼                     │
                                              1 · MERIT INSPECT (re-check)          │
                                                              │                     │
                                                              ▼                     ▼
                                                   4 · MERIT DELIVER  ──────► CLIENT
                                                    (build + verify)          (deliverable
                                                                             + caveat logs)
```

The numbering is the tools' menu order. The **flow** runs 2 → 1 → 3 → 1 → 4, with 5 running alongside.

---

## Step by step

### Before anything: assemble the month's data

Delivery data arrives from several places. Most of it is already in the standard reporting shape. **The TV team's files are not** — they come in the TV buying system's own export format.

**→ Run TV Data Standardization (Tool 2) first**, on the TV files only. It converts affidavit air dates into real dates, maps network and daypart names to the reporting platform's naming, and scales impressions to real units. Output: the same spots, in the shape everything else uses.

*Why first:* every later step assumes one consistent schema. Standardizing TV up front means the QA pass, the backfills and the deliverable all see one kind of row.

---

### Step 1 — Find out what's wrong

**→ Run Merit Inspect (Tool 1)** on the assembled raw file.

This is the diagnostic pass. It answers one question: *what in this file needs attention before it can go anywhere?* It reports three layers:

| Layer | What it finds | Typical response |
|---|---|---|
| **Missing required fields** | Rows with no Brand, no Category, no Audience… | Fix at source — these are filled in manually upstream |
| **Value-level rules** | Audience codes that contradict the placement, negative cost, placeholder rows, brand taxonomy breaches | Mostly fix at source; some are deliberate and can be accepted |
| **Delivery vs. spend** | Spend with zero delivery, delivery with zero spend, metrics in the wrong column, implausible CPM | Investigate — this is where real reporting problems surface |

It ends with a verdict — **action required**, **review suggested**, or **all clear** — and a ranked *what to fix first* list.

**The important habit:** Merit Inspect is a *diagnosis*, not a *fix*. It tells you which of the next three paths each problem belongs on.

---

### Step 2 — Route each finding

Every finding goes down exactly one of three paths.

#### Path A — Fixable at source
Most missing fields and taxonomy breaches. The row is wrong because something upstream was entered wrong. **Fix it upstream and re-pull**, so the correction survives into next month rather than being re-applied by hand every cycle.

#### Path B — The total is known, the rows aren't
A partner reports a correct campaign total but leaves cost or impressions blank at row level. The information isn't missing — it's just not distributed.

**→ Run RROI Manual Backfill (Tool 3).** Say what the total is, pick the rows, choose how to spread it (weighted by delivery, evenly, or copied from another column), preview it, queue it, run it.

#### Path C — A real gap that can't be filled
A placement genuinely had cost and genuinely delivered no impressions that month. There is no correct number to write. Inventing one would be fabrication.

**→ Run Data Caveats Generator (Tool 5).** It documents the gap on the official template so it's disclosed rather than hidden. See [*Correct vs. disclose*](#the-judgement-call-correct-vs-disclose) below.

---

### Step 3 — Re-check

**→ Run Merit Inspect again** on the corrected file.

Backfilling changes numbers, and changed numbers can trip checks that previously passed — a backfilled impressions figure can push a unit's CPM past the plausibility threshold, for instance. One re-run confirms the corrections landed and introduced nothing new.

---

### Step 4 — Build and verify the deliverable

**→ Run Merit Deliver (Tool 4).**

It builds the client-facing file to the fixed 18-column schema, then checks its own work:

- **Reconciliation** — every metric total, by channel and product line, must match the source. Nothing may leak between the raw file and the deliverable.
- **Formula scan** — flags cells holding a live formula instead of a plain value, which can silently go stale or blank on the recipient's machine.
- **Duplicate classification** — sorts visually identical rows into *expected*, *worth reviewing*, and *genuinely identical*.

Output: the deliverable, a backup copy carrying extra diagnostic columns, and a QA report — the evidence that the deliverable is sound.

---

### Alongside: the caveat logs

**Data Caveats Generator (Tool 5)** runs on the same delivery data, on its own track. Its output isn't the deliverable — it's the set of **Data Caveat Logs**, one per brand, that accompany it. Run it once the data is final: it should describe the gaps in what actually shipped.

---

## The judgement call: correct vs. disclose

The most consequential decision in the cycle, and the one worth being explicit about in any write-up.

|  | **Correct it** (Backfill) | **Disclose it** (Caveat) |
|---|---|---|
| **The situation** | The right number exists — it's just not on the rows | There is no right number to write |
| **Example** | Partner reports a $10,000 campaign total; the 40 daily rows are blank | A placement had spend and genuinely delivered zero impressions all month |
| **What you're asserting** | "We know what this should say, and we're distributing it" | "This is what the data says, and here's why it looks odd" |
| **Gets it wrong when…** | You invent a total that was never reported | You disclose a gap you could actually have filled |

**The test:** *can you point to where the correct number came from?* If yes, backfill. If you'd be estimating, caveat it. Fabricating a number that looks reasonable is the one outcome the whole workflow exists to prevent.

---

## What a healthy cycle looks like

- TV files standardize with **no unmapped networks** (any error names the network — add it to the config and re-run).
- Merit Inspect's second pass shows **fewer findings than the first**, and no new categories.
- Merit Deliver reports **all metrics reconciled — nothing leaked**.
- Every caveat line traces to a real, month-total gap you could explain to the client unprompted.
- Anything you chose *not* to fix was a decision someone made deliberately — not something that slipped through.

---

## Where the time goes

Worth knowing when planning a cycle: the tools are fast, and the thinking is not.

| Stage | Effort |
|---|---|
| Standardizing TV files | Seconds |
| Merit Inspect pass | Under a minute for a typical file |
| **Reviewing the findings and deciding what each one means** | **The bulk of the work** |
| Applying backfills | Minutes |
| Building and verifying the deliverable | Seconds |

M.E.R.I.T. removes the mechanical time — the eye-scanning, the manual arithmetic, the copy-paste — and concentrates the remaining effort on the decisions that genuinely need a person. That's the return: not that the month gets done faster, but that the time spent goes to judgement instead of clerical work.
