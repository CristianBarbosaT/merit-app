# M.E.R.I.T. APP — Overview

**Media Evaluation, Reconciliation & Integrity Tool**

A high-level explainer: what M.E.R.I.T. is, the problem it solves, and what sits inside it. Written to be read by someone who will never open the code.

> Hands-on instructions live in the five **playbooks** — see the [index](../README.md). Terms you don't recognise are in the [Glossary](EXPLAINER_Glossary.md). For licensing, hosting and data-security questions, see [Governance & Deployment](EXPLAINER_Governance_and_Deployment.md).

---

## In one paragraph

M.E.R.I.T. is an internal web app that takes the monthly media-delivery reporting cycle — a sequence of Excel checks, corrections and reconciliations that used to be done by hand — and turns it into five guided tools. Each tool takes the files the team already receives, applies the rules the team already follows, and returns the files the team already has to produce. Nothing about the business logic is new. What changed is that the logic now lives in one place, runs the same way every month, and explains itself as it goes.

---

## The problem it was built for

Every month, delivery data arrives from many sources — partner platforms, the TV buying team, the reporting platform — and has to be checked, corrected, reconciled and packaged before it reaches a client. Historically that meant a chain of manual Excel work:

| The manual reality | Why it hurt |
|---|---|
| **Rules lived in people's heads** and in ad-hoc spreadsheets | Two analysts could reach two different answers on the same file. Onboarding meant shadowing someone for months. |
| **Checks were done by eye** across tens of thousands of rows | Whatever got missed was found by the client, not by us. |
| **Corrections were typed by hand** | Every keystroke was a chance to fix one number and silently break another. |
| **Each step was re-derived monthly** | The same problems were re-solved from scratch, at the same cost, every cycle. |
| **Nothing recorded *why*** | A number could be defended only by whoever happened to produce it. |

The cost wasn't only time. It was **variance** — the same input could produce different output depending on who did the work and how tired they were.

---

## What M.E.R.I.T. changes

**One rulebook.** Business rules are written down once, in code, and applied identically every run. Where a rule is a lookup table that the team should own — TV network names, audience codes — it lives in an editable config file, not buried in logic.

**Findings, not verdicts.** The tools surface what looks wrong and say why. A human decides. Where a correction is genuinely unambiguous the tool proposes it; where it's a judgement call, the tool says so explicitly rather than guessing.

**Everything is explained.** Each output states what it did, what it skipped, and what it couldn't decide. A run is auditable after the fact by someone who wasn't there.

**Nothing is silently dropped.** If a value can't be mapped, the run stops and names it. A row that quietly vanishes from a reconciliation is worse than a run that fails loudly.

**No installation, no local files.** It runs in a browser. Files are processed in memory and handed straight back as downloads — nothing is written to a server.

---

## The five tools

The app opens on a menu. The numbering reflects the order they're typically used in a monthly cycle — see the [Monthly Workflow explainer](EXPLAINER_Monthly_Workflow.md).

### 1 · Merit Inspect — *the monthly QA pass*
Reads a raw delivery file and runs three layers of checking: **missing required fields**, **~15 value-level rules** (negative cost, audience codes that don't match the placement, placeholder rows, brand-specific taxonomy rules, and more), and a **spend-vs-delivery analysis** that catches money spent with nothing delivered, delivery with no money behind it, and metrics landing in the wrong column. Ends with a plain-English verdict — *action required*, *review suggested*, or *all clear* — and a ranked "what to fix first" list.

**→ [Playbook](PLAYBOOK_Merit_Inspect.md)**

### 2 · TV Data Standardization — *make TV files usable*
The TV team's spot-level files arrive in their own format: a report preamble, inconsistent network codes, and air dates written as `JUN28` with no year. This tool normalizes them — converting affidavit dates into real, year-aware dates, mapping networks and dayparts to consistent names, and scaling impressions to real units — and returns them per product, consolidated, or both.

**→ [Playbook](PLAYBOOK_TV_Data_Standardization.md)**

### 3 · RROI Manual Backfill — *fill known gaps, safely*
Sometimes a partner report is missing cost or impressions at row level even though the correct **total** for a group of rows is known. This tool distributes that total across the right rows — weighted by delivery, split evenly, or copied from another column — with a preview before anything is written, a queue so several backfills can be staged together, and a lock that refuses two operations targeting the same rows.

**→ [Playbook](PLAYBOOK_RROI_Manual_Backfill.md)**

### 4 · Merit Deliver — *build and check the client deliverable*
Builds the client-facing file to a fixed 18-column schema, then checks its own work: reconciles every metric total against the source (nothing may leak), flags cells holding live formulas instead of values, and classifies duplicate rows into *expected*, *worth reviewing*, and *genuinely identical*. Returns the deliverable, a backup copy with extra diagnostic columns, and a QA report.

**→ [Playbook](PLAYBOOK_Merit_Deliver.md)**

### 5 · Data Caveats Generator — *document what the data can't say*
Some gaps are real and can't be fixed — a placement with cost but genuinely no impressions for the month. Those need to be disclosed, not corrected. This tool finds them at placement-month level and writes one **Data Caveat Log** per brand, on the official corporate template, with its formatting and dropdowns intact.

**→ [Playbook](PLAYBOOK_Data_Caveats_Generator.md)**

---

## The design principles

These are the decisions that shaped the app, and the reasoning worth repeating in any write-up of it.

**1 · Fail loudly rather than silently.**
If a TV file contains a network that isn't in the mapping table, the run stops and names it. The alternative — passing the raw value through — would drop that network out of the comparison and quietly unbalance a reconciliation, and nobody would know. A run that fails is recoverable; a number that's quietly wrong is not.

**2 · Automate the unambiguous, surface the rest.**
The TV reconciliation logic proposes a correction only where the platform reports *nothing* and the TV files are unambiguous. Measured against a full cycle of an analyst's real historical corrections, those rules reproduced **every** spend zero-out the analyst made, with no false positives. The cases the rules deliberately skip are the ones where both sides report numbers that simply disagree — no threshold reliably separates those from ordinary measurement drift, so the tool lists them for a human instead of guessing.

**3 · Verify against reality, not against expectations.**
Each tool was tested against real production files, not only synthetic ones. That's how the spec's own control figures were found to be wrong in two places — a correction counted as applied that was actually a no-op, and a correction applied with no tracker entry. The tests assert the **measured** values, with the discrepancies documented.

**4 · Configuration belongs to the team.**
Network mappings, audience codes, and source-file schemas live in editable JSON/CSV files. Adding a new TV network is a config edit, not a code change.

**5 · The output should explain itself.**
Every run reports what it did, what it skipped and why. A correction that matched no rows says so. One whose rows were already at zero says "no change" rather than claiming success.

---

## What it is not

Being clear about the boundary is part of the value:

- **Not a replacement for judgement.** It narrows thousands of rows down to the handful that need a decision. It doesn't make the decision.
- **Not a data warehouse.** Files in, files out. Nothing is stored between sessions.
- **Not a scheduler.** It runs when someone runs it.
- **Not a single-click pipeline.** The tools are deliberately separate steps with a human between them — that's what makes each one auditable.

---

## Current status

All five tools are in use, covering the monthly cycle end to end. The codebase carries an automated test suite spanning synthetic edge cases and real-file regressions, plus a detailed engineering changelog (`estado_actual_app.md`) recording every behavioural decision and the reasoning behind it.

Two areas are built and tested but deliberately not yet exposed in the UI:

- **TV reconciliation and auto-correction** — the full compare-against-platform-export workflow, scoped out of the current tool to keep it to a simple upload-and-standardize flow.
- **Day-level caveat detection** — removed on purpose, so every caveat line reflects a genuine whole-month gap rather than a single off day inside an otherwise-complete month.

The app is distributed via SharePoint, with Git used for version history. Confirming organisational tool approval and switching off Streamlit's default usage telemetry are tracked as open items in [Governance & Deployment](EXPLAINER_Governance_and_Deployment.md#open-action-items).
