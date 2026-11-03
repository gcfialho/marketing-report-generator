"""The checked-in example report must match what the code produces now."""

import re
from datetime import datetime
from pathlib import Path

from marketing_report.pipeline import PipelineConfig, run

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "synthetic"


def test_synthetic_example_is_up_to_date(tmp_path: Path) -> None:
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


def test_channel_decision_example_builds(tmp_path: Path) -> None:
    import subprocess
    import sys

    script = EXAMPLE.parent / "channel-decision" / "build.py"
    subprocess.run(
        [sys.executable, str(script), "--runs", "2", "--out", str(tmp_path)],
        check=True,
        capture_output=True,
    )
    readme = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert readme.startswith("# Worked example")
    assert "{" not in readme.replace("```", "")  # no unformatted placeholders
    for name in ("estimates_vs_truth.png", "detection_by_sample_size.png", "simulation.csv"):
        assert (tmp_path / name).stat().st_size > 0
