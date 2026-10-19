# Design decisions

This document records the methodology behind the pipeline and the trade-offs taken.
It complements the README, which covers usage.

## 1. Which data points matter

| Field | Why it matters | Handling |
|---|---|---|
| `Prospect ID` | Primary key for deduplication and tracking | One row per prospect after cleaning |
| `Prospect Status` | The funnel outcome: Responded → (No Show \| Attended) → Registered | Standardised to four values; rows with other values are dropped and counted |
| `Prospect Source` | Channel attribution, the main lever for budget decisions | Analysed directly and grouped into channel families |
| `Country` | Geographic performance; arrives as free text | Mapped to ISO 3166-1 alpha-3, then to regions |
| `Job Title` | Audience segmentation (practitioner, decision maker, executive) | Keyword rules on whole words |
| Opt-in / opt-out timestamps | Timing, recency and the data period covered | Parsed to datetimes; used to break ties when deduplicating |

## 2. Funnel definition

`Prospect Status` stores the **furthest** stage a prospect reached, so stages are cumulative:
a registered prospect also attended the demo. The pipeline therefore defines:

- **Attended (cumulative)** = `Attended` + `Registered`
- **Demo attendance rate** = attended / (attended + no-show). Prospects still at
  `Responded` have no demo outcome yet and are left out of this base.
- **Trial registration rate** = registered / attended
- **Overall conversion** = registered / all prospects

The *bottleneck* is the step with the lowest rate. It is not simply the most common status.

## 3. Cleaning rules

- Text fields are trimmed and internal whitespace is collapsed. Missing values stay missing
  and are never turned into the string `"nan"`.
- Country spellings and aliases (`USA`, `U.S.`, `Deutschland`, ...) map to ISO-3 codes.
  Unknown countries are kept as title-cased text and listed in the report.
- Duplicate prospects keep the row with the **furthest funnel stage**, then the most recent
  opt-in. Keeping only the most recent touch could throw away a registration.

## 4. Statistical methods and why

| Question | Method | Reason |
|---|---|---|
| How precise is a segment's rate? | Wilson score interval (95%) | Stays inside [0, 1] and works for small samples. A channel with 0 of 14 registrations has an upper bound of about 21%, not a certain 0% |
| Do segments differ at all? | Chi-square test of independence on segment × registered, with Cramér's V | Answers the conversion question directly. Expected-count rules are checked and flagged |
| Which segments differ from the rest? | Fisher's exact test per segment vs. all others, Holm-adjusted | Exact for small cells. Holm controls the family-wise error rate across many comparisons |
| What is associated with registration when channel, region and role are considered together? | Logistic regression with one-hot (treatment) coding, reported as odds ratios with 95% CIs | Categorical predictors must not be label-encoded as integers. Odds ratios against a stated reference level are interpretable |

Levels with too few rows, or with no variation in the outcome, cause quasi-complete separation
in maximum-likelihood logistic regression. The pipeline excludes those rows from the model,
says so in the report, and still shows the levels in the descriptive tables.

## 5. From analysis to recommendations

1. **Performance baseline**: conversion rate by channel, with uncertainty.
2. **Cost efficiency**: cost per acquisition by source. *Not possible with this dataset*,
   because it has no spend data. The report says so instead of implying ROI figures.
3. **Trend analysis**: performance over time, using the opt-in timestamps (roadmap).
4. **Bottleneck identification**: the funnel step with the largest drop-off.
5. **Reallocation scenarios**: a channel is marked *Increase* or *Decrease* only when its
   difference from the other channels is statistically significant. The scenario then shifts
   **volume share** with fixed multipliers and renormalises to 100%.

## 6. Production data layout

For a recurring, production version of this analysis, a layered warehouse layout fits:

```
Raw layer      direct ingestion from source systems, minimal transformation
Trusted layer  fact table prospect_interactions (daily grain)
               dimensions dim_channels, dim_geography, dim_job_titles, dim_time
Refined layer  pre-aggregated tables for dashboards: channel performance,
               conversion funnels, geographic summaries
```

On GCP this maps to Cloud Storage for landing files, Dataflow for moving data between layers,
BigQuery (with stored procedures for incremental updates instead of full refreshes) as the
warehouse, and Cloud Composer (Airflow) for daily and hourly orchestration.

## 7. Visualisation

- An executive summary with the key KPIs first, then drill-down from high-level metrics to
  segment detail.
- Chart choices: a funnel for stage conversion, bar charts with confidence intervals for
  channel and audience comparisons, time series for trends, and geographic views for regions.
- For a live dashboard: BigQuery as the warehouse, a BI layer such as Looker Studio, and
  automated refresh schedules.

## 8. Communicating results to non-technical stakeholders

- Lead with business impact and the decision being asked for.
- Use visual before/after comparisons.
- Make every metric lead to an action. Where the data cannot support a claim (for example
  ROI without cost data), say so explicitly.
- Provide a phased implementation plan with checkpoints, and explain how performance will be
  monitored and adjusted.
