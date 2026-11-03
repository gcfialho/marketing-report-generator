# Marketing Funnel Report: Example Co.

- **Objective:** Maximise free-trial registrations
- **Data source:** `synthetic (rows=1000, seed=42)`
- **Opt-in period covered:** 2023-01-15 to 2023-11-30
- **Generated:** 2026-11-03 12:00
- **Significance level:** α = 0.05

## Executive summary

- 108 of 1,000 prospects registered for a trial (10.8%).
- Weakest funnel step: Demo attendance (attended / demo outcome known) at 26.2% (234 of 894).
- Conversion rates by channel do not differ significantly (Monte Carlo chi-square p = 0.066; expected counts too small for the asymptotic test, Holm-adjusted p = 0.132, Cramér's V = 0.08).
- Conversion rates by job category differ significantly (chi-square = 11.61, df = 3, p = 0.009, Holm-adjusted p = 0.027, Cramér's V = 0.11).
- Conversion rates by region do not differ significantly (chi-square = 1.86, df = 3, p = 0.601, Holm-adjusted p = 0.601, Cramér's V = 0.04).

## 1. Funnel

`Prospect Status` records the furthest stage each prospect reached:
Responded → (No Show | Attended) → Registered. Stages are therefore cumulative:
every registered prospect also attended a demo.

| Status | Prospects | Share |
|---|---:|---:|
| Responded | 106 | 10.6% |
| No Show | 660 | 66.0% |
| Attended | 126 | 12.6% |
| Registered | 108 | 10.8% |
| **Total** | **1,000** | 100.0% |

| Funnel step | Converted | Base | Rate |
|---|---:|---:|---:|
| Demo attendance (attended / demo outcome known) | 234 | 894 | 26.2% |
| Trial registration (registered / attended) | 108 | 234 | 46.2% |
| Overall (registered / all prospects) | 108 | 1,000 | 10.8% |

106 prospects are still at *Responded* (no demo outcome recorded) and are
excluded from the attendance-rate base.

![Funnel](charts/funnel.png)

## 2. Channel performance

| Prospect Source | Prospects | Registered | Rate | 95% CI | Volume share | Adj. p vs rest |
|---|---:|---:|---:|---:|---:|---:|
| Trade Show | 126 | 20 | 15.9% | 10.5% to 23.2% | 12.6% | 0.256 |
| Referral | 33 | 5 | 15.2% | 6.7% to 30.9% | 3.3% | 0.487 |
| Advertisement | 818 | 83 | 10.1% | 8.3% to 12.4% | 81.8% | 0.487 |
| Social Media | 23 | 0 | 0.0% | 0.0% to 14.3% | 2.3% | 0.487 |

![Channel conversion](charts/channel_rates.png)

*Chi-square test of independence: χ² = 7.16, df = 3, p = 0.067, Cramér's V = 0.08. Caution: smallest expected count is 2.5 and 25% of cells are below 5, so the chi-square approximation is unreliable. Monte Carlo test with fixed margins (9,999 simulated tables): p = 0.066. Holm-adjusted across the channel, job category and region tests: p = 0.132.*

**Where each channel loses prospects.** A channel's overall rate is the product of three
shares: prospects with a demo outcome recorded, demo attendance, and trial registration after
attending. The table splits out the last two, so prospects still at *Responded* do not dilute
either step.

| Prospect Source | Prospects | Pending | Demo attendance | 95% CI | Trial registration | 95% CI |
|---|---:|---:|---:|---:|---:|---:|
| Advertisement | 818 | 86 | 25.0% (183/732) | 22.0% to 28.3% | 45.4% (83/183) | 38.3% to 52.6% |
| Trade Show | 126 | 15 | 31.5% (35/111) | 23.6% to 40.7% | 57.1% (20/35) | 40.9% to 72.0% |
| Referral | 33 | 3 | 33.3% (10/30) | 19.2% to 51.2% | 50.0% (5/10) | 23.7% to 76.3% |
| Social Media | 23 | 2 | 28.6% (6/21) | 13.8% to 50.0% | 0.0% (0/6) | 0.0% to 39.0% |

## 3. Audience and geography

### Job category

| Job Category | Prospects | Registered | Rate | 95% CI | Volume share | Adj. p vs rest |
|---|---:|---:|---:|---:|---:|---:|
| Other | 48 | 11 | 22.9% | 13.3% to 36.5% | 4.8% | 0.054 |
| Decision Maker | 138 | 20 | 14.5% | 9.6% to 21.3% | 13.8% | 0.419 |
| Practitioner | 700 | 69 | 9.9% | 7.9% to 12.3% | 70.0% | 0.419 |
| Executive | 114 | 8 | 7.0% | 3.6% to 13.2% | 11.4% | 0.419 |

![Job category conversion](charts/job_category_rates.png)

*Chi-square test of independence: χ² = 11.61, df = 3, p = 0.009, Cramér's V = 0.11. Holm-adjusted across the channel, job category and region tests: p = 0.027.*

### Region

| Geographic Region | Prospects | Registered | Rate | 95% CI | Volume share | Adj. p vs rest |
|---|---:|---:|---:|---:|---:|---:|
| Asia Pacific | 183 | 22 | 12.0% | 8.1% to 17.5% | 18.3% | 1.000 |
| North America | 390 | 45 | 11.5% | 8.7% to 15.1% | 39.0% | 1.000 |
| Europe | 319 | 33 | 10.3% | 7.5% to 14.2% | 31.9% | 1.000 |
| Latin America | 108 | 8 | 7.4% | 3.8% to 13.9% | 10.8% | 1.000 |

*Chi-square test of independence: χ² = 1.86, df = 3, p = 0.601, Cramér's V = 0.04. Holm-adjusted across the channel, job category and region tests: p = 0.601.*

### Country

| Country | Prospects | Registered | Rate | 95% CI | Volume share | Adj. p vs rest |
|---|---:|---:|---:|---:|---:|---:|
| ARG | 24 | 4 | 16.7% | 6.7% to 35.9% | 2.4% | 1.000 |
| FRA | 44 | 6 | 13.6% | 6.4% to 26.7% | 4.4% | 1.000 |
| MEX | 53 | 7 | 13.2% | 6.5% to 24.8% | 5.3% | 1.000 |
| CHN | 84 | 11 | 13.1% | 7.5% to 21.9% | 8.4% | 1.000 |
| IND | 72 | 9 | 12.5% | 6.7% to 22.1% | 7.2% | 1.000 |
| USA | 262 | 32 | 12.2% | 8.8% to 16.7% | 26.2% | 1.000 |
| GBR | 161 | 18 | 11.2% | 7.2% to 17.0% | 16.1% | 1.000 |
| DEU | 9 | 1 | 11.1% | 2.0% to 43.5% | 0.9% | 1.000 |
| ESP | 98 | 8 | 8.2% | 4.2% to 15.3% | 9.8% | 1.000 |
| CAN | 75 | 6 | 8.0% | 3.7% to 16.4% | 7.5% | 1.000 |
| JPN | 27 | 2 | 7.4% | 2.1% to 23.4% | 2.7% | 1.000 |
| BRA | 84 | 4 | 4.8% | 1.9% to 11.6% | 8.4% | 0.859 |
| ITA | 7 | 0 | 0.0% | 0.0% to 35.4% | 0.7% | 1.000 |

*Chi-square test of independence: χ² = 8.45, df = 12, p = 0.749, Cramér's V = 0.09. Caution: smallest expected count is 0.8 and 19% of cells are below 5, so the chi-square approximation is unreliable. Monte Carlo test with fixed margins (9,999 simulated tables): p = 0.758.*

## 4. Multivariable logistic regression

Model: `is_registered ~ Prospect Source + Geographic Region + Job Category` on 977 prospects
(108 registrations). Odds ratios are relative to the reference level of each
variable (Prospect Source = Advertisement; Geographic Region = North America; Job Category = Practitioner),
holding the other variables fixed.

| Term | Odds ratio | 95% CI | p-value |
|---|---:|---:|---:|
| Prospect Source: Referral | 1.73 | 0.65 to 4.63 | 0.277 |
| Prospect Source: Trade Show | 1.69 | 0.99 to 2.88 | 0.056 |
| Geographic Region: Asia Pacific | 1.10 | 0.63 to 1.90 | 0.743 |
| Geographic Region: Europe | 0.91 | 0.56 to 1.47 | 0.703 |
| Geographic Region: Latin America | 0.57 | 0.26 to 1.27 | 0.170 |
| Job Category: Decision Maker | 1.54 | 0.90 to 2.63 | 0.118 |
| Job Category: Executive | 0.72 | 0.34 to 1.55 | 0.401 |
| Job Category: Other | 3.02 | 1.45 to 6.27 | 0.003 |

McFadden pseudo-R² = 0.024; likelihood-ratio test against the
intercept-only model: p = 0.036.
Term p-values are not adjusted for the 8 terms tested, so a single small
p-value here is a lead to check, not a finding on its own.

Excluded from the model because they are too small or have no variation in the outcome
(maximum likelihood cannot estimate them): Prospect Source: Social Media.
These levels still appear in the descriptive tables above.

## 5. Channel actions and volume-mix scenario

A channel is marked *Increase* or *Decrease* only when its registration rate differs from
the other channels at Holm-adjusted p < 0.05 (Fisher's exact test); otherwise *Hold*.
The scenario multiplies each channel's share of prospect volume by
1.25 / 0.75 / 1.0 and renormalises to 100%.
The dataset contains **no spend or cost data**, so these are shares of prospect volume, not of
budget, and no ROI or CAC figures are implied.

*Detectable if true rate is* shows how far a channel's true registration rate would have to be
from the other channels' rate for this test to flag it with 80% power at the current volume
(normal approximation with Cohen's h at α / number of channels, Holm's strictest step).
A *Hold* inside that range means "not enough data to tell", not "no difference".

| Channel | Action | Current volume share | Scenario share | Detectable if true rate is | Rationale |
|---|---|---:|---:|---|---|
| Trade Show | Hold | 12.6% | 12.6% | below 2.7% or above 21.5% | No significant difference vs. other channels (adj. p = 0.256) |
| Referral | Hold | 3.3% | 3.3% | below 0.1% or above 34.5% | No significant difference vs. other channels (adj. p = 0.487) |
| Advertisement | Hold | 81.8% | 81.8% | below 5.8% or above 24.4% | No significant difference vs. other channels (adj. p = 0.487) |
| Social Media | Hold | 2.3% | 2.3% | above 40.6% | No significant difference vs. other channels (adj. p = 0.487) |

## 6. Data quality

- Input rows: 1,003 across 14 columns; cell completeness 91.7%.
- Duplicate prospect IDs in the input: 3.
- Missing values by column: Opt-In (14), Opt-In Source (125), Opt-In Timestamp (50), Opt-Out Timestamp (975).
- Rows after cleaning: 1,000 (removed: 0 empty, 0 invalid status, 3 duplicates).

Cleaning steps:
1. Trimmed and collapsed whitespace in text columns; blank strings set to missing
2. Standardised country names to ISO 3166-1 alpha-3 codes
3. Standardised Prospect Status values
4. Parsed opt-in/opt-out timestamps (unparseable values set to missing)
5. Removed 3 duplicate prospect rows (kept furthest funnel stage, then most recent opt-in)

## 7. Methodology and limitations

- Rates use 95% Wilson score intervals, which remain valid for small segments and rates near 0%.
- Segment differences are tested with a chi-square test of independence on the
  segment × registered table, with Cramér's V as effect size. When expected counts are too small
  for the chi-square approximation, the verdict uses Fisher's exact test (two levels) or a Monte
  Carlo test with fixed margins (more levels). The channel, job category and region tests in the
  executive summary are Holm-corrected as one family.
- Per-segment comparisons use Fisher's exact test (segment vs. all others) with Holm correction
  for multiple comparisons.
- The logistic regression uses one-hot (treatment) coding; odds ratios are associations, not
  causal effects. Prospect source is a single-touch attribution field and campaigns were not
  randomised.
- No cost data is available, so cost-efficiency (CPA, ROAS) cannot be estimated.
- Job categories and seniority are derived from free-text job titles with keyword rules and will
  misclassify some titles.
