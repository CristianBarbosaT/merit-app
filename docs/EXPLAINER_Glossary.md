# M.E.R.I.T. APP — Glossary

Plain-English definitions of the terms used across the app and its documentation. Written for someone new to the team or new to media reporting.

> For what the app does, see the [Overview](EXPLAINER_Overview.md). For how the tools fit together, see the [Monthly Workflow](EXPLAINER_Monthly_Workflow.md).

---

## The app

**M.E.R.I.T.** — Media Evaluation, Reconciliation & Integrity Tool. The internal web app covering the monthly delivery-reporting cycle in five tools.

**Playbook** — a hands-on guide to operating one tool. One per tool.

**Explainer** — a high-level document about the app as a whole, rather than any single tool. This is one.

**Tool** — one of the five self-contained functions on the home menu. Each does one job and hands off to the next through files, not through shared state.

---

## Media & delivery

**Delivery** — what a media buy actually produced: impressions, GRPs, video views. As opposed to **spend**, which is what it cost. The central question in most checks is whether the two are consistent.

**Impressions** — the number of times an ad was served. The standard delivery metric for digital, OOH, DOOH and Cinema.

**GRPs (Gross Rating Points)** — the traditional broadcast measure of audience reach, as a percentage of a target population. The standard delivery metric for Print, and for some brands on TV. **Not comparable to impressions** — which is exactly why the app tracks an *expected metric* per unit.

**Expected metric** — the metric a given unit is *supposed* to be measured by. Deciding this up front is what makes "spend but no delivery" a meaningful test: without it, a unit reporting GRPs when it should report impressions looks populated and passes.

**Metric cross-contamination** — a unit carrying the metric it *isn't* measured by (a GRP-measured unit with impressions in it). Usually means a value landed in the wrong column upstream.

**CPM** — cost per thousand impressions. `cost ÷ impressions × 1000`. A CPM far above normal usually means impressions were under-reported rather than that the buy was genuinely expensive — which is why an implausible CPM is treated as a data-quality signal.

**CPP** — cost per point, the GRP-based equivalent of CPM.

**Added Value** — delivery a partner provided at no charge. Why "delivery with zero spend" is a REVIEW rather than an ERROR: it's often entirely legitimate.

**Channel** — the medium: Digital Social, Digital Video, Digital FEP, Digital Display, Digital Audio, TV, Print, OOH, DOOH, Cinema.

**Master Channel** — a coarser grouping where all the Digital sub-channels collapse into one "Digital". Used in summaries where the detail would be noise.

**Offline / Traditional (non-TV)** — Print, OOH, DOOH and Cinema. Grouped by partner rather than by placement, because they don't carry placement names.

**OOH / DOOH** — Out Of Home (billboards, transit) and its digital equivalent.

**FEP** — Full Episode Player. Long-form video inventory on broadcaster platforms.

**Daypart** — the time-of-day block a TV spot ran in (Prime, Early Morning, News, Cable Sports…). Part of what identifies a TV unit.

**Placement** — the specific ad slot bought. `Package_Placement_Name` is a long structured string encoding channel, format, audience, buy type and more — which is why several rules read information *out of* it and check it against the columns.

**Breakout** — a campaign-strategy dimension. Values like "Other Say" and "Brand Say" distinguish creative approaches, and are only valid on certain channels.

**Product Line** — the sub-brand grouping (for Knorr: Bouillon or Sides). Derivable from several sources, which is why it has its own rules.

**Retailer** — the retail partner a commerce campaign is tied to. Often `(all)`.

**Audience code** — the 4-digit code inside a placement name identifying the target audience, resolved through the audience catalog (`0005` → "Demo: Women 13-24"). When the code and the `Audience` column disagree, one of them is wrong.

---

## Reporting & reconciliation

**RROI** — the standard delivery-data schema this reporting process is built around. "RROI file" means data in that shape.

**LCA** — a second delivery-file format the Data Caveats tool accepts. Same underlying fields as RROI plus extra columns, with `Media Cost` and `Video Views` spelled with a space instead of an underscore. Selected explicitly before upload, since the two are not interchangeable.

**Deliverable** — the client-facing file. A fixed 18-column schema built by [Merit Deliver](PLAYBOOK_Merit_Deliver.md).

**Backup deliverable** — the same rows plus diagnostic columns (Creative Name, Network_Name). For internal use; not sent to the client.

**Reconciliation** — checking that two versions of the same data agree. In [Merit Deliver](PLAYBOOK_Merit_Deliver.md) it means source totals versus deliverable totals; in the TV context it means the TV team's files versus the reporting platform's export.

**Leak** — a total that changed between source and deliverable. Always a defect.

**Backfill** — distributing a known total across rows that are missing it. Weighted by delivery, split evenly, or copied from another column. See [RROI Manual Backfill](PLAYBOOK_RROI_Manual_Backfill.md).

**Data Caveat** — a documented, disclosed gap: something the data genuinely can't say, recorded on the official template rather than papered over. See [Data Caveats Generator](PLAYBOOK_Data_Caveats_Generator.md).

**Null impressions / Null cost** — the two caveat patterns. A placement-month with cost but no impressions, or impressions but no cost. Detected on the **whole month's total**, never a single day.

**Placement-month** — the grain caveat detection works at: one placement, one month. A single off day inside an otherwise-complete month is not a caveat.

**INC#** — the ticket number identifying a caveat submission, used in the output tab names.

---

## TV

**Affidavit date (AFFID DATE)** — the date a station **certified a spot actually aired**, as opposed to the date it was *planned* to air. Written as `JUN28` — month and day, **no year**.

> This is the single most important concept in [TV Data Standardization](PLAYBOOK_TV_Data_Standardization.md). The reporting platform files TV activity by affidavit date, not planned date, and make-goods and reschedules mean the two often differ. On real files, matching on affidavit date makes spend agree on **96.5%** of network-days; matching on planned date agrees on **40%**.

**Effective date** — the affidavit date converted into a real, year-aware date, falling back to the planned date when the affidavit is blank (about 5% of rows).

**Make-good** — a replacement spot a station runs when the original didn't air as booked. A common reason affidavit and planned dates differ.

**Re-pull** — a fresh export of the same period, usually because final audience figures have arrived. When two files cover the same product, the app keeps the **newer** one — an older pull can carry zeroed-out audience data.

**Spot** — one airing of one TV ad. TV files are spot-level: one row per airing.

**Network** — the channel a spot aired on. Raw files use codes (`ACCN ACC NETWORK`) that must be mapped to clean names (`ACC NETWORK`) via an explicit table, since the transformation isn't always mechanical.

**Estimate name** — the TV buying system's label for a buy, mapped to a clean name and a daypart.

**Phantom spend** — cost recorded against a network that delivered nothing on either side. One of the two auto-correctable patterns in the (built but not yet exposed) TV reconciliation logic.

---

## Data quality

**ERROR** — definitely wrong by the rules as written. Fix it, or consciously accept it as an exception.

**REVIEW** — might be fine, might not; the tool won't call it. Needs a person. A REVIEW is not a lesser error — it's a *different kind* of finding.

**Verdict** — Merit Inspect's headline: **ACTION REQUIRED** (an ERROR fired), **REVIEW SUGGESTED** (only REVIEWs), or **ALL CLEAR**.

**Placeholder placement** — a row whose placement name contains "Dummy", "DELETE", "DO NOT USE" or "DNU". Often should have been removed before delivery.

**Duplicate — EXPECTED / REVIEW / TRUE DUP** — rows identical across the deliverable's columns, classified by *what distinguishes them in the source*. Benign difference → EXPECTED; meaningful difference → REVIEW; no difference at all → TRUE DUP.

**Benign differentiator** — a column whose variation doesn't make two delivery rows meaningfully different (Creative Name, CCD JTBD, Network_Name). Two creatives on one placement legitimately produce identical delivery rows.

**Formula cell** — a cell holding `=SUM(...)` rather than a value. Looks normal on screen but can go stale or blank elsewhere, which is why it's flagged before a file is sent.

**Masked gap** — a day-level gap hidden by a complete month total. Reported as an FYI by validation, but never generated as a caveat: detection is month-total only.

---

## Technical

**Streamlit** — the Python framework the app is built in. It's why it runs in a browser with no installation.

**Session state** — what the app remembers while a browser tab is open. **Nothing persists after the tab closes** — always download before closing or reloading.

**In-memory processing** — files are handled in RAM and returned as downloads; nothing is written to a server or shared between users.

**Template** — the official corporate Excel file the Data Caveat Logs are written into, preserving its formatting, table structure and dropdowns.

**Config file** — reference data kept outside the code so the team can edit it: `tools/tv_mappings.json` (TV networks, dayparts) and `tools/config/audience_codes.csv` (audience codes).

**`estado_actual_app.md`** — the engineering changelog: every behavioural decision, why it was made, and what was verified against real data. The technical counterpart to these documents.
