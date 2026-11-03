import math

import numpy as np
import pandas as pd
import pytest

from marketing_report.stats import (
    chi_square_independence,
    holm_adjust,
    logistic_regression,
    rate_table,
    segment_vs_rest,
    wilson_interval,
)


def test_wilson_interval_known_values():
    # Reference values from the closed-form Wilson score interval (z = 1.959964).
    low, high = wilson_interval(10, 40)
    assert low == pytest.approx(0.1419, abs=1e-4)
    assert high == pytest.approx(0.4019, abs=1e-4)


def test_wilson_interval_zero_successes_has_positive_upper_bound():
    # 0 of 14 is not evidence of a 0% rate: the upper bound is about 21.5%.
    low, high = wilson_interval(0, 14)
    assert low == 0.0
    assert high == pytest.approx(0.2153, abs=1e-4)


def test_wilson_interval_empty_sample_is_nan():
    assert all(math.isnan(x) for x in wilson_interval(0, 0))


def test_rate_table_columns_and_order():
    df = pd.DataFrame({"seg": ["a"] * 10 + ["b"] * 10, "y": [1] * 5 + [0] * 5 + [1] * 1 + [0] * 9})
    table = rate_table(df, "seg", "y")
    assert table.index.tolist() == ["a", "b"]
    assert table.loc["a", "rate"] == 0.5
    assert table["volume_share"].sum() == pytest.approx(1.0)
    assert (table["ci_low"] <= table["rate"]).all()
    assert (table["rate"] <= table["ci_high"]).all()


def test_chi_square_uses_binary_outcome_and_flags_small_counts():
    df = pd.DataFrame({"seg": ["a"] * 6 + ["b"] * 6, "y": [1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 1]})
    test = chi_square_independence(df, "seg", "y")
    assert test.dof == 1  # 2 segments x 2 outcomes
    assert not test.assumptions_ok  # expected counts of 3 < 5
    assert test.fisher_p_value is not None
    assert 0 <= test.cramers_v <= 1


def test_holm_adjust_matches_manual_computation():
    adjusted = holm_adjust([0.01, 0.04, 0.03])
    # sorted: 0.01*3=0.03, 0.03*2=0.06, 0.04*1=0.04 -> monotone max -> 0.06
    assert adjusted == pytest.approx([0.03, 0.06, 0.06])


def test_segment_vs_rest_detects_clear_difference():
    df = pd.DataFrame(
        {"seg": ["hi"] * 100 + ["lo"] * 100, "y": [1] * 60 + [0] * 40 + [1] * 10 + [0] * 90}
    )
    result = segment_vs_rest(df, "seg", "y")
    assert result.loc["hi", "p_adjusted"] < 0.001
    assert result.loc["hi", "rate"] > result.loc["hi", "rest_rate"]


def test_logistic_regression_recovers_direction_and_excludes_sparse_levels():
    rng = np.random.default_rng(0)
    n = 2000
    channel = rng.choice(["Ads", "Referral"], size=n, p=[0.8, 0.2])
    p = np.where(channel == "Referral", 0.35, 0.12)
    y = (rng.random(n) < p).astype(int)
    df = pd.DataFrame({"channel": channel, "region": rng.choice(["N", "S"], size=n), "y": y})
    # A tiny level with zero conversions would cause quasi-complete separation.
    sparse = pd.DataFrame({"channel": ["Social"] * 10, "region": ["N"] * 10, "y": [0] * 10})
    df = pd.concat([df, sparse], ignore_index=True)

    result = logistic_regression(df, "y", ["channel", "region"])
    assert result is not None
    assert result.reference_levels["channel"] == "Ads"
    assert result.excluded_levels == {"channel": ["Social"]}
    referral = next(t for t in result.terms if t.term == "channel: Referral")
    assert referral.odds_ratio > 2
    assert referral.ci_low > 1
    assert referral.p_value < 0.001
    assert result.n_obs == n


def test_monte_carlo_p_matches_asymptotic_p_on_large_table():
    from scipy import stats as sps

    from marketing_report.stats import monte_carlo_chi_square_p

    table = np.array([[120, 880], [150, 850], [95, 905]])
    asymptotic = sps.chi2_contingency(table, correction=False).pvalue
    assert monte_carlo_chi_square_p(table) == pytest.approx(asymptotic, abs=0.01)
    # Seeded, so the report is reproducible.
    assert monte_carlo_chi_square_p(table) == monte_carlo_chi_square_p(table)


def test_small_expected_counts_switch_to_monte_carlo_p():
    # 4 x 2 table with a tiny zero-conversion segment: chi-square approximation fails.
    df = pd.DataFrame(
        {
            "seg": ["a"] * 120 + ["b"] * 30 + ["c"] * 800 + ["d"] * 20,
            "y": [1] * 20 + [0] * 100 + [1] * 5 + [0] * 25 + [1] * 80 + [0] * 720 + [0] * 20,
        }
    )
    test = chi_square_independence(df, "seg", "y")
    assert not test.assumptions_ok
    assert test.monte_carlo_p_value is not None
    assert test.p_value_used == test.monte_carlo_p_value
    assert 0 < test.monte_carlo_p_value <= 1


def test_two_by_two_with_small_counts_uses_fisher():
    df = pd.DataFrame({"seg": ["a"] * 6 + ["b"] * 6, "y": [1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 1]})
    test = chi_square_independence(df, "seg", "y")
    assert test.monte_carlo_p_value is None
    assert test.p_value_used == test.fisher_p_value


def test_detectable_rate_range_matches_textbook_sample_size():
    from marketing_report.stats import detectable_rate_range

    # Cohen's h for 10% vs 15% is 0.1519; at alpha = 0.05 and 80% power the classic
    # equal-groups sample size is (2.8016 / 0.1519)^2 * 2 = 680 per group.
    low, high = detectable_rate_range(0.10, 680, 680)
    assert high == pytest.approx(0.15, abs=0.001)
    assert low < 0.10 < high


def test_detectable_rate_range_shrinks_with_sample_size():
    from marketing_report.stats import detectable_rate_range

    small = detectable_rate_range(0.12, 33, 967)
    large = detectable_rate_range(0.12, 400, 9600)
    assert small[1] - small[0] > large[1] - large[0]
    # With 10 prospects not even a true rate of 0% would be detectably below 12%.
    assert detectable_rate_range(0.12, 10, 990)[0] == 0.0
    assert math.isnan(detectable_rate_range(0.12, 0, 100)[0])


def test_logistic_regression_skips_collinear_predictors():
    # "segment" is fully determined by "group", so the design matrix is rank deficient.
    n = 200
    df = pd.DataFrame(
        {
            "y": [i % 3 == 0 for i in range(n)],
            "group": [("a", "b", "c", "d")[i % 4] for i in range(n)],
            "segment": [("x", "y")[i % 2] for i in range(n)],
        }
    )
    assert logistic_regression(df, "y", ["group", "segment"]) is None
