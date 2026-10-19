# Marketing Report Generator

A Python pipeline that turns a prospect-level marketing export into a funnel and channel report with statistical tests attached: confidence intervals, significance tests and a multivariable model.

[![CI](https://github.com/gcfialho/marketing-report-generator/actions/workflows/ci.yml/badge.svg)](https://github.com/gcfialho/marketing-report-generator/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

![Registration rate by prospect source, with 95% Wilson intervals](examples/synthetic/charts/channel_rates.png)

*Chart from the example report in [`examples/synthetic/`](examples/synthetic/example-co-marketing-report.md), generated from synthetic data.*

## What it does

Marketing teams often have to decide where next quarter's effort goes using a single CRM export. That export has no cost data, inconsistent country spellings, duplicate contacts and segments with a few dozen rows. A rate such as "Referral converts at 25%" means little without its sample size.

This project automates that analysis end to end:

- **Validates and cleans** the export. It normalises whitespace, maps countries to ISO-3 codes, standardises funnel statuses and keeps one row per prospect.
- **Builds features**: job category and seniority from free-text titles, region from country, and cumulative funnel flags.
- **Analyses** the demo funnel (Responded → No Show | Attended → Registered) and the registration rate by channel, job category, region and country. Every rate gets an uncertainty estimate.
- **Recommends** channel actions only where the data supports them, and labels the result as a volume-mix scenario because the input has no spend data.
- **Writes** a Markdown report with charts, plus an optional PDF and a cleaned CSV.

It runs on any CSV or Excel file with the expected columns. It also runs on seeded **synthetic data** that has the same schema, so no proprietary data is needed.

## Architecture

```mermaid
flowchart LR
    A[CSV / Excel export<br/>or synthetic generator] --> B[validation<br/>schema + quality checks]
    B --> C[cleaning<br/>normalise, ISO-3, dedup]
    C --> D[transform<br/>job category, region,<br/>funnel flags]
    D --> E[analysis + stats<br/>funnel, Wilson CIs,<br/>chi-square, Fisher/Holm, logit]
    E --> F[report<br/>Jinja2 Markdown, charts,<br/>optional PDF]
    D --> G[(prospects_clean.csv)]
```

| Module | Responsibility |
|---|---|
| `validation.py` | Load CSV/Excel, check required columns, profile missing values, duplicates and unknown statuses |
| `cleaning.py` | Whitespace and missing-value normalisation, country and status standardisation, prospect deduplication |
| `transform.py` | Whole-word keyword rules for job category, seniority and channel group; ISO-3 to region; cumulative funnel flags |
| `stats.py` | Wilson intervals, chi-square with Cramér's V, Fisher's exact test with Holm correction, treatment-coded logistic regression |
| `analysis.py` | Funnel steps and bottleneck, segment tables, findings, evidence-gated channel actions |
| `report.py`, `charts.py` | Jinja2 Markdown template, matplotlib charts, optional PDF via `markdown-pdf` |
| `pipeline.py`, `cli.py` | Orchestration with per-step timing and logging; the `marketing-report` CLI |
| `synthetic.py` | Seeded generator with the same 14-column schema and realistic data-quality issues |

## Quickstart

Requires [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/gcfialho/marketing-report-generator.git
cd marketing-report-generator
uv sync

# Run on synthetic data (the default when no input is given)
uv run marketing-report run --output-dir output

# Run on your own export
uv run marketing-report run --input path/to/prospects.xlsx --company "Acme Corp"
```

Output in `output/`: `<company>-marketing-report.md`, `charts/*.png` and `prospects_clean.csv`.

For PDF output, install the optional extra. It pulls in PyMuPDF, which is a large dependency:

```bash
uv sync --extra pdf
uv run marketing-report run --pdf
```

## CLI usage

```text
marketing-report run   [-i INPUT | --synthetic] [--rows N] [--seed S] [-o OUTPUT_DIR]
                       [--company NAME] [--objective TEXT] [--alpha 0.05]
                       [--pdf] [--no-clean-export]
marketing-report synth -o OUTPUT.{csv,xlsx} [--rows N] [--seed S] [--tidy]
```

| Option | Default | Environment variable |
|---|---|---|
| `--input` | none (synthetic data) | `MARKETING_REPORT_INPUT` |
| `--output-dir` | `output` | `MARKETING_REPORT_OUTPUT_DIR` |
| `--company` | `Example Co.` | `MARKETING_REPORT_COMPANY` |
| `--objective` | `Maximise free-trial registrations` | `MARKETING_REPORT_OBJECTIVE` |

`synth` writes a synthetic dataset to disk. `--tidy` turns off the injected data-quality issues.

### Input schema

Required: `Prospect Status`, `Prospect Source`, `Country`, `Job Title`.
Optional: `Campaign ID`, `Campaign Name`, `Account ID`, `Account Name`, `domain`, `Prospect ID`, `Opt-In`, `Opt-In Source`, `Opt-In Timestamp`, `Opt-Out Timestamp`.
`Prospect Status` must be one of `Responded`, `No Show`, `Attended` or `Registered`; common spelling variants are mapped automatically.

## Project structure

```text
├── src/marketing_report/     # the package (see the module table above)
│   └── templates/report.md.j2
├── tests/                    # unit tests + end-to-end tests on synthetic data
├── examples/synthetic/       # example report generated with the default seed
├── docs/design-decisions.md  # methodology and trade-offs
├── .github/workflows/ci.yml  # ruff, pytest and a CLI smoke test
└── pyproject.toml / uv.lock
```

## Analytical methods and why

| Question | Method | Why this method |
|---|---|---|
| How far do prospects get? | Cumulative funnel. Attendance rate = attended / (attended + no-show); registration rate = registered / attended | `Prospect Status` stores the furthest stage reached, so stages must be cumulative. The bottleneck is the weakest step, not the most common status |
| How reliable is a segment's rate? | 95% Wilson score interval | Stays valid for small segments and 0% rates. A channel with 0 of 14 registrations has an upper bound of about 21%, which is not evidence that the channel never converts |
| Do segments convert differently? | Chi-square test on segment × registered, with Cramér's V | Tests the conversion question directly. The report flags low expected counts |
| Which segments stand out? | Fisher's exact test against all other prospects, Holm-adjusted | Exact for small cells, and corrected for testing many segments at once |
| What matters when channel, region and role are considered together? | Logistic regression with treatment coding, reported as odds ratios with 95% CIs | Nominal variables are not integer-encoded. Levels that would cause separation are excluded and listed in the report |
| Where should effort move? | *Increase*/*Decrease* only at adjusted p < α, otherwise *Hold*; volume shares renormalised to 100% | Avoids acting on noise. The report says explicitly that the input has no spend data |

More detail: [docs/design-decisions.md](docs/design-decisions.md).

## Testing

```bash
uv run ruff check
uv run ruff format --check
uv run pytest
```

The tests cover each pipeline stage on small hand-built fixtures, regression tests for earlier bugs (country-to-region lookup, substring keyword matches), the statistics helpers against known values, and end-to-end runs of the pipeline and CLI on synthetic data. CI runs all of this on Python 3.12 and 3.13.

## Limitations

- **No cost data**, so the pipeline cannot estimate CPA, ROAS or ROI. The channel scenario shifts prospect *volume* share, not budget.
- **Attribution is single-touch** (`Prospect Source`) and campaigns were not randomised. Model coefficients are associations, not causal effects.
- **Job categories come from keyword rules** on free-text titles and will misclassify some of them.
- **Synthetic data is illustrative.** Its effect sizes are modest and invented, so results on it say nothing about any real business.
- **The analysis is a snapshot**: there is no time-series or cohort analysis yet.

## Roadmap

- Join spend data to report cost per registration by channel and support budget optimisation under constraints.
- Trend and cohort views using the opt-in timestamps.
- Pydantic or pandera schema contracts for the input file.
- An optional dashboard view (for example Streamlit) built on the same analysis objects.

## Author

**Guilherme Fialho**, Machine Learning Engineer (GenAI/LLMs) and Data Engineer, working with Python, SQL, GCP (BigQuery, Dataflow, Composer/Airflow) and AWS.

- GitHub: [@gcfialho](https://github.com/gcfialho)
- LinkedIn: [guilherme-cagide-fialho](https://www.linkedin.com/in/guilherme-cagide-fialho/)

Licensed under the [MIT License](LICENSE).
