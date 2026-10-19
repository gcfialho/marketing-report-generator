"""End-to-end runs of the pipeline and CLI on synthetic data."""

from datetime import datetime

import pandas as pd

from marketing_report import schema, synthetic
from marketing_report.cli import main
from marketing_report.pipeline import PipelineConfig, run


def test_pipeline_on_generated_data(tmp_path):
    config = PipelineConfig(
        output_dir=tmp_path, synthetic_rows=1000, seed=42, generated_at=datetime(2026, 1, 1)
    )
    result = run(config)

    report = result.report.markdown.read_text(encoding="utf-8")
    assert report.startswith("# Marketing Funnel Report: Example Co.")
    assert "{{" not in report and "}}" not in report
    for section in ("## 1. Funnel", "## 2. Channel performance", "## 4. Multivariable",
                    "## 5. Channel actions", "## 6. Data quality"):  # fmt: skip
        assert section in report
    for chart in result.report.charts.values():
        assert chart.exists() and chart.stat().st_size > 0

    clean = pd.read_csv(result.clean_csv)
    assert clean[schema.PROSPECT_ID].is_unique
    assert len(clean) == result.cleaning.rows_out
    assert set(result.timings) == {"load", "validate", "clean", "transform", "analyze", "report"}


def test_pipeline_is_reproducible(tmp_path):
    fixed = datetime(2026, 1, 1)
    first = run(PipelineConfig(output_dir=tmp_path / "a", generated_at=fixed, export_clean=False))
    second = run(PipelineConfig(output_dir=tmp_path / "b", generated_at=fixed, export_clean=False))
    assert first.report.markdown.read_text() == second.report.markdown.read_text()


def test_cli_run_with_csv_input(tmp_path, capsys):
    data = synthetic.write(synthetic.generate(600, seed=5), tmp_path / "prospects.csv")
    out_dir = tmp_path / "out"

    code = main(["run", "--input", str(data), "--output-dir", str(out_dir), "--company", "Acme"])

    assert code == 0
    assert (out_dir / "acme-marketing-report.md").exists()
    assert "Markdown report:" in capsys.readouterr().out


def test_cli_synth_writes_excel(tmp_path):
    path = tmp_path / "synthetic.xlsx"
    assert main(["synth", "--output", str(path), "--rows", "100", "--seed", "1"]) == 0
    assert len(pd.read_excel(path)) >= 100


def test_cli_reports_missing_columns(tmp_path):
    bad = tmp_path / "bad.csv"
    pd.DataFrame({"foo": [1]}).to_csv(bad, index=False)
    assert main(["run", "--input", str(bad), "--output-dir", str(tmp_path / "o")]) == 1
