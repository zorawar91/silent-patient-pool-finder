# Validation Spine — Slide Content (lead with the miss)

**Purpose:** the credibility segment of the CEO deck. The move is
counterintuitive and deliberate: **open with the test that failed.** A deck
that only shows wins reads as marketing; a deck that shows the one test its own
authors could not pass — and killed — earns the right to be believed on the
four it did pass. This is the antidote to "another overclaiming internal pitch."

Every number below is computed from public data already in the repo and
reproducible with `python3 src/validation/part3_tables.py`
(snapshot: `data/scored/validation_part3.json`). Nothing here is a slideware
estimate. Numbers verified against the committed snapshot before this file was
written.

---

## SLIDE 1 — "We tried to break our own product"

**Headline:** Before we ask you to believe the map, here's us attacking it.

**Sub:** Five falsifiable tests, each with a pre-stated kill criterion. One
fired. We're showing it first.

**Body — one line each, in this order:**

1. 🔴 **The miss — outcome prediction on public data.** *Kill criterion fired.*
2. 🟢 Temporal coherence — the ranking is stable across data vintages.
3. 🟢 Held-out severity — predicts a source it never ingests.
4. 🟢 Not a deprivation index — the diagnosis-gap signal is real.
5. 🟢 Weight robustness — the answer isn't an artifact of our weights.

**Speaker note:** "Four of these passed and I'll show them. But I want to start
with the one that didn't, because it's the reason you should trust the other
four."

---

## SLIDE 2 — The miss (lead with this)

**Headline:** The one test we failed — and why we're telling you.

**The claim we tested:** does the score predict the *change* in diagnosed
prevalence between CDC PLACES data vintages? If flagged counties surface more
diagnoses next vintage, the score has outcome-level power on public data.

**Result — n = 3,135 counties, Type 2 Diabetes:**

| Metric | Naive pool ranking | SPPF composite | Significant? |
|---|---|---|---|
| Spearman ρ vs realized Δ | −0.04 | −0.09 | no |
| Precision @ top-20 | 0.25 | 0.55 | no (p = 0.16) |
| AUC (top tercile) | 0.44 | 0.47 | no (p = 0.10) |

**The honest read:** *No* ranking — ours or the naive one — predicts
vintage-to-vintage prevalence deltas. The dominant structure is regression to
the mean in CDC's model-smoothed estimates. **Kill criterion: if lift ≤ 0 or
not significant, the composite does not earn the claim. It didn't. So we make
no outcome-lift claim on public data.**

**Speaker note (the pivot):** "That number is exactly what a claims extract
fixes — claims deltas aren't model-smoothed. The failed test *is* the data ask,
made concrete. Now here's what public data *can* prove."

---

## SLIDE 3 — What survived (the four passes)

**Headline:** What public data does establish — four ways.

### Panel A · Temporal coherence
Build the score from the **older** 2020-BRFSS vintage only, freeze it, compare
to today's ranking.
- **Spearman ρ = 0.93 · Kendall τ = 0.79**
- **Top-50 overlap = 84%** (vs **1.6%** expected by chance) · n = 3,135
- *Proves:* the ranking is signal, not a single-release artifact.

### Panel B · Held-out severity
Predict a public severity measure the model **never ingests** — County Health
Rankings *premature death* (years of life lost).
- **Composite ρ = 0.47** (p < 10⁻¹⁷⁰) vs **−0.08** for the naive
  population × prevalence pool ranking · **lift = +0.55** · n = 3,144
- *Proves:* the score tracks real health severity, not internal noise.

### Panel C · Not a deprivation index
The obvious objection: "this is just a poverty map." Test the diagnosis-gap
dimension's *incremental* value over an SDoH-only model.
- SDoH-only R² = 0.23 → **+ Diagnosis Gap R² = 0.43 (ΔR² = +0.20)**
- **Partial r = 0.51** (p < 10⁻²⁰⁰) · full 7-dimension R² = 0.64 · n = 3,144
- *Proves:* the detection-gap signal adds real predictive content beyond
  deprivation.

### Panel D · Weight robustness
Shake all seven weights and watch the top-20.
- **±25% perturbation → 93% of the top-20 hold** (Kendall τ = 0.95, 2,000 draws)
- ±10% → 97% hold · 18 of 20 counties stable in ≥90% of draws
- *Proves:* the decision doesn't hinge on "why 20/25/15/…?"

---

## SLIDE 4 — Why the miss makes the rest believable + the ask

**Headline:** Public data takes us this far. One extract takes us the rest.

**Left — proven today (public, auditable, zero PHI):**
- Ranking is stable, corroborated by an external severity source, carries
  signal beyond deprivation, and survives weight stress.

**Right — the one thing public data can't do:**
- Calibrate outcome: *did flagged counties actually surface more diagnoses?*
  The public-data version of that test failed for a known reason (model
  smoothing). Claims data — which we already own — removes that ceiling.

**The ask:** one backdated claims extract · one condition · two states ·
90 days · **the same pre-registered kill criterion that just failed in public.**
If it fails again, we kill it for the cost of a pilot. If it passes, IQVIA owns
the demand-generation layer upstream of every product it already sells.

**Speaker note:** "You've now watched this framework kill one of its own claims.
That's the discipline the pilot runs under. You're not funding optimism — you're
funding a falsifiable test with a decision date."

---

## PREPARED-ANSWER PACK (the objections a sharp CFO/analyst will raise)

Keep these off the slides; have them ready. Each answer is a number, not a
posture.

| Objection | Answer |
|---|---|
| **"Prevalence alone predicts severity better than your composite."** | *True, and disclosed:* prevalence alone gets ρ = 0.63 on the severity measure vs our 0.47 — because prevalence is a near-sibling of severity, and we deliberately dilute it with payer, readiness, and access signal to optimize *actionability*, not severity correlation. But the gap signal isn't redundant with prevalence: controlling for prevalence, the Diagnosis Gap dimension still adds **ΔR² = +0.08** (partial r = +0.36, p < 10⁻⁹⁵). The composite carries independent signal — it's not repackaged prevalence. |
| **"You picked the weights to get this answer."** | Panel D: ±25% weight shake, 93% of the top-20 unchanged. And it's live in the product — drag them yourself. |
| **"Isn't this just a poverty map?"** | Panel C: ΔR² = +0.20, partial r = 0.51 for the diagnosis-gap dimension over an SDoH-only baseline. |
| **"Your one failed test worries me."** | It should reassure you — it's the only kind of test public data can run on outcomes, it failed for a documented reason (model smoothing), and we report it rather than bury it. The pilot re-runs it on data that doesn't have that flaw. |
| **"Why should I believe the passes if the outcome test failed?"** | The four passes test *different properties* — stability, external validity, incremental content, robustness — none of which depend on the vintage-delta signal that failed. Coherence, held-out severity, and weight stress are independent lines of evidence. |

---

## Design notes for the slide build

- **Color the miss red and put it first.** The instinct is to hide it or end on
  it; the credibility mechanism only works if it *leads*.
- One stat per panel gets the big number; the rest is small.
- Never show all five tests as equal green checks — the asymmetry (1 red, 4
  green) is the whole message.
- Footer every data slide: *"Public data · reproducible: src/validation/ ·
  zero PHI."*

*Numbers from the committed validation snapshot (public data, reproducible via
src/validation/part3_tables.py). Re-run after any re-ingestion.*
