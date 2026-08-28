# M.E.R.I.T. APP — Governance & Deployment

How the app is distributed, what it's built on, where data goes, and what's still open. Written for the questions raised in the stakeholder review: **licensing, tool approval, and hosting.**

> For what the app does, see the [Overview](EXPLAINER_Overview.md). This document is about the *operational* side — how it ships and what it depends on.

---

## The short version

- The app runs **entirely on the user's own machine**. No server, no cloud, no data transmitted.
- Everything it's built on is **permissive open-source** — Apache-2.0, BSD and MIT. No paid licences, no copyleft obligations, no per-seat cost.
- **Distribution is via SharePoint** for now, with **Git used for version history**. Agreed in the stakeholder review.
- **WPP tool approval is an open action item.** Nothing here presumes it has been granted.

---

## Where the data goes

The most common governance question, and the one with the cleanest answer: **nowhere**.

| Question | Answer | How it was verified |
|---|---|---|
| Is data uploaded to a server? | **No.** Streamlit runs locally; the browser talks to `localhost:8501` on the same machine | No network-calling libraries are imported or used anywhere in the app code |
| Is data written to disk? | **No.** Files are processed in memory and returned as browser downloads | The only two `open()` calls in the codebase are **read-only**, and both read bundled reference files (the caveat template and the TV mappings), never user data |
| Is data shared between users? | **No.** Each run is one person's browser session | Nothing persists after the tab closes — there is no database and no shared state |
| Does anything leave the network? | **No user data.** See the telemetry note below | Verified by inspection of the codebase |

This is a deliberate design choice, not an accident of implementation: files in, files out, nothing retained.

> ⚠️ **One open item — Streamlit usage telemetry.** By default, Streamlit itself (not this app) sends *anonymous usage statistics* to its maintainers. This carries **no file contents and no business data**, but it is an outbound connection and should be switched off before wider rollout. It is a two-line fix — create `.streamlit/config.toml` containing:
> ```toml
> [browser]
> gatherUsageStats = false
> ```
> This has **not** been applied yet. It is listed under [Open action items](#open-action-items).

---

## What it's built on

Four dependencies, all mainstream and all permissively licensed. Versions are as installed in the project environment:

| Package | Version | Licence | What it does |
|---|---|---|---|
| **streamlit** | 1.59.2 | Apache-2.0 | The web UI framework — why it runs in a browser with no installation |
| **pandas** | 3.0.3 | BSD-3-Clause | Data manipulation |
| **openpyxl** | 3.1.5 | MIT | Reading and writing Excel files, preserving formatting |
| **numpy** | 2.5.1 | BSD-3-Clause (with 0BSD, MIT, Zlib, CC0-1.0 components) | Numeric operations; pulled in by pandas |

**What these licences mean in practice:** all four are permissive OSS licences. They allow commercial and internal business use, require no payment or per-seat licence, and impose no copyleft obligation — nothing about using them requires this app's own code to be published. The only standard obligation is attribution: retaining the copyright and licence notices, which is satisfied by leaving the installed packages intact.

**What this does *not* settle:** whether these tools are on WPP's approved list is a separate organisational question from whether their licences permit use. Permissive licensing is necessary but not sufficient — see below.

---

## Distribution and versioning

Two related but distinct needs, resolved separately in the stakeholder review:

### Distribution — how people get the app: **SharePoint**

Agreed as the interim approach. It is where the team already works and requires no new tooling or access requests.

### Version history — how changes are tracked: **Git**

The repository (`github.com/CristianBarbosaT/merit-app`) carries the full history: every change, when it was made, and *why*. That "why" is the point — the engineering changelog (`estado_actual_app.md`) records the reasoning behind each behavioural decision, including the cases where testing against real files proved a specification wrong.

### Why both, rather than one

They solve different problems:

- **SharePoint answers "how do I get the app?"** — accessible to everyone today, no Git knowledge required. This directly addresses the concern that not everyone on the team uses Git.
- **Git answers "what changed, when, and why?"** — SharePoint cannot reconstruct the reasoning behind a decision made three months ago, and cannot cleanly merge two people's work.

Using both means nobody is blocked on learning Git, while the project still keeps a real engineering history. The direction of travel is toward broader Git adoption; leadership expressed support for that, with this project as a candidate to drive it.

---

## Why this shape reduces risk

Several governance concerns are answered by the architecture rather than by policy:

**No hosting means no hosting risk.** There is no server to secure, patch, pay for, or get approved. The app runs where the data already is.

**No data movement means no data-residency question.** Files never leave the machine they were opened on.

**No stored state means no retention question.** Nothing persists after the browser tab closes.

**Standard tools mean no exotic dependency.** Streamlit, pandas and openpyxl are among the most widely deployed packages in their categories — not niche or unmaintained.

**Reproducible outputs mean auditability.** The same input produces the same output, and every run reports what it did and what it skipped. A number in a client deliverable can be traced back to the rule that produced it.

---

## Open action items

Honest status. Nothing below is claimed as done.

| # | Item | Why it matters | Status |
|---|---|---|---|
| 1 | **Confirm WPP approval for Streamlit / pandas / openpyxl / numpy** | Raised directly in the stakeholder review — permissive licensing does not by itself mean organisationally approved | **Open** |
| 2 | **Disable Streamlit usage telemetry** | Removes the only outbound connection the stack makes by default. Two-line config change, see above | **Open — not yet applied** |
| 3 | **Agree the SharePoint distribution layout** | Where the folder lives, who can write to it, and how a new version is published | **Open** |
| 4 | **Define how SharePoint and Git stay in step** | Which is authoritative, and who publishes a Git version to SharePoint | **Open** |
| 5 | **Run the follow-up walkthrough session** | Requested in the review: how the tool is built, and how to use it. The [playbooks](../README.md) are the material; the session is the delivery | **Open** |
| 6 | **Decide the onboarding path for non-Git users** | So SharePoint distribution doesn't become a permanent ceiling on collaboration | **Open** |

---

## Frequently asked questions

**Does this need a licence or a budget?**
No. All four dependencies are free and permissively licensed. There is no per-seat cost and no subscription.

**Does it need IT to install anything on each machine?**
It needs Python and the four packages in a virtual environment. There is nothing to install per-user beyond that — no admin rights, no service, no browser extension.

**Can two people run it at once?**
Yes — each runs their own local copy. They don't share state and can't interfere with each other.

**What happens if a dependency has a security advisory?**
Update the package and re-run the test suite. Because nothing is hosted and no data is transmitted, the exposure from a dependency issue is limited to the local machine.

**Could this be hosted centrally later?**
Technically yes — Streamlit supports it. But it would introduce every question the current design avoids: hosting approval, data residency, authentication, retention. Local-only was chosen deliberately, and moving away from it should be a conscious decision with those costs accepted, not a default.

**Is any of this sending our client data anywhere?**
No. The app makes no outbound connections. The one default telemetry channel belongs to Streamlit itself, carries no file contents or business data, and is listed above as an item to switch off regardless.
