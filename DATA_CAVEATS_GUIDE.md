# M.E.R.I.T APP — Data Caveats Generator User Guide

A friendly, no-jargon walkthrough of what this tool does and how to use it.

> Open this tool from the **M.E.R.I.T APP** home menu. Click **"← Back to menu"** at any time to switch to another tool, like RROI Manual Backfill (see `USER_GUIDE.md`).

---

## What this tool is for

Delivery files sometimes have rows where the **cost is there but the impressions aren't** — or the other way around. Before a report goes out, someone needs to flag every one of those rows in a "Data Caveat Log" so the data team knows it's a known issue, not a mistake.

This tool reads your delivery files, finds every one of those rows automatically, and writes a ready-to-send Data Caveat Log for each brand — using the same official template, with its formatting, table and dropdowns intact. What used to be an hour of manually scanning a spreadsheet becomes one upload.

---

## Before you start

You need one or more delivery files (`.xlsx`) — the same files you already receive, no changes needed. You can upload a single file with several brands in it, or one file per brand, or a mix; the tool combines them all before looking for anything.

**Pick the file format** with the "Delivery file format" selector before uploading — every file in that batch is read with the same one:

- **RROI** — the standard raw delivery schema: Channel, Date, Brand, Category, Prisma_Campaign_Secondary, Raw_Partner, Package_Placement_Name, Impressions, Media_Cost. Retailer, GRPs and Video_Views are used if present but not required.
- **LCA** — the same fields, plus extra columns the tool ignores (Partnership, Campaign, Product_Line, Subcategory, Format, Audience, Daypart, Breakout, Clicks), with `Media Cost` and `Video Views` spelled with a space instead of an underscore.

If you upload files in both formats, run them through in two separate batches — read and generate the RROI ones, **Start over**, switch the selector, then read and generate the LCA ones.

You do **not** need to provide the Data Caveat Log template — the tool has the official one built in. Only upload your own if you've been told to use a different approved version.

---

## Step-by-step workflow

### 1. Upload your delivery files

Use the upload box to select one or more `.xlsx` files, then click **Read files**.

### 2. Check what was found

A table lists every file read — which tab it used, how many rows, which brand(s). If anything looks off (a file needed several attempts to find the right tab, or some rows had no valid date and were skipped), you'll see a note about it here.

### 3. Set up the run

- **Date range to report** — a slider showing every month found across your files. Drag both ends to cover the months you want in the log.
- **Detection granularity**:
  - **Month total (recommended)** — a row is a caveat if that placement's *whole month* has cost but no impressions (or the reverse). This is the setting validated against the template.
  - **Any single day** — also flags a placement if *any single day* matches the pattern, even though its month total is complete. Finds a lot more, but includes lines that are actually fine overall.
- **INC# for the output tabs** — the ticket number that goes into each output file's tab name. Leave it blank to keep a generic placeholder.
- **Filter the data to the selected range** — on by default. Turn it off to report every month found instead of just the ones you picked above (the file name still reflects your selected range either way).
- **Generate a file even if a brand has no caveats** — on by default. A brand with a completely clean delivery still gets a file (an empty, correctly-formatted log) so nothing is missing from the batch — it's flagged either way so you know to double-check it by hand.
- **Run validation before generating** — on by default. Strongly recommended; see below.
- **Stop instead of generating if validation finds issues** — off by default. Turn this on if you want a hard stop whenever validation has something to say, instead of generating anyway and reviewing after.

### 4. Generate

Click **Generate Data Caveat Logs**. This is the only step that actually produces files — uploading and adjusting settings never does.

### 5. Review the results

- Any validation findings appear first, color-coded by how serious they are (see below).
- A summary table shows every brand: how many caveats, how many of each type, and its status.
- Brands with zero caveats are called out separately — worth a manual double-check that their delivery is really complete.

### 6. Download

One button gives you a `.zip` containing every brand's Data Caveat Log, the validation report (if validation ran), and a plain-text summary.

---

## What counts as a caveat

Two patterns, both checked at the **placement + month** level (every day for that placement within that month, added together):

| Pattern | Meaning |
|---|---|
| **Null impressions** | That placement has Media Cost for the month, but zero (or blank) Impressions. |
| **Null cost** | That placement has Impressions for the month, but zero (or blank) Media Cost. |

**Example** — a placement's June rows add up to $500 in cost and 0 impressions all month → flagged **Null impressions** for June. If even one day that month has impressions, the month total is no longer zero, so it stops qualifying.

A placement with **both** metrics present — even partially, as long as the month total has something in each — is not a caveat.

---

## Understanding the validation findings

| Level | What it means |
|---|---|
| **ERROR** | Something blocks generation entirely — right now, only "the selected date range leaves no rows at all." |
| **FLAG** | Needs a manual look — a brand with zero caveat lines, meaning either its delivery is genuinely clean or something's missing. |
| **WARNING** | Worth checking, not necessarily wrong — masked single-day gaps, lines with GRPs/Video Views but zero cost and zero impressions, or negative values (usually adjustments/credits). |
| **INFO** | Just context — e.g. TV or other channels that don't carry Campaign/Placement in your file, so the tool can only detect caveats there at the Partner + Month level, not per placement. |

If validation finds nothing at all, you'll see a plain confirmation that the data looks consistent.

---

## What's in the download

- **One `.xlsx` per brand** — `{Brand}_DataCaveatLog_{range}.xlsx`, built from the official template. Each caveat becomes one row; the tab is named from your INC# and the brand's category.
- **A validation report** (`.xlsx`) — every finding with its full detail, one sheet per finding, if validation ran.
- **A summary** (`.txt`) — a plain-text recap of the whole run, useful for a quick paste into an email or ticket.

---

## Important rules & restrictions

- **Detection always happens at placement + month**, never at the single-day level for the log itself — "Any single day" mode only changes *which* placement-months qualify, the output is still one row per placement-month either way.
- **The Month column includes the year**, shown as `Jun-26`. It's written as a real date (which is what the template's own Month dropdown expects), so it sorts and filters correctly in Excel, and a log covering more than a year never leaves you guessing which `Jun` a row means.
- **Channels without a Campaign or Placement column filled in** (commonly TV) can only be checked at Partner + Month — that's the finest grain the data actually supports there.
- **A brand with zero caveats still gets a file by default** — an empty but correctly formatted log, so the batch is always complete. Turn off "Generate a file even if a brand has no caveats" if you'd rather skip those entirely.
- **Nothing is generated until you click "Generate Data Caveat Logs."** Uploading and adjusting settings are always safe.
- **Your session lives only in the browser tab.** Nothing is saved anywhere else — download the `.zip` before closing the tab or reloading the page.

---

## What the error messages mean

| Message | What it means | What to do |
|---|---|---|
| "No sheet has all the expected columns (...)." | None of a file's tabs has the required columns. | Check the file has the same structure as your usual delivery files. |
| "Missing columns in sheet '...': [...]" | The tab found is missing one of the required columns. | Add the missing column(s) to your file, or check you uploaded the right file. |
| "None of the uploaded files could be read." | Every uploaded file failed for the reasons above. | Fix the files and re-upload. |
| "None of the uploaded rows have a valid date." | Every row's Date column failed to parse. | Check the Date column's format in your file. |
| "The selected date range leaves no rows at all." | Your chosen range doesn't overlap any data. | Widen the range, or check you're looking at the right months. |
| "Could not locate the Data Caveat Log table in the template." | The template file doesn't have the expected table. | Use the built-in template, or check your custom one matches the approved structure. |

---

## Quick recap

1. Pick the delivery file format (RROI or LCA), then upload your delivery file(s) → **Read files**.
2. Check the files-read table for anything unexpected.
3. Set the date range, detection granularity, and INC#.
4. **Generate Data Caveat Logs.**
5. Review the validation findings and the summary table.
6. Download the `.zip` — one log per brand, ready to send.

That's it — no manually scanning rows, no retyping into the template by hand.
