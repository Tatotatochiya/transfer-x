---
title: "Sample Report: Player Valuation Stack"
last_updated: 2026-10-31
status: Design sample — illustrative model values, real public market estimates. Not for external distribution.
owner: "TODO — assign a Product Owner"
---

# Sample Report: Player Valuation Stack

> **What this is.** A design sample showing how a TransferX valuation would read once the [licensed market data and fee anchor](./market-data.md) plan is built. It is **not** a valuation report for any club, agent or player, and must not be sent outside TransferX as-is.
>
> **What is real and what is illustrative.**
> - **Real:** the public market estimates (SciSports ETV / FootballTransfers) and the reported transfer fees, with their dates and sources.
> - **Illustrative:** every "TransferX model" value, range, confidence and fee-anchor factor in this report. They were constructed for this sample and must be replaced with production `market-v3` values before any external use.
> - **Real but unverified:** the last transfer fees are public reports, not figures TransferX has verified. They are labelled "reported".
>
> **FX:** £1 = €1.17, the model's static fallback. A production report should use the ECB reference rate on the report date and state it.

## Report header

| | |
|---|---|
| Report | Player Valuation Stack — sample |
| Date | 31 October 2026 |
| Prepared for | Product and demo review |
| Model | `market-v3` (proposed; `market-v2` + last-fee anchor) |
| Market data | SciSports ETV via FootballTransfers (public figures) |
| Scope | Five cases: a fee-anchor case, an outgrown-fee case, a no-fee superstar, a release-clause case, and a coverage gap |
| Status | Design sample. Not for external distribution. |

## How to read it

| Term | Meaning |
|---|---|
| **TransferX model** | Our own estimate. The headline number, with a range and a confidence level. It is an estimate, never a verdict (D5) |
| **Market estimate** | A licensed provider's opinion, shown with the provider name and the date it was published. It is not "the true value" |
| **Market consensus** | A weighted combination of two or more licensed providers. Shown only when at least two providers cover the player |
| **Last reported fee** | What a club reportedly paid. A fact about a past transaction, not a current value |
| **Restated fee** | The last fee converted to today's money at the model's fee inflation rate, for comparison only. It is not a valuation |
| **Fee anchor** | The model's bounded adjustment toward the last fee, or an explicit decision not to apply it, with the reason |
| **Confidence** | The model's confidence in its own estimate. Not a probability that the number is "right" |

## Summary

| Player | Age · club · position | Contract | TransferX model | Range | Market estimate | Last reported fee | Restated | Fee anchor | Confidence |
|---|---|---|---|---|---|---|---|---|---|
| **Declan Rice** | 27 · Arsenal · MID | Jun 2028 | **£81.2m** | £69m–£93m | £85.5m (ETV, 1 Sep 2026) | £105m, Jul 2023 | £127.3m | **×1.13, applied** | Medium |
| **Cole Palmer** | 24 · Chelsea · MID | Jun 2033 | **£78.0m** | £66m–£90m | £85.5m (ETV, 2026) | £40m, Sep 2023 | £48.1m | **Not applied — outgrown** | Medium |
| **Lamine Yamal** | 19 · Barcelona · FWD | Jun 2031 | **£160.0m** | £130m–£190m | £193.1m (ETV, Oct 2026) | None (academy) | — | **Not applicable** | Low |
| **Erling Haaland** | 26 · Man City · FWD | Jun 2034 | **£130.0m** | £110m–£150m | £136.2m (ETV, 2026) | €60m release clause, Jul 2022 | £65.9m | **Not applied — release clause** | High |
| **Championship striker** (archetype) | 24 · Championship club · FWD | Jun 2029 | **£3.8m** | £3.3m–£4.4m | None | £2.0m, 2024 | £2.3m | **×0.84, applied** | Low |

All TransferX model values are illustrative. All ETV values are public and dated; all fees are reported, not verified.

---

## Case 1 — Declan Rice: the fee anchor that should have been visible

**Profile.** Declan Rice, born 14 January 1999, age 27, Arsenal, central midfielder, contract to 30 June 2028 (about 1.7 years remaining), England international.

**The last transfer.** West Ham United → Arsenal, July 2023. Reported £105m including add-ons (£100m base). Arsenal paid it after Rice had played 2,000+ minutes in each of the previous three Premier League seasons and captained West Ham. The fee was a market-clearing price for a proven 24-year-old midfielder with two years left on his West Ham contract.

### The three signals

| Signal | Value | Source and date | What it tells us |
|---|---|---|---|
| TransferX model | **£81.2m** (range £69m–£93m) | Illustrative; proposed `market-v3` | A midfielder with strong minutes, a long contract and a £105m fee should not be priced at £45m |
| Market estimate | **£85.5m** (range £71.5m–£87.4m) | SciSports ETV via FootballTransfers, 1 September 2026 (€100m, range €83.7m–€102.3m) | An independent licensed model lands within 5% of ours |
| Last reported fee | **£105m** in July 2023 | Public reports; not verified by TransferX | The last time the market priced him, it paid £105m |
| Restated fee | **£127.3m** today | £105m × 1.06^3.3 | Time value only; not a valuation |
| Market consensus | **Single-source £85.5m** | One provider | Labelled "single-source", not "consensus" |

### The fee anchor, step by step

```text
Last fee                          £105.0m   July 2023, reported
Restated to today                 £127.3m   × 1.06^3.3
Age factor (27, peak)              1.000    unchanged
Contract factor (1.7y left)        0.826    current vs at transfer (1.00)
Performance ratio (62 → 70)        1.063    square-root shrunk
Availability ratio                 0.950    95% available
League ratio                       1.000    PL to PL

Anchor value                      £106.2m
Model before anchor                £72.0m
Ratio                              1.475
Weight (credibility × recency)     0.310    0.65 reported fee × 0.476 recency
Factor                             ×1.128   exp(0.310 × ln 1.475)
Model after anchor                £81.2m
```

**Why the anchor applies.** The fee is recent enough to be informative (3.3 years), it was a permanent transfer at a disclosed price, and Rice has played enough football since to judge the purchase. The contract is the main discount: with 1.7 years left rather than the 3 years he had when Arsenal bought him, the same player is worth less to a buyer today. The anchor moves the model up by 12.8%; it does not set the value to £105m or £127m.

**Why the model is below the restated fee.** The restated fee assumes the 2023 price grows with football inflation. It does not account for the shorter contract, the possibility that Arsenal overpaid in a competitive auction, or the fact that a buyer today would not pay a 2023 price for a player two years older with 1.7 years left. The model applies those discounts explicitly.

**Why the model is close to ETV.** Both see a proven 27-year-old midfielder with a long record and a contract that still has value. The 5.0% gap is well inside the model's range. This is the case where the three signals agree, and the product can say so without pretending to know the "true" number.

### What the club sees

```text
┌──────────────────────────────────────────────────────────────────┐
│ Declan Rice · Arsenal · Midfielder · 27                          │
│                                                                  │
│ TransferX model      £81.2m    Range £69m–£93m      Medium       │
│ Market estimate      £85.5m    SciSports ETV · 1 Sep 2026        │
│ Last reported fee    £105m     Jul 2023 · West Ham → Arsenal      │
│                      £127.3m today · reported, not verified       │
│                                                                  │
│ Fee anchor ×1.13 · Contract to Jun 2028 · Model 5% below market   │
└──────────────────────────────────────────────────────────────────┘
```

### Before and after

| | Before (30 Oct demo) | After (this sample) |
|---|---|---|
| Headline | £45m, unexplained | £81.2m, with a range and a confidence |
| Last fee | Not shown | £105m, July 2023, with the clubs and the source |
| Market cross-check | None | £85.5m, named provider, dated |
| Contract | Not visible in the valuation | 1.7 years left, shown as the main discount |
| What the audience concludes | "The model is wrong" | "The model disagrees with the fee for a reason, and the market agrees with the model" |

---

## Case 2 — Cole Palmer: when the last fee should not anchor

**Profile.** Cole Palmer, born 6 May 2002, age 24, Chelsea, attacking midfielder/right winger, contract to 30 June 2033 (about 6.7 years remaining), England international.

**The last transfer.** Manchester City → Chelsea, September 2023. Reported £40m plus up to £2.5m in add-ons. At the time, Palmer was a 21-year-old with limited Premier League minutes. The fee priced potential, not a finished player.

### The three signals

| Signal | Value | Source and date | What it tells us |
|---|---|---|---|
| TransferX model | **£78.0m** (range £66m–£90m) | Illustrative; proposed `market-v3` | A 24-year-old with a long contract and elite output is not a £33m player |
| Market estimate | **£85.5m** (range £71.5m–£87.4m) | SciSports ETV via FootballTransfers, 2026 (€100m central; €103.5m in the most-valuable list) | The market prices him well above the fee |
| Last reported fee | **£40m** in September 2023 | Public reports; not verified by TransferX | The last fee describes a different, much less proven player |
| Restated fee | **£48.1m** today | £40m × 1.06^3.16 | Time value only |
| Market consensus | **Single-source £85.5m** | One provider | Labelled "single-source" |

### The fee anchor is deliberately not applied

A naive anchor would say: "Chelsea paid £40m in 2023; restated to £48.1m; therefore Palmer is worth about £50m." That would repeat the original error in the other direction. The model recognises that the fee was paid for a 21-year-old with potential, and that the player has since become one of the most productive attackers in the league.

The proposed guardrail:

> **Skip the anchor when the player has demonstrably outgrown the fee.** Conditions: age under 25, fee older than two years, and the performance score has improved by 15 points or more since the transfer. The fee describes a different player; use it as context, not as an anchor.

Palmer meets all three conditions. The model shows the decision explicitly:

```text
Fee anchor: not applied
  Reason: player outgrown the fee
  Last fee £40m (Sep 2023) restated to £48.1m
  Performance score then 58 → now 78 (+20)
  Age 21 → 24; contract now to 2033
  The fee priced potential; the model prices current output
```

This is a stronger answer than a mechanical anchor. It shows that the system knows *when not to use* the last fee, which is exactly the kind of judgement a club's analysts will test.

### What the club sees

```text
┌──────────────────────────────────────────────────────────────────┐
│ Cole Palmer · Chelsea · Attacking midfielder · 24                │
│                                                                  │
│ TransferX model      £78.0m    Range £66m–£90m      Medium       │
│ Market estimate      £85.5m    SciSports ETV · 2026              │
│ Last reported fee    £40m      Sep 2023 · Man City → Chelsea      │
│                      £48.1m today · reported                      │
│                                                                  │
│ Fee anchor not applied — outgrown · Market 9.6% above model       │
└──────────────────────────────────────────────────────────────────┘
```

**Reading the gap.** The market estimate is 9.6% above the model. The model is more conservative on a player with one outstanding season at the time of the estimate and a very long contract; ETV gives more weight to his ceiling and his brand. Both are within the model's range (£66m–£90m), so the product shows the disagreement rather than hiding it.

---

## Case 3 — Lamine Yamal: no fee, and providers disagree

**Profile.** Lamine Yamal, born 13 July 2007, age 19, Barcelona, forward, contract to 30 June 2031 (about 4.7 years remaining), Spain international. No transfer fee: he came through La Masia.

### The three signals

| Signal | Value | Source and date | What it tells us |
|---|---|---|---|
| TransferX model | **£160.0m** (range £130m–£190m) | Illustrative; Low confidence | The model is deliberately conservative on a teenager with a short record |
| Market estimate | **£193.1m** | SciSports ETV via FootballTransfers, October 2026 (€225.9m) | The market prices the ceiling |
| Last reported fee | **None** | Academy graduate | No fee anchor is possible |
| Market consensus | **Single-source £193.1m** | One integrated provider | "Single-source", not "consensus" |

**Public model dispersion (context, not integrated):**

| Model | Value | GBP equivalent | Gap vs ETV |
|---|---|---|---|
| SciSports ETV | €225.9m | £193.1m | — |
| CIES Football Observatory | €358.1m | £306.1m | +58% |
| xTV (Soccerment) | €253.6m | £216.8m | +12% |

The three public models disagree by up to 58%. That is not a reason to pick the highest or the lowest; it is a reason to show a range and to label the estimate as uncertain. ETV is the only one integrated through a licensed API, so it is the only one displayed as a market estimate; CIES and xTV are context in the report, not product data.

**What the model can say without a fee:** Yamal's value is driven by age, potential, contract length and performance. The model's Low confidence is honest: a 19-year-old with fewer than three full seasons is exactly the case where a point estimate is least reliable. The UI should lead with the range, not the point.

---

## Case 4 — Erling Haaland: a release clause is not a market fee

**Profile.** Erling Haaland, born 21 July 2000, age 26, Manchester City, striker, contract to 30 June 2034 (about 7.7 years remaining), Norway international.

### The three signals

| Signal | Value | Source and date | What it tells us |
|---|---|---|---|
| TransferX model | **£130.0m** (range £110m–£150m) | Illustrative; High confidence | Elite output, long contract, peak age |
| Market estimate | **£136.2m** | SciSports ETV via FootballTransfers, 2026 (€159.3m) | The market is within 5% of the model |
| Last reported fee | **€60m release clause**, July 2022 | Public reports; not verified by TransferX | A contract term, not a market clearing price |
| Restated fee | **£65.9m** today | €60m ≈ £51.3m × 1.06^4.3 | Time value only |
| Market consensus | **Single-source £136.2m** | One provider | Labelled "single-source" |

**Why the anchor is not applied.** A release clause is a negotiated ceiling that a club accepts to secure a player, not the price a competitive market would set. The model gives it a source credibility of 0.40 and a fee-basis weight of 0.40; with 4.3 years of recency decay, the combined weight falls below the 0.25 threshold. The anchor is skipped, and the reason is shown.

This is the right outcome: a £60m clause from 2022 is not evidence that Haaland is worth £66m today. The long contract and the market estimate carry the value.

---

## Case 5 — Coverage gap: a Championship striker

**Profile.** A 24-year-old Championship striker, contract to June 2029, last permanent move in 2024 for a reported £2.0m. No licensed market-value provider covers him at the required match confidence.

### The three signals

| Signal | Value | Source and date | What it tells us |
|---|---|---|---|
| TransferX model | **£3.8m** (range £3.3m–£4.4m) | Illustrative; Low confidence | The model can still value him from performance and contract |
| Market estimate | **None** | No licensed coverage | Do not invent a market number |
| Last reported fee | **£2.0m** in 2024 | Public reports; not verified | A recent, relevant anchor |
| Restated fee | **£2.3m** today | £2.0m × 1.06^2.3 | Time value only |
| Market consensus | **None** | Zero providers | The UI says "No licensed market estimate" |

**The anchor applies here.** The fee is recent (2.3 years), the player is 24, the transfer was permanent and disclosed, and his performance has improved but not beyond the "outgrown" guardrail:

```text
Restated fee                       £2.3m
Performance ratio                  1.350
Contract ratio                     0.940
Availability ratio                 0.970
Anchor value                       £2.8m
Model before anchor                £4.6m
Ratio                              0.613
Weight                             0.368
Factor                             ×0.835
Model after anchor                 £3.8m
```

This is a useful failure mode to show: the model was over-predicting a small fee (the known +118% bias for fees under £5m), and the anchor pulled it down. With no market coverage, the product says so plainly:

```text
TransferX model      £3.8m     Range £3.3m–£4.4m     Low
Market estimate      None      No licensed provider covers this player
Last reported fee    £2.0m     2024 · reported
```

**No provider? Say no provider.** A missing market value is better than a wrong one, and much better than a blank screen. The model, the range and the last fee still give the user something honest.

---

## What the club sees: the valuation stack

The full card, using Rice and Palmer as the two states:

### State A — model, market and last fee all available

```text
┌──────────────────────────────────────────────────────────────────┐
│ Declan Rice · Arsenal · Midfielder · 27                          │
│                                                                  │
│ TransferX model      £81.2m    Range £69m–£93m      Medium       │
│ Market estimate      £85.5m    SciSports ETV · 1 Sep 2026        │
│ Last reported fee    £105m     Jul 2023 · West Ham → Arsenal      │
│                      £127.3m today · reported, not verified       │
│                                                                  │
│ Fee anchor ×1.13 · Contract to Jun 2028 · Model 5% below market   │
│ [Why this number?]                                               │
└──────────────────────────────────────────────────────────────────┘
```

### State B — market available, anchor deliberately skipped

```text
┌──────────────────────────────────────────────────────────────────┐
│ Cole Palmer · Chelsea · Attacking midfielder · 24                │
│                                                                  │
│ TransferX model      £78.0m    Range £66m–£90m      Medium       │
│ Market estimate      £85.5m    SciSports ETV · 2026              │
│ Last reported fee    £40m      Sep 2023 · Man City → Chelsea      │
│                      £48.1m today · reported                      │
│                                                                  │
│ Fee anchor not applied — outgrown · Market 9.6% above model       │
│ [Why this number?]                                               │
└──────────────────────────────────────────────────────────────────┘
```

### The breakdown popover

```text
Why £81.2m?
  Performance        Strong: three seasons of high minutes
  League             Premier League (×1.00)
  Age                27, at peak
  Contract           1.7 years left (the main discount)
  Availability       95% available
  Market comps       Similar midfield transfers (×1.08)
  Last fee anchor    ×1.13 — £105m in 2023, restated £127.3m
  Release clause     None

  Range              £69m–£93m
  Confidence         Medium
  Market cross-check SciSports ETV £85.5m, 1 Sep 2026
  Last fee           £105m, Jul 2023, West Ham → Arsenal (reported)
```

The popover never shows a single multiplier without a label. Every input is one a club analyst can challenge, and every external number carries a source and a date.

---

## Market consensus: what it looks like with two providers

The public sample only has one integrated provider per player, so the report shows the single-source state. The layout below illustrates the consensus state. **The second provider value is illustrative; it is not a published quote.**

| Provider | Value | As of | Weight | Match confidence |
|---|---|---|---|---|
| SciSports ETV | £85.5m | 1 Sep 2026 | 0.55 | 0.99 |
| Provider B (illustrative) | £82.0m | 1 Sep 2026 | 0.45 | 0.97 |
| **Market consensus** | **£83.9m** | 1 Sep 2026 | — | — |

Dispersion: `|85.5 − 82.0| / 83.9 = 4.2%` — providers agree.

Rules shown by the layout:
- The consensus is a **weighted mean for two providers**; a weighted median is used when there are three or more.
- No provider may carry more than 60% of the weight.
- Only values with `match_confidence ≥ 0.90` and an `as_of` inside the freshness window are included.
- With one provider, the label is **"Single-source market estimate"**, not "consensus".
- The consensus is **not** blended into the TransferX model. It is a separate line, with its own value, range and dispersion.

---

## Before and after

| | Today | After this plan |
|---|---|---|
| What the user sees | One number, a range and a confidence, with no external reference | Three signals: the model, the licensed market estimate(s), and the last reported fee |
| Rice | £45m | £81.2m model · £85.5m market · £105m last fee (restated £127.3m) |
| Palmer | £33m | £78.0m model · £85.5m market · £40m last fee (anchor skipped: outgrown) |
| Yamal | A model number with no fee context | £160m model · £193.1m ETV · no fee; range and Low confidence lead |
| Haaland | A model number with no fee context | £130m model · £136.2m ETV · €60m release clause, not used as an anchor |
| A Championship player | A model number, possibly no provider | £3.8m model · no market estimate, stated plainly · £2.0m last fee |
| Provenance | None | Provider, as-of date, match confidence, fee source, anchor decision |
| Disagreement | Hidden | Shown, with the size of the gap |

The improvement is not only that the numbers move. It is that the user can see **why** they move, **who** says what, and **when** they said it. That is what makes the number defensible in a demo and in a club's investment committee.

---

## Data sources and caveats

### Sources

| Item | Source | Date | Verified by TransferX? |
|---|---|---|---|
| Declan Rice ETV | FootballTransfers / SciSports ETV, €100m (range €83.7m–€102.3m) | 1 Sep 2026 | No — public figure |
| Declan Rice last fee | Public reports, £105m including add-ons | Jul 2023 | No — reported |
| Cole Palmer ETV | FootballTransfers / SciSports ETV, €100m central (€103.5m in the most-valuable list) | 2026 | No — public figure |
| Cole Palmer last fee | Public reports, £40m plus add-ons | Sep 2023 | No — reported |
| Lamine Yamal ETV | FootballTransfers / SciSports ETV, €225.9m | Oct 2026 | No — public figure |
| Yamal comparison values | CIES €358.1m; xTV €253.6m | 2026 | No — public figures, not integrated |
| Erling Haaland ETV | FootballTransfers / SciSports ETV, €159.3m | 2026 | No — public figure |
| Haaland last fee | Public reports, €60m release clause | Jul 2022 | No — reported |
| TransferX model values | Constructed for this sample | 2026-10-31 | **Illustrative — not production values** |

### Caveats

1. **This is a design sample, not a valuation report.** Do not send it to a club, agent or player as-is.
2. **The TransferX model values are illustrative.** Replace them with production `market-v3` outputs before any external use.
3. **The provider values are opinions, not facts.** ETV is a licensed estimate, not an official price. CIES and xTV are context only.
4. **The fees are reported, not verified.** TransferX's own completed deals are the only verified fees; the rest carry `is_reported = true`.
5. **The FX rate is the model's static fallback.** A production report should use the ECB rate on the report date.
6. **Contract dates are public reporting.** Verify them against the vendor feed before relying on them.
7. **The second provider in the consensus illustration is synthetic.** It exists to show the layout, not to assert a value.
8. **A range is not a guarantee.** The model's confidence is a statement about its inputs, not a probability that the true value lies inside the range.

---

## Appendix — the one-line summary for a demo

If a demo needs a single sentence per player, use these. They are deliberately short, and they never say "true value":

- **Rice:** "Our model says £81.2m; the market says £85.5m; the last fee was £105m in 2023, but he has 1.7 years left on his contract, which is why the model is below the fee."
- **Palmer:** "Our model says £78m; the market says £85.5m; Chelsea paid £40m in 2023, but he has outgrown that fee, so we do not anchor to it."
- **Yamal:** "Our model says £160m; ETV says £193m; there is no transfer fee, and the public models disagree by up to 58%, so we show a range and low confidence."
- **Haaland:** "Our model says £130m; ETV says £136m; his last 'fee' was a €60m release clause, which is not a market price, so we do not anchor to it."
- **Championship player:** "Our model says £3.8m; no licensed provider covers him; his last fee was £2m, and we show that rather than inventing a market number."
