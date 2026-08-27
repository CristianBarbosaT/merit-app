# M.E.R.I.T APP — RROI Manual Backfill User Guide

A friendly, no-jargon walkthrough of what this tool does and how to use it.

> This app now opens on a **home menu** with more than one tool. This guide covers **RROI Manual Backfill** — open it from the menu, or from inside the app click **"← Back to menu"** at any time to switch tools. For the other tools see `DATA_CAVEATS_GUIDE.md` and `TV_STANDARDIZATION_GUIDE.md`.

---

## What this tool is for

Every month, your partner reports (Pinterest, Meta, TV networks, etc.) sometimes arrive with a **missing cost or missing impressions** at the detailed row level, even though you know the **correct total** for a specific group of rows (a campaign, a package, a TV daypart, etc.).

Instead of typing numbers in by hand, this tool fills them in for you. Most often it splits a known total **proportionally to how much delivery each row actually had** — a row that delivered more impressions gets a bigger share of the cost — and guarantees the pieces add back up exactly to the total you entered. It can also spread a total evenly, or copy values straight from another column when that's the right answer.

You do this one group of rows at a time, review each one before it touches your data, and only apply everything at the very end — so you're always in control.

---

## Before you start

You need an Excel file (`.xlsx`) with the same column structure you already work with — the tool reads it directly, no changes needed on your end. It can contain up to a few months of data, and both TV and Digital rows mixed together in the same sheet.

Two things the tool needs to work properly:
- A **Channel** column, so it can tell Digital rows apart from TV rows.
- All the columns used by whichever mode you plan to use (see [File requirements](#file-requirements) below).

If a file is missing something a mode needs, the tool will tell you exactly what's missing — and the other mode will usually still work fine.

---

## Step-by-step workflow

### 1. Upload your file

Open the app in your browser and use the upload box to select your `.xlsx` file.

### 2. Pick the working sheet (if needed)

If your file has more than one sheet (tab), you'll be asked which one to work with. If it only has one, the tool uses it automatically. Click **Load sheet** to continue.

### 3. Say what you're backfilling

**Mode** — **Digital** or **TV**. You can switch back and forth freely during your session.

If you pick **Digital**, you then choose which kind of Digital buy you're adjusting. The tool works this out from each row's placement name and partner, so you don't have to tag anything yourself:

| Type | What lands here |
|---|---|
| **Social** | Placement contains `UNE` **and** the partner is a social platform (Facebook, TikTok, Reddit, Pinterest, Snapchat, or anything from X Corp) |
| **Reserve** | Placement contains `UNE` on any other partner (Amazon, Peacock, Hulu, publishers…) |
| **Programmatic** | Placement contains `UUT` (YouTube, The Trade Desk and friends) |

Rows whose placement has neither `UNE` nor `UUT` — usually bonus or added-value lines — can't be backfilled here. The tool tells you how many of those your file has when you load it.

**Social only:** you also choose whether to select rows **by Package** or **by Placement**. By package you'll also need to fill in CCD JTBD, Audience and Breakout; by placement you just pick the one placement and that's it.

### 4. Choose how the numbers should be calculated

First pick the **field to backfill** — Media Cost or Impressions — then the **operation**. Each one has a short description under it in the app.

**For Media Cost:**

| Operation | What it does | Needs a target? |
|---|---|---|
| **Weighted by impressions** | Splits your target across the rows, proportional to each row's impressions. The classic backfill. | Yes |
| **Even allocation across rows** | Divides your target equally — every row gets exactly the same amount. | Yes |
| **Copy from Delivered Spend (Reconciled)** | Replaces Media Cost with that column's value, row by row. | No |
| **Copy from Delivered Spend (Prisma)** | Same, from the Prisma column. | No |

**For Impressions:**

| Operation | What it does | Needs a target? |
|---|---|---|
| **Weighted** | Splits your target proportional to the impressions already there, so the day-to-day delivery shape stays the same. If the rows have no impressions at all, it weights by Media Cost instead. | Yes |
| **Copy from Weighted Planned Units** | Replaces Impressions with that column's value, row by row. | No |

The **copy** operations don't ask you for a number at all — the values come straight from the other column. The target box simply disappears when you pick one.

### 5. Pick which rows — in order

The filters are **numbered**, and you fill them **top to bottom**. Which ones you get depends on what you chose in step 3:

- **Social (by package)** — 1 Month, 2 Campaign, 3 Partner, 4 Package, 5 CCD JTBD, 6 Audience, 7 Breakout
- **Social (by placement)** — 1 Month, 2 Campaign, 3 Partner, 4 Placement
- **Reserve** — 1 Month, 2 Campaign, 3 Partner\*, 4 Audience\*
- **Programmatic** — 1 Month, 2 Campaign, 3 Partner, 4 Channel\*, 5 Package, 6 CCD JTBD\*, 7 Audience\*
- **TV** — 1 Month, 2 Brand, 3 Audience, 4 Daypart, 5 Network

**Each filter only offers what's still possible given the ones above it.** Until you answer a filter, everything below it stays greyed out with a *"Pick [filter] first"* message. So on Social, CCD JTBD, Audience and Breakout show **nothing** until you've chosen a Package — and once you do, they only list the values that actually exist for *that* package, instead of every value in the file.

That's deliberate: it means you can't build a combination that doesn't exist in your data, and the dropdowns stay short instead of making you hunt through dozens of irrelevant options.

If you change a filter higher up, anything below it that no longer applies is cleared so you can pick again.

Filters marked **\*** let you pick **one, several, or all** values at once — they start with everything available selected, so if you want "all" you don't have to do anything. Remove the ones you don't want.

> The page refreshes as you pick each filter — that's how it knows what to offer next. Nothing is calculated or changed until you click **Preview**.

### 6. Review the Preview

The preview names the exact operation it's about to run (for example *Digital · Social · Media_Cost · Weighted by impressions*), followed by four numbers:

| Card | Meaning |
|---|---|
| **Rows in subset** | How many rows match the filters you picked. |
| **Current sum** | What those rows add up to today, before any change. |
| **Resulting sum** | What they'll add up to after the backfill. For a target-based operation this is your target; for a copy operation it's whatever the source column totals. |
| **Delta** | The difference between the two — how much this adjustment moves the total. |

This is your chance to sanity-check **before anything is written**. If the row count looks way off, double-check your filters. Nothing has changed yet.

If something's wrong, the tool tells you exactly why instead of showing the preview — see [What the error messages mean](#what-the-error-messages-mean).

### 7. Add it to your queue

Happy with the preview? Click **Add to queue**. This doesn't touch your file yet either — it just saves this adjustment as one item on a to-do list.

You can now go back and set up your **next** adjustment — a different campaign, a different Digital type, a different operation, or TV. Repeat as many times as you need. Nothing gets applied until you say so.

### 8. Review your queue

Scroll down to the **Backfill queue** table to see everything lined up so far — mode, type, field, **operation**, filters, row count, current sum, resulting sum and delta for each one. This is a good moment to double-check the whole batch before running it.

Made a mistake? Pick the item's number in **Remove from queue** and click **Remove selected**. You can also click **Clear queue** to wipe the whole list and start over.

### 9. Run the queue

When your queue looks right, click **Run full queue**. This is the one moment your file's numbers actually change — every item is applied in one go, and you'll see a results table confirming what happened to each one (applied, with the final numbers, or skipped with a reason).

### 10. Download your results

Two downloads are available at any point:

- **The updated Excel file** — contains your data with every backfill you've run applied. You can rename it before downloading.
- **The backfill log (CSV)** — a record of every adjustment actually applied this session: timestamp, mode, type, field, **the exact operation used**, filters, target, rows affected, and the totals before/after. Keep this for your own records or to explain what changed later.

You can keep working after downloading — add more items to the queue, run them, and download again with the latest numbers.

### Starting over

Click **Start over with another file (reset)** at any time to clear everything and upload a new file. Note: reloading the browser page also clears your session — download your file first if you have unsaved work.

---

## How the numbers are calculated

### Weighted by impressions (Media Cost)

Splits the target across the matching rows **in proportion to how much each row delivered** — never evenly, never guessed. A row that delivered twice as many impressions as another gets twice as much of the cost.

**Example** — you know a package really cost $1,000 total, split across 3 rows:

| Row | Impressions | Share of impressions | New Media Cost |
|---|---|---|---|
| A | 6,000 | 60% | $600 |
| B | 3,000 | 30% | $300 |
| C | 1,000 | 10% | $100 |
| **Total** | **10,000** | **100%** | **$1,000** |

Row A delivered the most, so it gets the biggest share. The new numbers always add up exactly to your target. A row with 0 (or blank) impressions always gets $0 — it didn't deliver anything, so it shouldn't receive any cost.

### Even allocation (Media Cost)

Ignores delivery entirely and gives every row the same amount: **target ÷ number of rows**. With $1,000 across those same 3 rows, each one gets $333.33. Useful when there's no delivery to weight by, or when the cost genuinely isn't tied to delivery.

### Weighted (Impressions)

Splits the target in proportion to the impressions **already in the rows**, which means the day-to-day delivery curve keeps its exact shape — only the total changes.

**Example** — the rows currently hold 100 / 200 / 700 impressions and you set a target of 2,000:

| Row | Current impressions | Share | New impressions |
|---|---|---|---|
| A | 100 | 10% | 200 |
| B | 200 | 20% | 400 |
| C | 700 | 70% | 1,400 |
| **Total** | **1,000** | **100%** | **2,000** |

Same proportions, new total. If the rows have **no** impressions at all, the tool falls back to weighting by Media Cost instead:

| Row | Media Cost | Share of cost | New Impressions |
|---|---|---|---|
| A | $672.35 | 7.3% | ~58,114 |
| B | $2,866.20 | 31.0% | ~247,736 |
| C | $5,045.60 | 54.5% | ~436,110 |
| D | $671.50 | 7.3% | ~58,040 |
| **Total** | **$9,255.65** | **100%** | **800,000** |

Impressions always come out as whole numbers, and they still add up exactly to your target — the tool distributes the rounding so nothing is invented or lost.

### The copy operations

**Copy from Delivered Spend (Reconciled)**, **Copy from Delivered Spend (Prisma)** and **Copy from Weighted Planned Units** don't do any maths at all. They take the value sitting in that column, on that same row, and write it into Media Cost (or Impressions). No target, no weighting, no redistribution — a straight row-by-row copy. Blank cells in the source column are treated as 0.

### One important note

**Whatever number was already in the field you're backfilling gets fully replaced.** The tool doesn't look at the old value — it recalculates from scratch. This is intentional: it's the whole point of a backfill.

---

## Important rules & restrictions

- **No row can be backfilled twice in one session.** Once a set of rows is queued (or already run), the tool refuses any later selection that touches **even one** of those same rows — including a partly-overlapping multi-select, and including a different operation on the other field. This is a safety net against silently applying two conflicting adjustments to the same rows. The message tells you which queued or applied backfill is in the way. If you genuinely need to redo one, remove it from the queue, or finish the session, download the file, and start fresh on the downloaded result.
- **Some filters take several values, some take exactly one.** The ones labelled *(one, several or all)* — Reserve's Partner and Audience, Programmatic's Channel, CCD JTBD and Audience — start with everything available selected. Every other filter is a single value.
- **Filters must be answered in the numbered order.** Each one narrows the ones below it, so they stay locked until their turn. This is what keeps the dependent dropdowns (CCD JTBD, Audience, Breakout) showing only the values that belong to the package you picked.
- **Digital is split into Social, Reserve and Programmatic**, worked out automatically from each row's placement name and partner. You can't mix them in one backfill — pick the type first.
- **Rows whose placement has neither `UNE` nor `UUT` can't be backfilled here.** These are typically bonus or added-value lines. The tool reports how many your file has, but offers no way to adjust them — they have to be handled by hand in Excel.
- **Rows with 0 (or blank) weight get 0 in a weighted result** — a row with no impressions gets $0 cost. This is automatic, not something you configure. (Even allocation and the copy operations don't work this way — they don't look at delivery at all.)
- **You can target exactly 0**, on Digital or TV — useful for deliberately zeroing out a miscoded cost. Only a negative number is rejected.
- **A weighted backfill needs something to weight by — unless your target is 0.** If every row's weight is 0 or blank and your target is anything other than 0, there's no basis to split proportionally, so the tool blocks it and says so. A target of exactly 0 is always allowed even then (there's nothing ambiguous about splitting zero across zero delivery), and even allocation or a copy operation will usually still work on those rows regardless of target.
- **Impressions are always whole numbers**, on every operation, and still add up exactly to your target.
- **Nothing is applied until you click "Run full queue."** Uploading, previewing, and queuing are all completely safe — they never change your data.
- **Only the field you're backfilling changes.** No other column is ever touched — not Delivered Spend, not GRPs, nothing else. Note this means the *other* spend columns won't agree with Media Cost after a backfill.
- **Your session lives only in the browser tab.** There's no saving to a server or database. If you close the tab or reload the page before downloading, your work is gone — download often, especially after a big batch.
- **The downloaded file contains only your working sheet**, not any other tabs that were in the original file, to keep it lightweight.

---

## File requirements

The file needs a **Channel** column and a **Date** column no matter what. Beyond that:

**For Digital mode**, your file needs: Channel, Date, Campaign (secondary), Partner, Package Name, **Package/Placement Name**, CCD JTBD, Audience, Breakout, Impressions, Media Cost. (Package/Placement Name is what the tool reads to tell Social, Reserve and Programmatic apart, so Digital can't work without it.)

**For TV mode**, your file needs: Channel, Date, Brand, Audience, Daypart, Network Name, Impressions, Media Cost.

**For the copy operations**, you also need whichever source column you're copying from: Delivered Spend (Reconciled), Delivered Spend (Prisma), or Weighted Planned Units. If a column isn't in your file, that operation says so instead of failing halfway.

If your file is missing something for one mode but has everything for the other, you'll still be able to use the mode that's fully covered — you'll just see a clear notice about the other one.

---

## What the error messages mean

| Message | What it means | What to do |
|---|---|---|
| "The target must be a number greater than or equal to 0." | You entered a negative number. | 0 is fine (e.g. to zero out a cost) — only negative numbers are rejected. |
| "Pick a value for [filter] — the filters below it are still locked." | You clicked Preview before answering every filter in order. | Work down the numbered list; the greyed-out ones unlock as you go. |
| "Pick at least one value for [filter]." | You cleared a multi-select filter completely. | Select at least one value, or put them all back. |
| "0 rows match these filters." | No row matches every filter you picked, all at once. | Double-check each one — a common cause is a Month/Package/Audience combination that doesn't actually co-occur. Also check you're on the right Digital type. |
| "These rows overlap a backfill that is #N (…), still queued." | Some of these rows are already in a queued adjustment. | Look at the queue: either remove that item, or narrow your filters so the two don't share rows. |
| "These rows overlap a backfill that is …, already applied in this session." | You already ran a backfill on some of these rows. | If you truly need to change them again, download the file and start a new session on the result. |
| "The rows in this subset have 0 total [field]. There is no basis to distribute the value." | Every matching row has 0 (or blank) in the column being used as weight. | Use **Even allocation** or a **copy** operation instead — neither needs delivery. On TV with a genuine $0 target, entering 0 also works. |
| "This file has no '[column]' column, so this operation is unavailable." | You picked a copy operation but that source column isn't in your file. | Use a different operation, or load a file that includes the column. |
| "[Mode] mode is not available for this file: missing critical columns (...)." | Your file is missing one or more columns that mode needs. | Either use the other mode, or load a file with the full column set. |

---

## Quick recap

1. Upload → pick sheet.
2. Pick **Digital** (then Social / Reserve / Programmatic) or **TV**.
3. Pick the **field** and the **operation**.
4. Answer the numbered filters top to bottom (each unlocks the next), add the target if the operation needs one → **Preview** → sanity-check the 4 numbers.
5. **Add to queue**. Repeat for every adjustment you need.
6. Review the queue, remove anything wrong.
7. **Run full queue** — this is the only step that changes your data.
8. Download the updated file and the log.

That's it — no formulas to write, no manual math, and every number you enter always adds up exactly on the other end.
