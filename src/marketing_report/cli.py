"""Command-line interface: ``marketing-report run`` and ``marketing-report synth``."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from marketing_report import __version__, synthetic
from marketing_report.pipeline import DEFAULT_COMPANY, DEFAULT_OBJECTIVE, PipelineConfig, run
from marketing_report.report import PdfUnavailableError
from marketing_report.validation import SchemaError

logger = logging.getLogger("marketing_report")


def _env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(f"MARKETING_REPORT_{name}", default)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="marketing-report",
        description="Validate, clean and analyse prospect-level funnel data and write a report.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser(
        "run",
        help="run the full pipeline",
        description=(
            "Run the pipeline on a CSV/Excel export, or on generated synthetic data when no "
            "input is given. Defaults can be set with MARKETING_REPORT_INPUT, "
            "MARKETING_REPORT_OUTPUT_DIR, MARKETING_REPORT_COMPANY and MARKETING_REPORT_OBJECTIVE."
        ),
    )
    source = run_p.add_mutually_exclusive_group()
    source.add_argument("-i", "--input", type=Path, default=_env("INPUT"), help="CSV or Excel file")
    source.add_argument(
        "--synthetic", action="store_true", help="use generated data (default when no input)"
    )
    run_p.add_argument("--rows", type=int, default=1000, help="synthetic rows (default: 1000)")
    run_p.add_argument("--seed", type=int, default=42, help="synthetic seed (default: 42)")
    run_p.add_argument(
        "-o", "--output-dir", type=Path, default=Path(_env("OUTPUT_DIR", "output")),
        help="output directory (default: ./output)",
    )  # fmt: skip
    run_p.add_argument(
        "--company", default=_env("COMPANY", DEFAULT_COMPANY), help="name shown in the report"
    )
    run_p.add_argument(
        "--objective", default=_env("OBJECTIVE", DEFAULT_OBJECTIVE), help="objective line"
    )
    run_p.add_argument("--alpha", type=float, default=0.05, help="significance level")
    run_p.add_argument(
        "--pdf", action="store_true", help="also write a PDF (needs the 'pdf' extra)"
    )
    run_p.add_argument(
        "--no-clean-export", dest="export_clean", action="store_false",
        help="do not write the cleaned CSV",
    )  # fmt: skip

    synth_p = sub.add_parser("synth", help="write a synthetic dataset to CSV or Excel")
    synth_p.add_argument("-o", "--output", type=Path, required=True, help=".csv or .xlsx path")
    synth_p.add_argument("--rows", type=int, default=1000)
    synth_p.add_argument("--seed", type=int, default=42)
    synth_p.add_argument("--tidy", action="store_true", help="do not inject data-quality issues")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.command == "synth":
        df = synthetic.generate(args.rows, seed=args.seed, messy=not args.tidy)
        path = synthetic.write(df, args.output)
        logger.info("Wrote %d synthetic rows to %s", len(df), path)
        return 0

    config = PipelineConfig(
        output_dir=args.output_dir,
        input_path=None if args.synthetic else args.input,
        synthetic_rows=args.rows,
        seed=args.seed,
        company=args.company,
        objective=args.objective,
        pdf=args.pdf,
        alpha=args.alpha,
        export_clean=args.export_clean,
    )
    try:
        result = run(config)
    except (FileNotFoundError, SchemaError, PdfUnavailableError, ValueError) as exc:
        logger.error("%s", exc)
        return 1

    print(f"Markdown report: {result.report.markdown}")
    if result.report.pdf:
        print(f"PDF report:      {result.report.pdf}")
    if result.clean_csv:
        print(f"Cleaned data:    {result.clean_csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
