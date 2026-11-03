"""The checked-in example report must match what the code produces now."""

import re
from datetime import datetime
from pathlib import Path

from marketing_report.pipeline import PipelineConfig, run

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "synthetic"


def test_synthetic_example_is_up_to_date(tmp_path):
    checked_in = (EXAMPLE / "example-co-marketing-report.md").read_text(encoding="utf-8")
    stamp = re.search(r"\*\*Generated:\*\* (.+)", checked_in)
    assert stamp, "example report has no Generated line"
    generated_at = datetime.strptime(stamp.group(1).strip(), "%Y-%m-%d %H:%M")

    result = run(PipelineConfig(output_dir=tmp_path, generated_at=generated_at, export_clean=False))
    regenerated = result.report.markdown.read_text(encoding="utf-8")
    assert regenerated == checked_in, (
        "examples/synthetic is stale. Regenerate it with:\n"
        "SOURCE_DATE_EPOCH=$(date +%s) uv run marketing-report run "
        "--output-dir examples/synthetic --no-clean-export"
    )
