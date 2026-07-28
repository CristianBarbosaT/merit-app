# Weighted Media Cost Backfill — User Guide

A friendly, no-jargon walkthrough of what this tool does and how to use it.

---

## What this tool is for

Every month, your partner reports (Pinterest, Meta, TV networks, etc.) sometimes arrive with a **missing cost or missing impressions** at the detailed row level, even though you know the **correct total** for a specific group of rows (a campaign, a package, a TV daypart, etc.).

Instead of splitting that total evenly across the rows — or typing numbers in by hand — this tool splits it **proportionally to how much delivery each row actually had**. A row that delivered more impressions gets a bigger share of the cost; a row that delivered fewer gets a smaller share. The tool guarantees the pieces always add back up exactly to the total you entered.

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

### 3. Choose Digital or TV

Right above the filters, you'll see a **Mode** switch: **Digital** or **TV**. Pick whichever kind of adjustment you're making. You can switch back and forth freely during your session — it doesn't lock you in.

### 4. Set your filters and your target number

Fill in every dropdown to describe exactly which rows you want to adjust, then enter the number you want those rows to add up to.

- **Digital** — 7 filters: Month, Campaign, Partner, Package, CCD JTBD, Audience, Breakout, plus a **Target Media Cost**.
- **TV** — 5 filters: Month, Brand, Audience, Daypart, Network, plus a choice of **which field to fix** (Media Cost or Impressions) and the target number for it.

All the dropdowns only show values that actually exist in your file, so you can't accidentally type something that doesn't match.

> Changing a dropdown does **not** reload the page or recalculate anything by itself — take your time picking all the filters, and only when you're ready, click **Preview**.

### 5. Review the Preview

After clicking **Preview**, you'll see four numbers:

| Card | Meaning |
|---|---|
| **Rows in subset** | How many rows in your file match the filters you picked. |
| **Current sum** | What those rows currently add up to, before any change. |
| **Target sum** | The number you typed in. |
| **Delta** | The difference between the target and the current sum — how much this adjustment will move the total. |

This is your chance to sanity-check things **before anything is written**. If the row count looks way too high or too low, double-check your filters. Nothing has been changed yet at this point.

If something's wrong with your filters or target, the tool will tell you exactly why instead of showing the preview — see [What the error messages mean](#what-the-error-messages-mean).

### 6. Add it to your queue

Happy with the preview? Click **Add to queue**. This doesn't touch your file yet either — it just saves this adjustment as one item on a to-do list.

You can now go back to step 4 and set up your **next** adjustment — same file, maybe a different campaign, a different package, or even switch to TV mode. Repeat as many times as you need. Nothing gets applied until you say so.

### 7. Review your queue

Scroll down to the **Backfill queue** table to see everything you've lined up so far — mode, field, filters, row count, current sum, target, and delta for each one. This is a good moment to double-check the whole batch before running it.

Made a mistake? Pick the item's number in **Remove from queue** and click **Remove selected**. You can also click **Clear queue** to wipe the whole list and start over.

### 8. Run the queue

When your queue looks right, click **Run full queue**. This is the one moment your file's numbers actually change — every item in the queue gets applied in one go, and you'll see a results table confirming what happened to each one (applied, with the final numbers, or skipped with a reason).

### 9. Download your results

Two downloads are available at any point:

- **The updated Excel file** — contains your data with every backfill you've run applied. You can rename it before downloading.
- **The backfill log (CSV)** — a record of every adjustment you've actually applied this session: timestamp, filters used, target, rows affected, and the totals before/after. Keep this for your own records or to explain what changed later.

You can keep working after downloading — add more items to the queue, run them, and download again with the latest numbers.

### Starting over

Click **Start over with another file (reset)** at any time to clear everything and upload a new file. Note: reloading the browser page also clears your session — download your file first if you have unsaved work.

---

## How the numbers are calculated

Both modes use the same underlying idea: **split the target number across the matching rows, in proportion to how much delivery each row had** — never evenly, never guessed.

### Digital: Cost, weighted by Impressions

Digital always fixes **Media Cost**, and always splits it based on **Impressions**. A row that delivered twice as many impressions as another gets twice as much of the cost.

**Example** — you know a package really cost $1,000 total, split across 3 rows:

| Row | Impressions | Share of impressions | New Media Cost |
|---|---|---|---|
| A | 6,000 | 60% | $600 |
| B | 3,000 | 30% | $300 |
| C | 1,000 | 10% | $100 |
| **Total** | **10,000** | **100%** | **$1,000** |

Row A delivered the most, so it gets the biggest share of the $1,000. The three new numbers always add up exactly to your target.

A row with 0 (or blank) impressions always gets $0 — it didn't deliver anything, so it shouldn't receive any of the cost.

### TV: either field, weighted by the other one

TV works the same way, but you choose which field to fix:

- **Fix Media Cost, weighted by Impressions** — identical logic to Digital, shown above.
- **Fix Impressions, weighted by Media Cost** — the reverse: rows that cost more get a bigger share of the total impressions you're entering.

**Example** — fixing Impressions, target = 800,000, weighted by each row's Media Cost:

| Row | Media Cost | Share of cost | New Impressions |
|---|---|---|---|
| A | $672.35 | 7.3% | ~58,114 |
| B | $2,866.20 | 31.0% | ~247,736 |
| C | $5,045.60 | 54.5% | ~436,110 |
| D | $671.50 | 7.3% | ~58,040 |
| **Total** | **$9,255.65** | **100%** | **800,000** |

Same principle, just flipped: the field you're weighting by decides how the pie gets sliced; the field you're fixing is what gets sliced.

### One important note

**Whatever number was already sitting in the field you're fixing gets fully replaced.** The tool doesn't look at the old value at all — it recalculates from scratch based only on delivery (impressions or cost, whichever is the weight). This is intentional: it's the whole point of a backfill.

---

## Important rules & restrictions

- **You always pick one exact value per filter.** There's no way to select "Pinterest or Meta" in one go — do them as separate adjustments if you need to cover both.
- **One adjustment per exact group of rows, per session.** Once you've queued (or already run) a backfill for a specific combination of filters, the tool won't let you queue another one for that *exact same combination* — even if you pick the other field on TV. This is a safety net so you don't accidentally apply two conflicting adjustments to the same rows without noticing. If you really need to redo one, finish your session, download the file, and start a fresh session on the downloaded result.
- **Digital only ever fixes Media Cost, weighted by Impressions.** There's no field choice on Digital — that flexibility only exists for TV.
- **Rows with 0 (or blank) weight get 0 in the result** — a row with no impressions gets $0 cost; a row with no cost gets 0 impressions. This is automatic, not something you configure.
- **Exception for TV only**: if a whole group of rows has 0 impressions (so there's normally no way to split a cost among them) **and** you're targeting exactly **$0**, the tool allows it — every row simply gets $0, since there's nothing ambiguous about splitting zero. Any target other than exactly 0 still requires real delivery to weight by.
- **A group of rows with nothing to weight by (and a non-zero target) cannot be backfilled.** If every row's weight field is 0 or blank, there's no basis to split the number proportionally, so the tool blocks it and tells you why.
- **Nothing is applied until you click "Run full queue."** Uploading, previewing, and queuing are all completely safe — they never change your data.
- **Only the field you're backfilling changes.** No other column in your file is ever touched — not Delivered Spend, not GRPs, nothing else.
- **Your session lives only in the browser tab.** There's no saving to a server or database. If you close the tab or reload the page before downloading, your work is gone — download often, especially after a big batch.
- **The downloaded file contains only your working sheet**, not any other tabs that were in the original file, to keep it lightweight.

---

## File requirements

The file needs a **Channel** column and a **Date** column no matter what. Beyond that:

**For Digital mode**, your file needs: Channel, Date, Campaign (secondary), Partner, Package Name, CCD JTBD, Audience, Breakout, Impressions, Media Cost.

**For TV mode**, your file needs: Channel, Date, Brand, Audience, Daypart, Network Name, Impressions, Media Cost.

If your file is missing something for one mode but has everything for the other, you'll still be able to use the mode that's fully covered — you'll just see a clear notice that the other one isn't available until you load a more complete file.

---

## What the error messages mean

| Message | What it means | What to do |
|---|---|---|
| "The target must be a positive number." (Digital) | You left the target at 0 or entered a negative number. | Enter the real total cost you want those rows to add up to. |
| "The target must be a number greater than or equal to 0." (TV) | You entered a negative number. | TV allows 0, but not negative numbers. |
| "0 rows match these filters." | No row in your file matches every filter you picked, all at once. | Double-check each dropdown — a common cause is picking a Month/Package/Audience combination that doesn't actually co-occur in your data. |
| "This subset already has a [field] backfill pending or applied in this session." | You've already queued or run an adjustment for this exact combination of filters. | Check your queue and your log — if you truly need to change it again, do it in a new session on the downloaded file. |
| "The rows in this subset have 0 total [field]. There is no basis to distribute the value." | Every matching row has 0 (or blank) in the field you're weighting by, so there's nothing to split proportionally. | If you're on TV and your target is genuinely $0, enter 0 — that specific case is allowed. Otherwise, this group of rows can't be backfilled this way. |
| "[Mode] mode is not available for this file: missing critical columns (...)." | Your file is missing one or more columns that mode needs. | Either use the other mode, or reload a file that has the full column set. |

---

## Quick recap

1. Upload → pick sheet.
2. Pick Digital or TV.
3. Set filters + target → **Preview** → sanity-check the 4 numbers.
4. **Add to queue**. Repeat for every adjustment you need.
5. Review the queue, remove anything wrong.
6. **Run full queue** — this is the only step that changes your data.
7. Download the updated file and the log.

That's it — no formulas to write, no manual math, and every number you enter always adds up exactly on the other end.
