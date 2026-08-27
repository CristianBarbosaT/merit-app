# M.E.R.I.T APP — TV Data Standardization User Guide

A friendly, no-jargon walkthrough of what this tool does and how to use it.

> Open this tool from the **M.E.R.I.T APP** home menu. Click **"← Back to menu"** at any time to switch tools.

---

## What this tool is for

The TV team sends you a file per product listing every single spot that aired. It arrives exactly as pulled from their system — report header, inconsistent network codes, dates with no year — which makes it awkward to use anywhere else.

This tool takes those raw files and returns a **standardized** version: real dates instead of text codes, networks and dayparts mapped to consistent names, impressions converted to real units. You choose whether you want that back as one file per product, one file with everything combined, or both.

---

## The one thing worth understanding: affidavit dates

Every spot has two dates:

- **DATE** — when the spot was *planned* to air.
- **AFFID DATE** — the *affidavit* date, when the station certified it actually aired. It looks like `JUN28` (month + day, no year).

These often differ — make-goods and reschedules are normal. The tool converts **AFFID DATE** into a real, year-aware date (falling back to the planned date when the affidavit is blank, about 5% of rows) and adds it to the standardized output as `EFFECTIVE DATE`. This is the date that reliably lines up with how the reporting platform files its own records.

You don't have to do anything for this — it's automatic.

---

## Before you start

You need the TV team's files (`.xlsx`) — one per product. The tool reads them exactly as they arrive, report header and all; it finds the real header row by looking for `ESTIMATE NAME`, so you don't need to delete anything.

The product code (DHC / TRE / VIC) is taken from the **start of each filename**, since it isn't a column inside the file. So keep the naming convention: `DHC 4.1-6.30 TV Data.xlsx`.

---

## Step-by-step workflow

### 1. Upload the TV files

Drop in all the TV files at once and click **Standardize**.

**If you uploaded two files for the same product** (a re-pull), the tool keeps the **more recent** one and tells you which it discarded. This matters: a re-pull usually exists precisely because the real audience numbers finally arrived, so using the older file would silently lose them.

### 2. Check what was read

You'll see a row per file: which product, how many spots, how many had a blank affidavit date. Above that, headline numbers for the whole batch.

### 3. Choose the output format

Pick how you want the standardized data delivered:

| Option | What you get |
|---|---|
| **Separate files per product** | One `.xlsx` per product, zipped together. |
| **One consolidated file** | A single `.xlsx` with every product's rows combined. |
| **Both** | A zip containing the per-product files *and* the consolidated one. |

### 4. Generate and download

Click **Generate**, then **Download**. Each output file has one sheet, `DATA`, with the fully standardized rows.

---

## What the tool will refuse to do

**An unmapped network stops the run.** If a TV file contains a network that isn't in the mapping table, the tool raises an error naming it rather than carrying on. This is deliberate: an unmapped network would silently arrive un-standardized instead of being flagged. Add it to `tools/tv_mappings.json` and re-run.

The same applies to an unrecognised `ESTIMATE NAME`.

---

## Editing the mapping tables

Two lookups live in `tools/tv_mappings.json`, editable without touching any code:

- **`estimate_names`** — maps a raw `ESTIMATE NAME` (`25/26 HISPANIC ROS`) to its clean name and its daypart (`HISPANIC`). The year prefix/suffix is inconsistent across estimates, which is why this is an explicit table rather than a pattern.
- **`networks`** — maps a raw `NETWORK` (`ACCN ACC NETWORK`) to a clean network name (`ACC NETWORK`). Usually it just drops the code, but not always — `XNCN NATIONAL CINEMEDIA` keeps its code — so again, an explicit table.

Also in there: `daypart_to_platform` and `product_brands`.

---

## Things worth knowing

- **Impressions in the TV files are in thousands** and are multiplied by 1,000 automatically.
- **Quarter is ignored.** Some spots are tagged `JUL-JUL` because they were bought in Q3 but started running in June. What matters is the date, not the quarter, so they're included.
- **Blank cells arrive as spaces, not as empty cells**, in the TV files — handled automatically.
- **Your session lives only in the browser tab.** Download the output before closing or reloading.

---

## What the error messages mean

| Message | What it means | What to do |
|---|---|---|
| "NETWORK values not in the mapping table: [...]" | A TV file has a network the mapping doesn't know. | Add it to `tools/tv_mappings.json` under `networks`. |
| "ESTIMATE NAME values not in the mapping table: [...]" | Same, for an estimate name. | Add it under `estimate_names`, with its daypart. |
| "Could not find the header row (column A = 'ESTIMATE NAME')." | The file doesn't look like a TV pull. | Check you uploaded the right file and that the `RAW DATA` sheet is intact. |
| "column N is 'X', expected one of [...]" (warning) | A TV file's header is spelled differently than usual. | Usually harmless — columns are read by position — but worth a look. |

---

## Quick recap

1. Upload the TV files → **Standardize**.
2. Check the files-read table, especially any re-pull notice.
3. Pick separate / consolidated / both.
4. **Generate** → download.
