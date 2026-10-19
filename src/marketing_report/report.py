"""Render the analysis into Markdown (Jinja2) and optionally PDF."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, PackageLoader, StrictUndefined

from marketing_report import charts
from marketing_report.analysis import SCENARIO_MULTIPLIERS, AnalysisResult, SegmentAnalysis
from marketing_report.cleaning import CleaningReport
from marketing_report.stats import IndependenceTest
from marketing_report.validation import ValidationReport

logger = logging.getLogger(__name__)

PDF_CSS = """
body { font-family: Helvetica, Arial, sans-serif; font-size: 10pt; color: #0b0b0b; }
h1 { font-size: 18pt; border-bottom: 2px solid #2a78d6; padding-bottom: 4px; }
h2 { font-size: 13pt; margin-top: 14px; }
h3 { font-size: 11pt; }
table { border-collapse: collapse; width: 100%; }
th, td { border: 1px solid #d4d3cf; padding: 3px 5px; font-size: 8.5pt; }
th { background-color: #f1f0ec; }
code { font-family: Courier, monospace; font-size: 9pt; }
blockquote { color: #52514e; }
"""


@dataclass(frozen=True)
class ReportPaths:
    markdown: Path
    pdf: Path | None
    charts: dict[str, Path]


def _pct(value: float) -> str:
    return "n/a" if value != value else f"{value:.1%}"


def _pvalue(value: float) -> str:
    if value != value:
        return "n/a"
    return "< 0.001" if value < 0.001 else f"{value:.3f}"


def segment_table(segment: SegmentAnalysis) -> str:
    header = (
        f"| {segment.column} | Prospects | Registered | Rate | 95% CI | Volume share | "
        "Adj. p vs rest |\n|---|---:|---:|---:|---:|---:|---:|"
    )
    rows = []
    for level, row in segment.table.iterrows():
        p_adj = segment.vs_rest["p_adjusted"].get(level, float("nan"))
        rows.append(
            f"| {level} | {int(row['prospects']):,} | {int(row['conversions']):,} | "
            f"{_pct(row['rate'])} | {_pct(row['ci_low'])} to {_pct(row['ci_high'])} | "
            f"{_pct(row['volume_share'])} | {_pvalue(p_adj)} |"
        )
    return "\n".join([header, *rows])


def test_line(test: IndependenceTest) -> str:
    if test.p_value != test.p_value:
        return "*Chi-square test not applicable (fewer than two levels).*"
    line = (
        f"Chi-square test of independence: χ² = {test.chi2:.2f}, df = {test.dof}, "
        f"p = {_pvalue(test.p_value)}, Cramér's V = {test.cramers_v:.2f}."
    )
    if test.fisher_p_value is not None:
        line += f" Fisher's exact test: p = {_pvalue(test.fisher_p_value)}."
    if not test.assumptions_ok:
        line += (
            f" Caution: smallest expected count is {test.min_expected:.1f} and "
            f"{test.low_expected_share:.0%} of cells are below 5, so the chi-square "
            "approximation is unreliable; rely on the exact per-segment tests."
        )
    return f"*{line}*"


def _environment() -> Environment:
    env = Environment(
        loader=PackageLoader("marketing_report", "templates"),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
        autoescape=False,  # Markdown output, not HTML
    )
    env.filters["pct"] = _pct
    env.filters["pvalue"] = _pvalue
    env.globals.update(segment_table=segment_table, test_line=test_line)
    return env


def render_markdown(
    analysis: AnalysisResult,
    validation: ValidationReport,
    cleaning: CleaningReport,
    *,
    company: str,
    objective: str,
    source_name: str,
    chart_paths: dict[str, str],
    generated_at: datetime | None = None,
) -> str:
    template = _environment().get_template("report.md.j2")
    return template.render(
        a=analysis,
        v=validation,
        c=cleaning,
        company=company,
        objective=objective,
        source_name=source_name,
        charts=chart_paths,
        multipliers=SCENARIO_MULTIPLIERS,
        generated_at=(generated_at or datetime.now()).strftime("%Y-%m-%d %H:%M"),
    )


def build_charts(analysis: AnalysisResult, chart_dir: Path) -> dict[str, Path]:
    chart_dir.mkdir(parents=True, exist_ok=True)
    overall = analysis.funnel.overall_rate
    return {
        "funnel": charts.funnel_chart(analysis.funnel, chart_dir / "funnel.png"),
        "channel": charts.rate_chart(
            analysis.segments["channel"].table,
            "Registration rate by prospect source",
            overall,
            chart_dir / "channel_rates.png",
        ),
        "job_category": charts.rate_chart(
            analysis.segments["job_category"].table,
            "Registration rate by job category",
            overall,
            chart_dir / "job_category_rates.png",
        ),
    }


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "report"


class PdfUnavailableError(RuntimeError):
    """Raised when PDF output is requested but the optional ``pdf`` extra is not installed."""


def write_pdf(markdown_text: str, pdf_path: Path, *, root: Path, title: str) -> Path:
    """Convert Markdown to PDF with markdown-pdf (PyMuPDF). Images resolve relative to ``root``."""
    try:
        from markdown_pdf import MarkdownPdf, Section
    except ImportError as exc:
        raise PdfUnavailableError(
            "PDF output needs the optional 'pdf' extra: uv sync --extra pdf"
        ) from exc

    pdf = MarkdownPdf(toc_level=2, optimize=True)
    pdf.meta["title"] = title
    pdf.meta["creator"] = "marketing-report"
    pdf.add_section(Section(markdown_text, root=str(root)), user_css=PDF_CSS)
    pdf.save(str(pdf_path))
    return pdf_path


def write_report(
    analysis: AnalysisResult,
    validation: ValidationReport,
    cleaning: CleaningReport,
    output_dir: Path,
    *,
    company: str,
    objective: str,
    source_name: str,
    pdf: bool = False,
    generated_at: datetime | None = None,
) -> ReportPaths:
    output_dir.mkdir(parents=True, exist_ok=True)
    chart_files = build_charts(analysis, output_dir / "charts")
    relative = {k: p.relative_to(output_dir).as_posix() for k, p in chart_files.items()}

    markdown_text = render_markdown(
        analysis,
        validation,
        cleaning,
        company=company,
        objective=objective,
        source_name=source_name,
        chart_paths=relative,
        generated_at=generated_at,
    )
    stem = f"{slugify(company)}-marketing-report"
    md_path = output_dir / f"{stem}.md"
    md_path.write_text(markdown_text, encoding="utf-8")
    logger.info("Wrote %s", md_path)

    pdf_path = None
    if pdf:
        pdf_path = write_pdf(
            markdown_text,
            output_dir / f"{stem}.pdf",
            root=output_dir,
            title=f"{company} marketing funnel report",
        )
        logger.info("Wrote %s", pdf_path)
    return ReportPaths(markdown=md_path, pdf=pdf_path, charts=chart_files)
