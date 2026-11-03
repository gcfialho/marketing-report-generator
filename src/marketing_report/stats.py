"""Statistical helpers: proportion intervals, independence tests and logistic regression."""

from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass, field
from typing import SupportsFloat

import numpy as np
import pandas as pd
from scipy import stats as sps

logger = logging.getLogger(__name__)


def as_float(value: object) -> float:
    """A numeric table cell as a Python float.

    pandas types single-cell access (``row["rate"]``, ``df.loc[i, col]``) as any possible
    scalar; this narrows it, and fails loudly if the cell is not numeric.
    """
    if not isinstance(value, SupportsFloat):
        raise TypeError(f"Expected a numeric value, got {value!r}")
    return float(value)


def wilson_interval(successes: int, n: int, confidence: float = 0.95) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion.

    Preferred over the normal (Wald) interval because it stays inside [0, 1] and
    behaves sensibly for small samples and rates near 0 or 1 (e.g. 0 of 14).
    """
    if n <= 0:
        return (float("nan"), float("nan"))
    z = sps.norm.ppf(1 - (1 - confidence) / 2)
    p = successes / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    half = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    low = 0.0 if successes == 0 else max(0.0, centre - half)
    high = 1.0 if successes == n else min(1.0, centre + half)
    return (float(low), float(high))


def rate_table(df: pd.DataFrame, by: str, target: str, confidence: float = 0.95) -> pd.DataFrame:
    """Per-segment volume, conversions, rate and Wilson CI (rates as fractions)."""
    grouped = df.groupby(by, dropna=False).agg(
        prospects=(target, "count"), conversions=(target, "sum")
    )
    grouped["conversions"] = grouped["conversions"].astype(int)
    grouped["rate"] = grouped["conversions"] / grouped["prospects"]
    bounds = [
        wilson_interval(int(c), int(n), confidence)
        for c, n in zip(grouped["conversions"], grouped["prospects"], strict=True)
    ]
    grouped["ci_low"] = [lo for lo, _ in bounds]
    grouped["ci_high"] = [hi for _, hi in bounds]
    grouped["volume_share"] = grouped["prospects"] / grouped["prospects"].sum()
    return grouped.sort_values(["rate", "prospects"], ascending=False)


@dataclass(frozen=True)
class IndependenceTest:
    variable: str
    chi2: float
    p_value: float
    dof: int
    cramers_v: float
    min_expected: float
    low_expected_share: float
    fisher_p_value: float | None = None
    monte_carlo_p_value: float | None = None

    @property
    def assumptions_ok(self) -> bool:
        """Cochran's rule: no expected count < 1 and at most 20% of cells below 5."""
        return self.min_expected >= 1 and self.low_expected_share <= 0.2

    @property
    def p_value_used(self) -> float:
        """The p-value to act on: exact (2x2) or Monte Carlo when the chi-square
        approximation is unreliable, otherwise the asymptotic chi-square p-value."""
        if self.assumptions_ok:
            return self.p_value
        if self.fisher_p_value is not None:
            return self.fisher_p_value
        if self.monte_carlo_p_value is not None:
            return self.monte_carlo_p_value
        return self.p_value


def monte_carlo_chi_square_p(table: np.ndarray, n_resamples: int = 9999, seed: int = 0) -> float:
    """Chi-square p-value from tables simulated with the observed margins fixed.

    Tables are drawn with Patefield's algorithm (``scipy.stats.random_table``), which is
    the conditional null distribution used by Fisher's exact test, so the result stays
    valid when expected counts are too small for the asymptotic chi-square distribution.
    The seed makes the p-value reproducible.
    """
    observed = np.asarray(table, dtype=float)
    rows, cols = observed.sum(axis=1), observed.sum(axis=0)
    expected = np.outer(rows, cols) / observed.sum()
    statistic = ((observed - expected) ** 2 / expected).sum()
    sims = sps.random_table(rows.astype(int), cols.astype(int), seed=seed).rvs(size=n_resamples)
    simulated = ((sims - expected) ** 2 / expected).sum(axis=(1, 2))
    # Small tolerance so floating-point noise does not drop ties with the observed table.
    exceed = int((simulated >= statistic - 1e-9 * max(1.0, statistic)).sum())
    return (1 + exceed) / (n_resamples + 1)


def chi_square_independence(df: pd.DataFrame, variable: str, target: str) -> IndependenceTest:
    """Chi-square test of independence between a segment and the binary conversion flag.

    The test is run on the segment x converted (2-column) table, which is what the
    question "do segments convert at different rates?" actually asks.
    """
    table = pd.crosstab(df[variable], df[target])
    if table.shape[0] < 2 or table.shape[1] < 2:
        return IndependenceTest(variable, float("nan"), float("nan"), 0, float("nan"), 0, 1)
    result = sps.chi2_contingency(table, correction=False)
    expected = np.asarray(result.expected_freq)
    n = table.to_numpy().sum()
    k = min(table.shape) - 1
    cramers_v = float(np.sqrt(result.statistic / (n * k))) if k > 0 else float("nan")

    fisher_p = None
    if table.shape == (2, 2):
        fisher_p = float(sps.fisher_exact(table.to_numpy()).pvalue)

    min_expected = float(expected.min())
    low_share = float((expected < 5).mean())
    monte_carlo_p = None
    if fisher_p is None and not (min_expected >= 1 and low_share <= 0.2):
        monte_carlo_p = monte_carlo_chi_square_p(table.to_numpy())

    return IndependenceTest(
        variable=variable,
        chi2=float(result.statistic),
        p_value=float(result.pvalue),
        dof=int(result.dof),
        cramers_v=cramers_v,
        min_expected=min_expected,
        low_expected_share=low_share,
        fisher_p_value=fisher_p,
        monte_carlo_p_value=monte_carlo_p,
    )


@dataclass(frozen=True)
class LogitTerm:
    term: str
    odds_ratio: float
    ci_low: float
    ci_high: float
    p_value: float


@dataclass
class LogitResult:
    formula: str
    n_obs: int
    n_events: int
    reference_levels: dict[str, str]
    terms: list[LogitTerm]
    pseudo_r2: float
    llr_p_value: float
    excluded_levels: dict[str, list[str]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def logistic_regression(
    df: pd.DataFrame,
    target: str,
    categorical: list[str],
    min_level_size: int = 30,
) -> LogitResult | None:
    """Multivariable logistic regression with one-hot (treatment) coding.

    Each categorical predictor uses its most frequent level as the reference, so every
    odds ratio reads as "vs. the largest segment, holding the other variables fixed".
    Levels with fewer than ``min_level_size`` rows or with zero/all conversions cannot
    be estimated by maximum likelihood (quasi-complete separation); their rows are
    excluded from the model and reported in ``excluded_levels``.
    """
    import statsmodels.api as sm
    from statsmodels.tools.sm_exceptions import ConvergenceWarning, PerfectSeparationWarning

    data = df[[target, *categorical]].dropna()
    excluded: dict[str, list[str]] = {}
    for column in categorical:
        stats_by_level = data.groupby(column)[target].agg(["count", "sum"])
        bad = stats_by_level[
            (stats_by_level["count"] < min_level_size)
            | (stats_by_level["sum"] == 0)
            | (stats_by_level["sum"] == stats_by_level["count"])
        ].index.tolist()
        if bad:
            excluded[column] = [str(level) for level in bad]
            data = data[~data[column].isin(bad)]

    usable = [c for c in categorical if data[c].nunique() >= 2]
    if not usable or data[target].nunique() < 2:
        logger.warning("Logistic regression skipped: not enough variation after filtering")
        return None

    # Explicit treatment coding: one indicator per non-reference level.
    references = {c: str(data[c].value_counts().idxmax()) for c in usable}
    design = pd.DataFrame(index=data.index)
    for column in usable:
        for level in sorted(data[column].astype(str).unique()):
            if level != references[column]:
                design[f"{column}: {level}"] = (data[column].astype(str) == level).astype(float)
    design = sm.add_constant(design, has_constant="add")

    # Perfectly collinear predictors (e.g. one segment fully determined by another) make the
    # Hessian singular; whether the fit then crashes depends on the BLAS build. Skip instead.
    if np.linalg.matrix_rank(design.to_numpy()) < design.shape[1]:
        logger.warning("Logistic regression skipped: predictors are perfectly collinear")
        return None

    with warnings.catch_warnings(record=True) as records:
        warnings.simplefilter("always", ConvergenceWarning)
        warnings.simplefilter("always", PerfectSeparationWarning)
        try:
            fit = sm.Logit(data[target].astype(float), design).fit(disp=False, maxiter=200)
        except np.linalg.LinAlgError:
            logger.warning("Logistic regression skipped: singular Hessian")
            return None
    caught = [str(r.message) for r in records]

    conf = fit.conf_int()
    terms = [
        LogitTerm(
            term=name,
            odds_ratio=float(np.exp(fit.params[name])),
            ci_low=float(np.exp(conf.loc[name, 0])),
            ci_high=float(np.exp(conf.loc[name, 1])),
            p_value=float(fit.pvalues[name]),
        )
        for name in fit.params.index
        if name != "const"
    ]
    return LogitResult(
        formula=f"{target} ~ " + " + ".join(usable),
        n_obs=int(fit.nobs),
        n_events=int(data[target].sum()),
        reference_levels=references,
        terms=terms,
        pseudo_r2=float(fit.prsquared),
        llr_p_value=float(fit.llr_pvalue),
        excluded_levels=excluded,
        warnings=caught,
    )


def segment_vs_rest(df: pd.DataFrame, by: str, target: str) -> pd.DataFrame:
    """Fisher's exact test of each segment against all other prospects, Holm-adjusted.

    Exact tests avoid the small-sample problems of chi-square/z-tests for tiny segments,
    and the Holm correction accounts for testing every segment at once.
    """
    rows = []
    total_n = len(df)
    total_conv = int(df[target].sum())
    for level, group in df.groupby(by):
        n = len(group)
        conv = int(group[target].sum())
        rest_n, rest_conv = total_n - n, total_conv - conv
        if rest_n == 0:
            continue
        table = [[conv, n - conv], [rest_conv, rest_n - rest_conv]]
        rows.append(
            {
                by: level,
                "rate": conv / n,
                "rest_rate": rest_conv / rest_n,
                "p_value": float(sps.fisher_exact(table).pvalue),
            }
        )
    result = pd.DataFrame(rows, columns=[by, "rate", "rest_rate", "p_value"])
    result["p_adjusted"] = holm_adjust(result["p_value"].tolist())
    return result.set_index(by)


def holm_adjust(p_values: list[float]) -> list[float]:
    """Holm-Bonferroni adjusted p-values (controls family-wise error rate)."""
    m = len(p_values)
    order = np.argsort(p_values)
    adjusted = np.empty(m)
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, (m - rank) * p_values[idx])
        adjusted[idx] = min(1.0, running)
    return adjusted.tolist()


def detectable_rate_range(
    rest_rate: float,
    n: int,
    n_rest: int,
    alpha: float = 0.05,
    power: float = 0.8,
) -> tuple[float, float]:
    """True rates a segment would need to be told apart from the rest at the given power.

    Returns ``(low, high)``: with ``n`` prospects in the segment and ``n_rest`` in the
    rest (whose rate is ``rest_rate``), a two-sided test at level ``alpha`` detects the
    difference with probability ``power`` only if the segment's true rate is below
    ``low`` or above ``high``. Uses Cohen's h (arcsine-transformed proportions), whose
    variance does not depend on the rate, so it stays usable near 0%. It is a normal
    approximation: Fisher's exact test is slightly more conservative.
    """
    if n <= 0 or n_rest <= 0:
        return (float("nan"), float("nan"))
    z = sps.norm.ppf(1 - alpha / 2) + sps.norm.ppf(power)
    h = z * np.sqrt(1 / n + 1 / n_rest)
    phi = np.arcsin(np.sqrt(rest_rate))
    low = 0.0 if phi - h / 2 <= 0 else float(np.sin(phi - h / 2) ** 2)
    high = 1.0 if phi + h / 2 >= np.pi / 2 else float(np.sin(phi + h / 2) ** 2)
    return (low, high)
