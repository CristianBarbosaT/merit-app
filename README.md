# M.E.R.I.T. APP

**Media Evaluation, Reconciliation & Integrity Tool**

An internal web app covering the monthly media delivery-reporting cycle in five guided tools — checking raw delivery data, standardizing TV files, filling known gaps, building the client deliverable, and documenting what the data can't say.

---

## Start here

| If you want to… | Read |
|---|---|
| Understand what this is and why it exists | **[Overview](docs/EXPLAINER_Overview.md)** |
| See how the tools fit together across a month | **[Monthly Workflow](docs/EXPLAINER_Monthly_Workflow.md)** |
| Look up an unfamiliar term | **[Glossary](docs/EXPLAINER_Glossary.md)** |
| Actually operate a tool | The **playbook** for that tool, below |
| Understand a technical decision | [`estado_actual_app.md`](estado_actual_app.md) |

---

## The five tools

| # | Tool | What it does | Playbook |
|---|---|---|---|
| 1 | 🔍 **Merit Inspect** | Monthly QA pass: field checks, ~15 value-level rules, spend-vs-delivery analysis, and a verdict | [Playbook](docs/PLAYBOOK_Merit_Inspect.md) |
| 2 | 📺 **TV Data Standardization** | Normalizes the TV team's raw spot files — affidavit dates to real dates, networks and dayparts mapped | [Playbook](docs/PLAYBOOK_TV_Data_Standardization.md) |
| 3 | 🧩 **RROI Manual Backfill** | Distributes a known total across rows missing cost or impressions — weighted, evenly, or copied | [Playbook](docs/PLAYBOOK_RROI_Manual_Backfill.md) |
| 4 | 📦 **Merit Deliver** | Builds the client deliverable, reconciles it against the source, flags formulas and duplicates | [Playbook](docs/PLAYBOOK_Merit_Deliver.md) |
| 5 | ⚠️ **Data Caveats Generator** | Finds genuine unfixable gaps and writes one Data Caveat Log per brand on the corporate template | [Playbook](docs/PLAYBOOK_Data_Caveats_Generator.md) |

The typical order across a month is **2 → 1 → 3 → 1 → 4**, with **5** alongside. See the [Monthly Workflow](docs/EXPLAINER_Monthly_Workflow.md).

---

## Running the app

```bash
cd "C:\Users\Cristian.Barbosa\Documents\merit_V1"
.venv\Scripts\python.exe -m streamlit run app.py
```

It opens at **http://localhost:8501**. `Ctrl+C` in the terminal stops it.

> On this machine `python` and `py` resolve to the Microsoft Store aliases and fail — always call the interpreter inside `.venv` by its full path, as above.

**First-time setup**

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Requirements: `streamlit`, `pandas`, `openpyxl` (plus `numpy`, pulled in by pandas).

---

## Repository layout

```
merit_V1/
├── app.py                       # Shell: home menu + tool registry. Adding a tool = one entry here
├── tools/
│   ├── merit_inspect.py         # 1 · Merit Inspect
│   ├── tv_standardization.py    # 2 · TV Data Standardization
│   ├── rroi_backfill.py         # 3 · RROI Manual Backfill
│   ├── merit_deliver.py         # 4 · Merit Deliver
│   ├── data_caveats.py          # 5 · Data Caveats Generator
│   ├── config/
│   │   └── audience_codes.csv   # Audience code catalog (586 codes) — editable
│   ├── tv_mappings.json         # TV network/daypart mappings — editable
│   └── data_caveats_template.xlsx   # Official Data Caveat Log template
├── docs/
│   ├── EXPLAINER_Overview.md
│   ├── EXPLAINER_Monthly_Workflow.md
│   ├── EXPLAINER_Glossary.md
│   └── PLAYBOOK_*.md            # One per tool
├── estado_actual_app.md         # Engineering changelog — decisions and their reasoning
└── test_*.py                    # Test suites (see below)
```

Each tool is a self-contained module exposing `render()` and `init_state()`, with its own session-state key prefix so tools can't collide. The shell holds no business logic.

---

## Reference data you can edit without touching code

| File | Holds | Edit when |
|---|---|---|
| `tools/tv_mappings.json` | TV network names, estimate names, daypart mappings | A TV file fails on an unmapped network |
| `tools/config/audience_codes.csv` | Audience code → audience name (586 codes) | The approved audience list changes |
| `tools/data_caveats_template.xlsx` | The official Data Caveat Log template | The corporate template is revised |

---

## Tests

```bash
.venv\Scripts\python.exe test_logic.py
```

| Suite | Covers |
|---|---|
| `test_logic.py` | Backfill calculations, row-overlap locking, preview building |
| `test_data_caveats.py` | Caveat detection, both source schemas, template writing |
| `test_tv_standardization.py` | Affidavit-date conversion, re-pull resolution, real-file regression |
| `test_apptest_flow.py` | The backfill flow through real Streamlit widgets |
| `test_apptest_home.py` | Home menu, tool mounting, Data Caveats and TV flows |
| `test_apptest_cache.py` | Caching behaviour |
| `test_real_file.py` | Backfill against a real production workbook |

Two suites skip themselves cleanly when the real data files they need aren't on the machine — a skip is reported, never silently passed.

---

## Design principles

1. **Fail loudly rather than silently** — an unmapped value stops the run and names itself; it never passes through to quietly unbalance a total.
2. **Automate the unambiguous, surface the rest** — corrections are proposed only where the data is unambiguous; judgement calls are listed for a human, not guessed.
3. **Verify against reality** — tools are tested against real production files, not only synthetic ones.
4. **Configuration belongs to the team** — mappings and code lists live in editable config, not in logic.
5. **The output explains itself** — every run reports what it did, what it skipped, and what it couldn't decide.

The reasoning behind each is in the [Overview](docs/EXPLAINER_Overview.md#the-design-principles); the decision-by-decision record is in [`estado_actual_app.md`](estado_actual_app.md).
