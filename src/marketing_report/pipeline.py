"""End-to-end orchestration: load -> validate -> clean -> transform -> analyse -> report."""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pandas as pd

from marketing_report import synthetic
from marketing_report.analysis import AnalysisResult, analyze
from marketing_report.cleaning import CleaningReport, clean
from marketing_report.report import ReportPaths, write_report
from marketing_report.transform import transform
from marketing_report.validation import ValidationReport, load_data, validate_or_raise

logger = logging.getLogger(__name__)

DEFAULT_COMPANY = "Example Co."
DEFAULT_OBJECTIVE = "Maximise free-trial registrations"


@dataclass(frozen=True)
class PipelineConfig:
    output_dir: Path
    input_path: Path | None = None
    synthetic_rows: int = 1000
    seed: int = 42
    company: str = DEFAULT_COMPANY
    objective: str = DEFAULT_OBJECTIVE
    pdf: bool = False
    alpha: float = 0.05
    export_clean: bool = True
    generated_at: datetime | None = None


@dataclass
class PipelineResult:
    validation: ValidationReport
    cleaning: CleaningReport
    analysis: AnalysisResult
    report: ReportPaths
    clean_csv: Path | None
    timings: dict[str, float] = field(default_factory=dict)


@contextmanager
def _timed(timings: dict[str, float], step: str) -> Iterator[None]:
    start = time.perf_counter()
    logger.info("Step: %s", step)
    yield
    timings[step] = time.perf_counter() - start


def _load(config: PipelineConfig) -> tuple[pd.DataFrame, str]:
    if config.input_path is None:
        logger.info(
            "No input file given: generating %d synthetic rows (seed=%d)",
            config.synthetic_rows,
            config.seed,
        )
        return synthetic.generate(config.synthetic_rows, seed=config.seed), (
            f"synthetic (rows={config.synthetic_rows}, seed={config.seed})"
        )
    return load_data(config.input_path), config.input_path.name


def run(config: PipelineConfig) -> PipelineResult:
    timings: dict[str, float] = {}
    output_dir = config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    with _timed(timings, "load"):
        raw, source_name = _load(config)
    with _timed(timings, "validate"):
        validation = validate_or_raise(raw)
    with _timed(timings, "clean"):
        cleaned, cleaning = clean(raw)
    with _timed(timings, "transform"):
        features = transform(cleaned)
    with _timed(timings, "analyze"):
        analysis = analyze(features, alpha=config.alpha)
    with _timed(timings, "report"):
        report = write_report(
            analysis,
            validation,
            cleaning,
            output_dir,
            company=config.company,
            objective=config.objective,
            source_name=source_name,
            pdf=config.pdf,
            generated_at=config.generated_at,
        )

    clean_csv = None
    if config.export_clean:
        clean_csv = output_dir / "prospects_clean.csv"
        features.to_csv(clean_csv, index=False)
        logger.info("Wrote %s", clean_csv)

    logger.info(
        "Done in %.2fs (%s)",
        sum(timings.values()),
        ", ".join(f"{k} {v:.2f}s" for k, v in timings.items()),
    )
    return PipelineResult(validation, cleaning, analysis, report, clean_csv, timings)
