# SPPF — Executive Demo Script (8 minutes, 3 views)

**Audience:** CEO / commercial leadership. Not a product tour — a narrative with
three stops. The other eight views exist for *their analysts*, later; in this
meeting they are depth-on-demand only (map at the bottom).

**The arc:** Where the money is → how it lands in a rep's hands → how we prove
it worked. Every number below is real, current, and was re-computed from the
live data before this script was written — nothing is a slide-ware estimate
unless explicitly labeled as one.

---

## Pre-flight checklist (5 minutes before)

- [ ] `streamlit run src/output/dashboard.py` — confirm it loads on **⚡ Insights & Actions** with **no state filter**
- [ ] Confirm header numbers: **3,144 counties · 20 Priority · 1,416 Emerging**
- [ ] Have this FIPS string in your clipboard manager:
      `48479, 48215, 48061, 48323, 48505, 48427, 48131, 48247`
- [ ] Browser at 100% zoom, sidebar visible, no other tabs
- [ ] Do **not** pre-click anything else — the demo starts clean

---

## Beat 0 — Cold open (0:00–0:30) · no screen yet

> "Every IQVIA asset — claims, LRx, OCE — starts *after* a diagnosis exists.
> Roughly 45 million American adults are walking around with undiagnosed
> diabetes, hypertension, or thyroid disease — that's the published CDC/NHANES
> estimate, not ours. Nobody sells the map of where they are. We built it,
> from public data, with zero PHI and zero licensing cost. Eight minutes."

*(The 45M figure is a published national estimate — always attribute it. Never
present it as a computed output.)*

---

## Beat 1 — ⚡ Insights & Actions (0:30–2:30)

**Do:** Nothing. The landing view *is* the demo.

**Say:**
> "This is the whole product on one screen: 3,144 counties scored on seven
> dimensions of public data, distilled to *where you move next*. Top of the
> list: **Starr County, Texas — score 65, the #1 county in America** for
> undiagnosed metabolic disease opportunity. The tool doesn't just rank it —
> it prescribes the *program type*: payer partnership, because Starr's
> Medicare Advantage penetration means an insurer there has a Stars-rating
> incentive to co-fund screening."

**Point at** the Top-3 cards: Starr TX · Oglala Lakota SD · Presidio TX.

> "Rio Grande Valley, the border, tribal lands — exactly where epidemiology
> says undiagnosed disease concentrates. The model has never seen a medical
> claim, and it independently finds the places any endocrinologist would name.
> That's face validity; the audit trail behind it is one click away and I'll
> show it if you want it."

**Guardrail:** Do NOT scroll through every card. Two cards, one sentence each, move.

---

## Beat 2 — 💡 Investment Planner (2:30–4:30)

**Do:** Sidebar → view **Investment Planner**. Leave filters at defaults
(top 20 counties). Scroll once to the ranked table, then click
**"⬇ Export investment list (CSV)"**.

**Say:**
> "Leadership picks the budget; this builds the plan. Twenty counties, each
> with its score, its estimated pool, and its recommended program type — and
> the program mix tells you what you're actually funding: payer partnerships
> where MA penetration is high, community health centers where social burden
> is high, pharmacy screening where nothing else reaches."

*(click Export)*

> "And this is the part that makes it operational rather than academic: that
> download is a CRM-ready call list. The same engine scores **411,000
> prescribers** from public CMS data — **20,612 priority targets** — ranked by
> the opportunity around their actual practice address, down to the ZIP:
> 33,791 of them scored. County → ZIP → the doctor a rep calls Monday morning.
> It plugs into the field force IQVIA already deploys."

**Guardrail:** Name the HCP and ZIP numbers; do NOT open those views. If asked,
that's depth-on-demand (below).

---

## Beat 3 — 📐 Campaign Measurement (4:30–7:00) · the moat

**Do:** Sidebar → **Campaign Measurement**. Paste the clipboard FIPS string
into the "paste county FIPS codes" box.

**Say while it computes:**
> "Here's the uncomfortable industry secret: screening-campaign ROI is
> essentially unmeasured. Money goes out, awareness goes up, nobody can prove
> diagnosis rates moved. This engine measures it like a clinical trial:
> you name your campaign counties — I just pasted eight Rio Grande Valley
> counties — it auto-matches each to its statistical twins, and reports
> diagnosis-rate lift net of the background trend, with confidence intervals."

**The rehearsed moment — the result will read approximately
`+0.17pp, 95% CI [−0.72, +1.07] — not distinguishable from zero`:**

> "And look at the verdict: *not significant*. No campaign actually ran in
> these counties — **and the tool says so**. It just refused to hallucinate
> lift on eight counties I picked to impress you. That's the product. When
> your campaign *does* run, this is a number your client can take to a
> budget-renewal meeting — because you've just watched it decline to flatter me."

**Guardrail:** Do not apologize for the null result. It is the close, not a bug.

---

## Beat 4 — Close and ask (7:00–8:00) · screen off or back to Insights

> "What you saw is live today on all public data: validated out-of-time —
> the ranking holds at ρ = 0.94 across data vintages, predicts an external
> severity measure it never ingests, and survives ±25% weight shake with 96%
> of the top-20 unchanged. What public data cannot do is calibrate the last
> step — did flagged counties actually surface more diagnoses. That takes one
> backdated claims extract we already own: one condition, two states, ninety
> days, pre-registered kill criterion. If it fails, we killed it for the cost
> of a pilot. If it passes, IQVIA has the demand-generation layer upstream of
> every product it already sells."

**The ask, in one sentence:** one design-partner pilot + one internal claims
extract, decision in 90 days.

---

## Depth-on-demand map (only if challenged)

| If they say… | Open… | One line |
|---|---|---|
| "You picked those weights to get this answer" | 7-Dimension Analysis → weight expander | "Drag them yourself — Spearman 0.98, Starr doesn't move." |
| "Where does the data come from?" | Data Provenance | "Eleven public sources, vintage-stamped, QA gates re-run on load — this page is the audit." |
| "Is this just a poverty map?" | (no view needed) | "We tested that: the Diagnosis Gap dimension adds ΔR² = +0.09 beyond deprivation alone, partial r = 0.35, p < 10⁻⁸⁰." |
| "Who exactly does a rep call?" | HCP Targeting | "Ranked call list with a written rationale per prescriber — public CMS data, no PHI." |
| "Counties are too coarse" | ZIP & Territory | "33,791 ZIPs; paste your own territory and get its scorecard." |
| "Which payer do we approach?" | Payer Landscape | "MA penetration is real CMS data; the quadrant chart names the conversation." |

## Do-NOT list

- Do not tour the 11 views or say "eleven views." Say **"three answers: where, who, and did it work."**
- Do not quote the 45M pool as a computed output — it's a published estimate, attributed.
- Do not say "AI" or "machine learning." Say **"a transparent, auditable index — deliberately."**
- Do not open Market Overview, State Drill-Down, or 7-Dim unprompted — they dilute the arc.
- Do not fill silence during the campaign computation — the wait builds the payoff.

---
*Numbers verified against live data (dimension_scores / hcp_targets / zip_scores
parquets) and the campaign result rehearsed with the exact paste string, at the
time this script was committed. Re-verify the pre-flight numbers after any
re-ingestion.*
