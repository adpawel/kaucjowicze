"""Figures and summary tables of comparisons P1 to P9, made from experiment CSVs.

P3 compares the trail signals of ACO N1 (`--trails` in `kaucjowicze.experiments`) and the
success measure J for several weights; it comes next to P1 and P2, whose runs are the same.

P4 compares how fast the variants take up the cans of parties in the dynamic scenario. P5 and
P7 to P9 are sweeps: the variants run with several values of one parameter (number of agents,
bag capacity, vision radius, trail parameters), and their report replaces the other comparisons,
which would otherwise mix runs of different settings. P6 does the same for the can layouts, whose
runs lie in one directory per layout and are read together (several `--input` directories).

`python -m kaucjowicze.plots` needs the optional `analysis` dependencies.
"""

import argparse
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from scipy import stats

from kaucjowicze.config import LAYOUTS, SimulationConfig
from kaucjowicze.experiments import SWEEPS
from kaucjowicze.metrics import J_WEIGHT, objective_j

CONFIDENCE = 0.95

RANDOM = "random"
ACO_SHARED = "aco/shared"
ACO_INDIVIDUAL = "aco/individual"
# ACO N1 with another trail signal than `source` (comparison P3)
ACO_SPEED = "aco/shared/speed"
ACO_EQUAL_PLUS = "aco/shared/equal+"
ACO_EQUAL_MINUS = "aco/shared/equal-"
VARIANT_ORDER = (RANDOM, ACO_SHARED, ACO_INDIVIDUAL, ACO_SPEED, ACO_EQUAL_PLUS, ACO_EQUAL_MINUS)
LABELS = {
    RANDOM: "Random walk",
    ACO_SHARED: "ACO, shared reward (N1)",
    ACO_INDIVIDUAL: "Individual reward (N2)",
    ACO_SPEED: "N1, trail for pace (speed)",
    ACO_EQUAL_PLUS: "N1, trail for equality, gamma +1",
    ACO_EQUAL_MINUS: "N1, trail for equality, gamma -1",
}
# A variant keeps its color in every figure: the categorical slots in their fixed order
COLORS = {
    RANDOM: "#2a78d6",
    ACO_SHARED: "#eb6834",
    ACO_INDIVIDUAL: "#1baf7a",
    ACO_SPEED: "#eda100",
    ACO_EQUAL_PLUS: "#e87ba4",
    ACO_EQUAL_MINUS: "#008300",
}
# The trail signals are also dashed, so they never differ by color alone
LINE_STYLES = {ACO_SPEED: "--", ACO_EQUAL_PLUS: "--", ACO_EQUAL_MINUS: "--"}
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3df"

P1_VARIANTS = (RANDOM, ACO_SHARED)
P3_VARIANTS = (ACO_SHARED, ACO_SPEED, ACO_EQUAL_PLUS, ACO_EQUAL_MINUS)
# P3 tests each signal against `source` on its own success measure (decided before it ran)
P3_TESTS = ((ACO_SPEED, "t_90"), (ACO_EQUAL_PLUS, "gini"), (ACO_EQUAL_MINUS, "gini"))
J_WEIGHTS = (0.0, 0.25, 0.5, 0.75, 1.0)
P2_VARIANTS = (RANDOM, ACO_SHARED, ACO_INDIVIDUAL)
TESTED_PAIRS = (
    (ACO_SHARED, RANDOM),
    (ACO_SHARED, ACO_INDIVIDUAL),
    (ACO_INDIVIDUAL, RANDOM),
)
# P5 tests only this pair, once per number of agents, as decided before the measurement;
# the other sweeps (P7 to P9) test the same pair once per value
P5_PAIR = (ACO_SHARED, RANDOM)
SWEEP_TITLES = {
    "n_agents": ("P5", "Number of agents"),
    "bag_capacity": ("P7", "Bag capacity"),
    "vision_radius": ("P8", "Vision radius"),
    "evaporation_rate": ("P9", "Evaporation rate"),
    "pheromone_alpha": ("P9", "Trail weight exponent"),
    "exploration_rate": ("P9", "Exploration rate"),
}
# P5 was planned with the unpaired test of P1 and P2; the later sweeps, like P6, pair by seed
UNPAIRED_SWEEPS = ("n_agents",)
# Trail parameters change only ACO N1, so P9 tests N1 against itself at the default value
TRAIL_SWEEPS = ("evaporation_rate", "pheromone_alpha", "exploration_rate")
# P6 tests the same pair, t_90 and Gini once per layout, paired by seed (decided before it ran)
P6_METRICS = ("t_90", "gini")
# Runs written without `--layout` have the counts of their map and scenario
DEFAULT_LAYOUT = "map default"
SIGNIFICANCE_LEVEL = 0.05


@dataclass(frozen=True)
class Results:
    runs: pd.DataFrame
    timeline: pd.DataFrame
    agents: pd.DataFrame
    events: pd.DataFrame | None = None  # `None`: files written before parties existed


def load_results(input_dir: str | Path) -> Results:
    """Read the CSV files written by `kaucjowicze.experiments`."""
    directory = Path(input_dir)
    runs = pd.read_csv(directory / "runs.csv")
    timeline = pd.read_csv(directory / "timeline.csv")
    agents = pd.read_csv(directory / "agents.csv")
    events_path = directory / "events.csv"
    events = pd.read_csv(events_path) if events_path.exists() else None
    has_reward = runs["reward"].notna()
    runs["variant"] = runs["algorithm"].where(~has_reward, runs["algorithm"] + "/" + runs["reward"])
    if "trail" in runs:  # `source` is ACO N1 as it always was, so it keeps its name
        other = runs["trail"].notna() & (runs["trail"] != "source")
        runs.loc[other, "variant"] = runs["variant"] + "/" + runs["trail"]
    return Results(runs, timeline, agents, events)


def combine_results(parts: Sequence[Results]) -> Results:
    """Results of several directories as one, with run ids shifted so they do not repeat."""
    runs, timeline, agents, events = [], [], [], []
    next_id = 0
    for part in parts:
        shift = next_id - int(part.runs["run_id"].min())
        for source, target in (
            (part.runs, runs),
            (part.timeline, timeline),
            (part.agents, agents),
            (part.events, events),
        ):
            if source is not None:
                target.append(source.assign(run_id=source["run_id"] + shift))
        next_id = int(part.runs["run_id"].max()) + shift + 1
    return Results(
        pd.concat(runs, ignore_index=True),
        pd.concat(timeline, ignore_index=True),
        pd.concat(agents, ignore_index=True),
        pd.concat(events, ignore_index=True) if events else None,
    )


def mean_ci(values: Iterable[float]) -> tuple[float, float]:
    """Mean and half-width of its 95% Student's t interval, skipping missing values."""
    data = np.asarray(list(values), dtype=float)
    data = data[~np.isnan(data)]
    if data.size == 0:
        return float("nan"), float("nan")
    mean = float(data.mean())
    if data.size == 1:
        return mean, float("nan")
    return mean, float(_t_quantile(data.size) * data.std(ddof=1) / np.sqrt(data.size))


def _t_quantile(n: int) -> float:
    return float(stats.t.ppf((1 + CONFIDENCE) / 2, df=n - 1))


def censored(runs: pd.DataFrame, column: str) -> pd.Series:
    """Times with a threshold not reached by the limit counted as the limit itself."""
    return runs[column].fillna(runs["max_steps"])


def collection_curves(results: Results) -> pd.DataFrame:
    """Delivered cans: one row per step and one column per run, over the longest run.

    A run ends when its last can is delivered. It stays at its final count afterwards, otherwise
    the fastest runs would drop out of the mean and the curve would fall towards its end.
    """
    curves = results.timeline.pivot(index="step", columns="run_id", values="cans_collected")
    return curves.ffill()


def curve_band(curves: pd.DataFrame) -> pd.DataFrame:
    """Mean of the runs at each step with its 95% interval."""
    mean = curves.mean(axis=1)
    half_width = (
        _t_quantile(curves.shape[1]) * curves.std(axis=1, ddof=1) / np.sqrt(curves.shape[1])
    )
    return pd.DataFrame({"mean": mean, "low": mean - half_width, "high": mean + half_width})


def _present(runs: pd.DataFrame, variants: Sequence[str]) -> list[str]:
    available = set(runs["variant"])
    return [variant for variant in variants if variant in available]


def summary_table(runs: pd.DataFrame) -> pd.DataFrame:
    """One row per variant: means with intervals, and how many runs reached each threshold."""
    rows = []
    for variant in _present(runs, VARIANT_ORDER):
        group = runs[runs["variant"] == variant]
        row: dict[str, object] = {"variant": variant, "runs": len(group)}
        for column in ("t_50", "t_90"):
            row[f"{column}_mean"], row[f"{column}_ci"] = mean_ci(censored(group, column))
        for column in ("path_per_can", "trips", "gini"):
            row[f"{column}_mean"], row[f"{column}_ci"] = mean_ci(group[column])
        row["cans_min_mean"] = group["cans_min"].mean()
        row["cans_max_mean"] = group["cans_max"].mean()
        row["t_90_reached"] = int(group["t_90"].notna().sum())
        row["t_100_reached"] = int(group["t_100"].notna().sum())
        rows.append(row)
    return pd.DataFrame(rows)


def _mann_whitney_p(a: pd.Series, b: pd.Series) -> float:
    """Two-sided p-value. With all values equal there is no difference to detect, so it is 1;
    SciPy gives 1 or NaN for that case depending on its version.
    """
    if pd.concat([a, b]).nunique() == 1:
        return 1.0
    return float(stats.mannwhitneyu(a, b, alternative="two-sided").pvalue)


def significance_table(runs: pd.DataFrame) -> pd.DataFrame:
    """Two-sided Mann-Whitney tests between variants for t_90 and Gini, uncorrected."""
    rows = []
    for variant_a, variant_b in TESTED_PAIRS:
        a = runs[runs["variant"] == variant_a]
        b = runs[runs["variant"] == variant_b]
        if a.empty or b.empty:
            continue
        for metric, values_a, values_b in (
            ("t_90", censored(a, "t_90"), censored(b, "t_90")),
            ("gini", a["gini"], b["gini"]),
        ):
            rows.append(
                {
                    "metric": metric,
                    "variant_a": variant_a,
                    "variant_b": variant_b,
                    "p_value": _mann_whitney_p(values_a, values_b),
                }
            )
    return pd.DataFrame(rows, columns=["metric", "variant_a", "variant_b", "p_value"])


def has_trails(results: Results) -> bool:
    """Whether ACO N1 also ran with another trail signal (comparison P3)."""
    return bool(set(results.runs["variant"]) & set(P3_VARIANTS[1:]))


def with_j(runs: pd.DataFrame, w1: float) -> pd.Series:
    """J of each run for the weight `w1` of the pace; t_90 below 90% counts as no pace."""
    return pd.Series(
        [
            objective_j(None if pd.isna(t) else t, limit, gini, w1)
            for t, limit, gini in zip(runs["t_90"], runs["max_steps"], runs["gini"], strict=True)
        ],
        index=runs.index,
    )


def signal_table(runs: pd.DataFrame) -> pd.DataFrame:
    """One row per variant: t_90, Gini and J for every weight in `J_WEIGHTS`, with intervals."""
    rows = []
    for variant in _present(runs, VARIANT_ORDER):
        group = runs[runs["variant"] == variant]
        row: dict[str, object] = {"variant": variant, "runs": len(group)}
        row["t_90_mean"], row["t_90_ci"] = mean_ci(censored(group, "t_90"))
        row["gini_mean"], row["gini_ci"] = mean_ci(group["gini"])
        for w1 in J_WEIGHTS:
            row[f"J_{w1:g}_mean"], row[f"J_{w1:g}_ci"] = mean_ci(with_j(group, w1))
        row["t_90_reached"] = int(group["t_90"].notna().sum())
        rows.append(row)
    return pd.DataFrame(rows)


def signal_significance(runs: pd.DataFrame) -> pd.DataFrame:
    """Two-sided Mann-Whitney test of each trail signal against `source` on its own measure,
    with the Bonferroni threshold over the planned tests.
    """
    reference = runs[runs["variant"] == ACO_SHARED]
    rows = []
    for variant, metric in P3_TESTS:
        group = runs[runs["variant"] == variant]
        if group.empty or reference.empty:
            continue
        if metric == "t_90":
            a, b = censored(group, metric), censored(reference, metric)
        else:
            a, b = group[metric], reference[metric]
        rows.append(
            {
                "variant": variant,
                "metric": metric,
                "mean": float(a.mean()),
                "reference_mean": float(b.mean()),
                "p_value": _mann_whitney_p(a, b),
            }
        )
    table = pd.DataFrame(rows, columns=["variant", "metric", "mean", "reference_mean", "p_value"])
    # The number of tests is fixed by the plan, so a missing signal does not loosen the threshold
    table["threshold"] = SIGNIFICANCE_LEVEL / len(P3_TESTS)
    table["significant"] = table["p_value"] < table["threshold"]
    return table


def best_by_weight(runs: pd.DataFrame) -> pd.DataFrame:
    """For each weight of the pace: the variant with the highest mean J."""
    table = signal_table(runs)
    rows = []
    for w1 in J_WEIGHTS:
        best = table.loc[table[f"J_{w1:g}_mean"].idxmax()]
        rows.append({"w1": w1, "variant": best["variant"], "J": best[f"J_{w1:g}_mean"]})
    return pd.DataFrame(rows)


def has_parties(results: Results) -> bool:
    return results.events is not None and not results.events.empty


def party_latencies(results: Results) -> pd.DataFrame:
    """One row per run: its mean over parties, so each run counts as one observation.

    A party not picked from, or below 50%, by the step limit counts as the steps it had, from
    its start to T, so both latencies are averaged over the same parties.
    """
    events = results.events.merge(results.runs[["run_id", "variant", "max_steps"]], on="run_id")
    events["reached_50"] = events["latency_50"].notna()
    steps_had = events["max_steps"] - events["spawn_step"]
    for column in ("latency_first", "latency_50"):
        events[column] = events[column].fillna(steps_had)
    return events.groupby(["run_id", "variant"], as_index=False).agg(
        latency_first=("latency_first", "mean"),
        latency_50=("latency_50", "mean"),
        agents_visited=("agents_visited", "mean"),
        overlap_share=("overlap_share", "mean"),
        parties=("event_id", "count"),
        reached_50=("reached_50", "sum"),
    )


def party_table(results: Results) -> pd.DataFrame:
    """One row per variant: party latencies and spread over agents, means with intervals."""
    per_run = party_latencies(results)
    rows = []
    for variant in _present(per_run, VARIANT_ORDER):
        group = per_run[per_run["variant"] == variant]
        row: dict[str, object] = {"variant": variant, "runs": len(group)}
        for column in ("latency_first", "latency_50", "agents_visited", "overlap_share"):
            row[f"{column}_mean"], row[f"{column}_ci"] = mean_ci(group[column])
        row["reached_50"] = int(group["reached_50"].sum())
        row["parties"] = int(group["parties"].sum())
        rows.append(row)
    return pd.DataFrame(rows)


def party_significance(results: Results) -> pd.DataFrame:
    """Two-sided Mann-Whitney tests of the per-run mean steps to 50% of a party's cans."""
    per_run = party_latencies(results)
    rows = []
    for variant_a, variant_b in TESTED_PAIRS:
        a = per_run.loc[per_run["variant"] == variant_a, "latency_50"]
        b = per_run.loc[per_run["variant"] == variant_b, "latency_50"]
        if a.empty or b.empty:
            continue
        rows.append(
            {
                "metric": "latency_50",
                "variant_a": variant_a,
                "variant_b": variant_b,
                "p_value": _mann_whitney_p(a, b),
            }
        )
    return pd.DataFrame(rows, columns=["metric", "variant_a", "variant_b", "p_value"])


def sweep_parameter(runs: pd.DataFrame) -> str | None:
    """The parameter the runs sweep, or `None` without a sweep.

    Runs of `run_sweep` name it in `sweep`. Files written before that column existed hold only
    sweeps of the number of agents, recognised by more than one value of it.
    """
    if "sweep" in runs and runs["sweep"].notna().any():
        names = runs["sweep"].dropna().unique()
        if len(names) > 1 or runs["sweep"].isna().any():
            raise ValueError("The runs mix several sweeps, or a sweep with plain runs")
        return str(names[0])
    if runs["n_agents"].nunique() > 1:
        return "n_agents"
    return None


def has_sweep(results: Results) -> bool:
    """Whether the runs vary one parameter over several values (comparisons P5, P7 to P9)."""
    return sweep_parameter(results.runs) is not None


def with_sweep_value(runs: pd.DataFrame) -> pd.DataFrame:
    """Runs with a `value` column: the value of the swept parameter in each run."""
    parameter = sweep_parameter(runs) or "n_agents"  # one value is not a sweep, but has one
    if "sweep_value" in runs and runs["sweep_value"].notna().all():
        value = runs["sweep_value"]
    else:  # a sweep of agents written before `sweep_value` existed
        value = runs[parameter]
    return runs.assign(value=value)


def _plain(value) -> int | float:
    """A whole number as `int`, so tables show 10 rather than 10.0."""
    return int(value) if float(value).is_integer() else float(value)


def sweep_table(runs: pd.DataFrame) -> pd.DataFrame:
    """One row per value of the swept parameter and variant.

    For the number of agents `work` is N · t_90, the agent-steps spent until 90% of the cans are
    delivered: if it grows with N, each extra agent adds less than the ones before. It means
    nothing for the other parameters, so they have no `work` columns.
    """
    parameter = sweep_parameter(runs)
    runs = with_sweep_value(runs)
    rows = []
    for value in _sweep_values(runs, "value"):
        same = runs[runs["value"] == value]
        for variant in _present(same, VARIANT_ORDER):
            group = same[same["variant"] == variant]
            t_90 = censored(group, "t_90")
            row: dict[str, object] = {"value": value, "variant": variant, "runs": len(group)}
            row["t_90_mean"], row["t_90_ci"] = mean_ci(t_90)
            if parameter == "n_agents":
                row["work_mean"], row["work_ci"] = mean_ci(t_90 * value)
            row["gini_mean"], row["gini_ci"] = mean_ci(group["gini"])
            row["t_90_reached"] = int(group["t_90"].notna().sum())
            rows.append(row)
    return pd.DataFrame(rows)


def paired_by_seed(runs: pd.DataFrame, column: str, variants: Sequence[str]) -> pd.DataFrame:
    """One row per seed and one column per variant, only seeds that every variant ran on.

    t_90 below its threshold counts as the step limit, as everywhere else.
    """
    by_seed = {}
    for variant in variants:
        group = runs[runs["variant"] == variant]
        values = censored(group, column) if column.startswith("t_") else group[column]
        by_seed[variant] = values.set_axis(group["seed"])
    return pd.concat(by_seed, axis=1, join="inner")


def aco_advantage(runs: pd.DataFrame, by: str = "value") -> pd.DataFrame:
    """Per value of `by` (of the swept parameter or layout): mean t_90 of the random walk over
    that of ACO N1, and on how many seeds ACO N1 is faster. Both use only the seeds both variants
    ran on.
    """
    if by == "value":
        runs = with_sweep_value(runs)
    faster, slower = P5_PAIR
    rows = []
    for value in _sweep_values(runs, by):
        paired = paired_by_seed(runs[runs[by] == value], "t_90", (slower, faster))
        if paired.empty:
            continue
        rows.append(
            {
                by: value,
                "ratio": paired[slower].mean() / paired[faster].mean(),
                "aco_faster": int((paired[faster] < paired[slower]).sum()),
                "seeds": len(paired),
            }
        )
    return pd.DataFrame(rows, columns=[by, "ratio", "aco_faster", "seeds"])


def _sweep_values(runs: pd.DataFrame, by: str) -> list:
    """Values of `by` in order: layouts from the most clustered, numbers ascending."""
    if by == "layout":
        return layout_order(runs)
    return [_plain(value) for value in sorted(runs[by].unique())]


def sweep_significance(runs: pd.DataFrame) -> pd.DataFrame:
    """Two-sided test of t_90, ACO N1 vs random walk, for each value of the swept parameter,
    with the Bonferroni threshold over those tests.

    The number of agents (P5) keeps the Mann-Whitney test it was planned with; the other sweeps
    use the Wilcoxon signed-rank test paired by seed, as P6. `pairs` is `None` for Mann-Whitney.
    """
    parameter = sweep_parameter(runs)
    runs = with_sweep_value(runs)
    variant_a, variant_b = P5_PAIR
    rows = []
    for value in _sweep_values(runs, "value"):
        same = runs[runs["value"] == value]
        a = same[same["variant"] == variant_a]
        b = same[same["variant"] == variant_b]
        if a.empty or b.empty:
            continue
        if parameter in UNPAIRED_SWEEPS:
            p_value = _mann_whitney_p(censored(a, "t_90"), censored(b, "t_90"))
            pairs = None
        else:
            paired = paired_by_seed(same, "t_90", P5_PAIR)
            p_value = _wilcoxon_p(paired[variant_a], paired[variant_b])
            pairs = len(paired)
        rows.append({"value": value, "pairs": pairs, "p_value": p_value})
    table = pd.DataFrame(rows, columns=["value", "pairs", "p_value"])
    table["threshold"] = SIGNIFICANCE_LEVEL / max(len(table), 1)
    table["significant"] = table["p_value"] < table["threshold"]
    return table


def default_value(parameter: str) -> int | float:
    return _plain(getattr(SimulationConfig(), parameter))


def trail_sweep_significance(runs: pd.DataFrame) -> pd.DataFrame:
    """Two-sided Wilcoxon signed-rank tests of t_90, ACO N1 at each other value of a trail
    parameter vs ACO N1 at its default, paired by seed, with the Bonferroni threshold over them.
    """
    parameter = sweep_parameter(runs)
    runs = with_sweep_value(runs)
    aco = runs[runs["variant"] == ACO_SHARED]
    default = default_value(parameter)
    at_default = censored(aco[aco["value"] == default], "t_90").set_axis(
        aco.loc[aco["value"] == default, "seed"]
    )
    rows = []
    if not at_default.empty:
        for value in _sweep_values(aco, "value"):
            if value == default:
                continue
            same = aco[aco["value"] == value]
            values = censored(same, "t_90").set_axis(same["seed"])
            paired = pd.concat({"value": values, "default": at_default}, axis=1, join="inner")
            p_value = _wilcoxon_p(paired["value"], paired["default"])
            rows.append(
                {
                    "value": value,
                    "pairs": len(paired),
                    "t_90_ratio": paired["value"].mean() / paired["default"].mean(),
                    "p_value": p_value,
                }
            )
    table = pd.DataFrame(rows, columns=["value", "pairs", "t_90_ratio", "p_value"])
    table["threshold"] = SIGNIFICANCE_LEVEL / max(len(table), 1)
    table["significant"] = table["p_value"] < table["threshold"]
    return table


def with_layout(runs: pd.DataFrame) -> pd.DataFrame:
    """Runs with a `layout` column; one written without a layout gets `DEFAULT_LAYOUT`."""
    layout = runs["layout"] if "layout" in runs else pd.Series(np.nan, index=runs.index)
    return runs.assign(layout=layout.astype(object).fillna(DEFAULT_LAYOUT))  # all empty: floats


def has_layout_sweep(results: Results) -> bool:
    """Whether the runs come with more than one can layout (comparison P6)."""
    return with_layout(results.runs)["layout"].nunique() > 1


def layout_order(runs: pd.DataFrame) -> list[str]:
    """Layouts of the runs in the order of `LAYOUTS`, from the most clustered; others last."""
    present = set(runs["layout"])
    known = [name for name in LAYOUTS if name in present]
    return known + sorted(present - set(known))


def layout_table(runs: pd.DataFrame) -> pd.DataFrame:
    """One row per layout and variant: t_90 and Gini with intervals, runs reaching 90%."""
    rows = []
    for layout in layout_order(runs):
        same = runs[runs["layout"] == layout]
        for variant in _present(same, VARIANT_ORDER):
            group = same[same["variant"] == variant]
            row: dict[str, object] = {"layout": layout, "variant": variant, "runs": len(group)}
            row["t_90_mean"], row["t_90_ci"] = mean_ci(censored(group, "t_90"))
            row["gini_mean"], row["gini_ci"] = mean_ci(group["gini"])
            row["t_90_reached"] = int(group["t_90"].notna().sum())
            rows.append(row)
    return pd.DataFrame(rows)


def _wilcoxon_p(a: pd.Series, b: pd.Series) -> float:
    """Two-sided Wilcoxon signed-rank p-value of paired values. Pairs with no difference drop
    out; with no pair left there is no difference to detect, so it is 1.
    """
    if (a.to_numpy() == b.to_numpy()).all():
        return 1.0
    return float(stats.wilcoxon(a, b, zero_method="wilcox", alternative="two-sided").pvalue)


def layout_significance(runs: pd.DataFrame) -> pd.DataFrame:
    """Wilcoxon signed-rank tests, ACO N1 vs random walk paired by seed, of t_90 and Gini for
    each layout, with the Bonferroni threshold over all of them.
    """
    variant_a, variant_b = P5_PAIR
    rows = []
    for layout in layout_order(runs):
        same = runs[runs["layout"] == layout]
        for metric in P6_METRICS:
            paired = paired_by_seed(same, metric, P5_PAIR)
            if paired.empty:
                continue
            p_value = _wilcoxon_p(paired[variant_a], paired[variant_b])
            rows.append(
                {"layout": layout, "metric": metric, "pairs": len(paired), "p_value": p_value}
            )
    table = pd.DataFrame(rows, columns=["layout", "metric", "pairs", "p_value"])
    # The number of tests is fixed by the plan, so a missing layout does not loosen the threshold
    table["threshold"] = SIGNIFICANCE_LEVEL / (len(LAYOUTS) * len(P6_METRICS))
    table["significant"] = table["p_value"] < table["threshold"]
    return table


def check_layout_inputs(parts: Sequence[Results]) -> str | None:
    """Why the directories cannot form comparison P6, or `None` when they can.

    Each must hold one named layout, a different one, and all must share the map, scenario,
    number of agents and step limit, so that only the layout differs.
    """
    layouts = []
    for part in parts:
        found = set(part.runs["layout"].dropna()) if "layout" in part.runs else set()
        if len(found) != 1 or part.runs["layout"].isna().any():
            return "each --input directory must hold the runs of one --layout"
        layouts += found
    if len(set(layouts)) != len(layouts):
        return "each --input directory must hold a different layout"
    for column in ("map", "scenario", "n_agents", "max_steps"):
        values = pd.concat([part.runs[column] for part in parts if column in part.runs])
        if values.nunique(dropna=False) > 1:
            return f"the --input directories differ in {column}, not only in the layout"
    return None


def _style_axes(figure: Figure, title: str, xlabel: str, ylabel: str):
    axes = figure.add_subplot()
    axes.set_title(title, color=TEXT_PRIMARY, loc="left", fontsize=12)
    axes.set_xlabel(xlabel, color=TEXT_SECONDARY)
    axes.set_ylabel(ylabel, color=TEXT_SECONDARY)
    axes.tick_params(colors=TEXT_SECONDARY, length=0)
    axes.grid(color=GRID, linewidth=0.8)
    axes.set_axisbelow(True)
    for side in ("top", "right", "left"):
        axes.spines[side].set_visible(False)
    axes.spines["bottom"].set_color(GRID)
    return axes


def plot_collection_curves(
    results: Results, variants: Sequence[str], title: str, path: Path
) -> None:
    """Mean curve with its 95% band for each variant."""
    figure = Figure(figsize=(8, 4.5), layout="constrained")
    axes = _style_axes(figure, title, "Step", "Cans delivered to the base")
    _plot_bands(axes, results, collection_curves(results), variants, legend="lower right")
    figure.savefig(path, dpi=150)


def _plot_bands(axes, results: Results, curves: pd.DataFrame, variants, legend: str) -> None:
    """Mean curve of each variant with its 95% band; `curves` has one column per run."""
    for variant in variants:
        run_ids = results.runs.loc[results.runs["variant"] == variant, "run_id"]
        band = curve_band(curves[run_ids.tolist()])
        color = COLORS[variant]
        axes.fill_between(band.index, band["low"], band["high"], color=color, alpha=0.18, lw=0)
        style = LINE_STYLES.get(variant, "-")
        axes.plot(
            band.index,
            band["mean"],
            color=color,
            linewidth=2,
            linestyle=style,
            label=LABELS[variant],
        )
    axes.set_xlim(left=0)
    axes.set_ylim(bottom=0)
    axes.legend(frameon=False, loc=legend, labelcolor=TEXT_PRIMARY)


def plot_cans_per_agent(results: Results, variants: Sequence[str], title: str, path: Path) -> None:
    """Distribution of cans delivered per agent, pooled over all runs of a variant."""
    data = []
    for variant in variants:
        run_ids = results.runs.loc[results.runs["variant"] == variant, "run_id"]
        data.append(results.agents.loc[results.agents["run_id"].isin(run_ids), "cans"])
    _box_plot(data, variants, title, "Cans delivered per agent", path)


def plot_party_latency(results: Results, variants: Sequence[str], title: str, path: Path) -> None:
    """Distribution over runs of the mean steps to pick up half of a party's cans."""
    per_run = party_latencies(results)
    data = [per_run.loc[per_run["variant"] == variant, "latency_50"] for variant in variants]
    _box_plot(data, variants, title, "Steps to pick up 50% of a party (mean per run)", path)


def plot_cans_on_map(results: Results, variants: Sequence[str], title: str, path: Path) -> None:
    """Mean cans left on the map with its 95% band; dotted lines mark the parties."""
    curves = results.timeline.pivot(index="step", columns="run_id", values="cans_on_map").ffill()
    figure = Figure(figsize=(8, 4.5), layout="constrained")
    axes = _style_axes(figure, title, "Step", "Cans on the map")
    for step in sorted(results.events["spawn_step"].unique()):
        axes.axvline(step, color=TEXT_SECONDARY, linewidth=1, linestyle=":")
    _plot_bands(axes, results, curves, variants, legend="upper right")
    figure.savefig(path, dpi=150)


def _sweep_axis(axes, values: Sequence[float]) -> None:
    """Doubling values (agents, radius) spread evenly on a log axis; a zero needs a linear one."""
    if min(values) > 0:
        axes.set_xscale("log", base=2)
    axes.set_xticks(values, [f"{value:g}" for value in values])
    axes.minorticks_off()


def _sweep_xlabel(parameter: str) -> str:
    return f"{SWEEP_TITLES[parameter][1]} {SWEEPS[parameter].symbol}"


def plot_sweep(runs: pd.DataFrame, column: str, title: str, ylabel: str, path: Path) -> None:
    """Mean of `column` from `sweep_table` for each variant, with its 95% band."""
    table = sweep_table(runs)
    figure = Figure(figsize=(8, 4.5), layout="constrained")
    axes = _style_axes(figure, title, _sweep_xlabel(sweep_parameter(runs)), ylabel)
    for variant in _present(table, VARIANT_ORDER):
        rows = table[table["variant"] == variant]
        mean, half_width = rows[f"{column}_mean"], rows[f"{column}_ci"].fillna(0)
        color = COLORS[variant]
        axes.fill_between(
            rows["value"], mean - half_width, mean + half_width, color=color, alpha=0.18, lw=0
        )
        axes.plot(rows["value"], mean, color=color, linewidth=2, marker="o", label=LABELS[variant])
    _sweep_axis(axes, sorted(table["value"].unique()))
    axes.set_ylim(bottom=0)
    axes.legend(frameon=False, loc="best", labelcolor=TEXT_PRIMARY)
    figure.savefig(path, dpi=150)


def plot_aco_advantage(runs: pd.DataFrame, title: str, path: Path) -> None:
    """How many times faster ACO N1 reaches 90% than the random walk, per value of the sweep."""
    table = aco_advantage(runs)
    figure = Figure(figsize=(8, 4.5), layout="constrained")
    xlabel = _sweep_xlabel(sweep_parameter(runs))
    axes = _style_axes(figure, title, xlabel, "t_90 random walk / t_90 ACO N1")
    axes.axhline(1, color=TEXT_SECONDARY, linewidth=1, linestyle=":")
    axes.plot(table["value"], table["ratio"], color=COLORS[ACO_SHARED], linewidth=2, marker="o")
    _sweep_axis(axes, table["value"].tolist())
    axes.set_ylim(bottom=0)
    figure.savefig(path, dpi=150)


def plot_aco_advantage_by_layout(runs: pd.DataFrame, title: str, path: Path) -> None:
    """How many times faster ACO N1 reaches 90% than the random walk, per layout."""
    table = aco_advantage(runs, by="layout")
    figure = Figure(figsize=(8, 4.5), layout="constrained")
    axes = _style_axes(figure, title, "Can layout", "t_90 random walk / t_90 ACO N1")
    axes.grid(axis="x", visible=False)
    positions = np.arange(len(table))
    axes.bar(positions, table["ratio"], width=0.5, color=COLORS[ACO_SHARED])
    for position, ratio in zip(positions, table["ratio"], strict=True):
        axes.annotate(
            f"{ratio:.2f}",
            (position, ratio),
            xytext=(0, 4),
            textcoords="offset points",
            ha="center",
            color=TEXT_PRIMARY,
        )
    axes.axhline(1, color=TEXT_SECONDARY, linewidth=1, linestyle=":")
    axes.set_xticks(positions, table["layout"])
    axes.set_ylim(bottom=0)
    figure.savefig(path, dpi=150)


def plot_by_layout(runs: pd.DataFrame, column: str, title: str, ylabel: str, path: Path) -> None:
    """Mean of `column` from `layout_table` with its 95% interval, grouped by layout."""
    table = layout_table(runs)
    layouts = layout_order(runs)
    variants = _present(table, VARIANT_ORDER)
    figure = Figure(figsize=(8, 4.5), layout="constrained")
    axes = _style_axes(figure, title, "Can layout", ylabel)
    axes.grid(axis="x", visible=False)
    width = 0.8 / max(len(variants), 1)
    for index, variant in enumerate(variants):
        rows = table[table["variant"] == variant].set_index("layout").reindex(layouts)
        positions = np.arange(len(layouts)) + (index - (len(variants) - 1) / 2) * width
        axes.bar(
            positions,
            rows[f"{column}_mean"],
            width=width,
            color=COLORS[variant],
            edgecolor="white",  # a gap between neighbouring bars
            linewidth=1,
            yerr=rows[f"{column}_ci"].fillna(0),
            error_kw={"ecolor": TEXT_SECONDARY, "elinewidth": 1, "capsize": 3},
            label=LABELS[variant],
        )
    axes.set_xticks(np.arange(len(layouts)), layouts)
    axes.set_ylim(bottom=0)
    axes.legend(frameon=False, loc="best", labelcolor=TEXT_PRIMARY)
    figure.savefig(path, dpi=150)


def plot_tradeoff(runs: pd.DataFrame, title: str, path: Path) -> None:
    """Mean t_90 against mean Gini of each variant with 95% intervals: lower-left is better."""
    table = signal_table(runs)
    figure = Figure(figsize=(8, 4.5), layout="constrained")
    axes = _style_axes(figure, title, "t_90 [steps]", "Gini of cans per agent")
    for row in table.itertuples():
        axes.errorbar(
            row.t_90_mean,
            row.gini_mean,
            xerr=0 if np.isnan(row.t_90_ci) else row.t_90_ci,
            yerr=0 if np.isnan(row.gini_ci) else row.gini_ci,
            fmt="o",
            markersize=8,
            color=COLORS[row.variant],
            markeredgecolor="white",  # a ring keeps overlapping points apart
            markeredgewidth=2,
            ecolor=COLORS[row.variant],
            elinewidth=1,
            capsize=3,
            label=LABELS[row.variant],
        )
    axes.set_xlim(left=0)
    axes.set_ylim(bottom=0)
    axes.legend(frameon=False, loc="best", labelcolor=TEXT_PRIMARY, fontsize=9)
    figure.savefig(path, dpi=150)


def _box_plot(
    data: Sequence[pd.Series], variants: Sequence[str], title: str, ylabel: str, path: Path
) -> None:
    figure = Figure(figsize=(8, 4.5), layout="constrained")
    axes = _style_axes(figure, title, "", ylabel)
    axes.grid(axis="x", visible=False)
    boxes = axes.boxplot(
        data,
        widths=0.45,
        patch_artist=True,
        medianprops={"color": TEXT_PRIMARY, "linewidth": 2},
        whiskerprops={"color": TEXT_SECONDARY},
        capprops={"color": TEXT_SECONDARY},
        flierprops={"markersize": 3, "markeredgecolor": TEXT_SECONDARY, "alpha": 0.5},
    )
    for box, variant in zip(boxes["boxes"], variants, strict=True):
        box.set(facecolor=COLORS[variant], edgecolor=COLORS[variant])
    axes.set_xticks(range(1, len(variants) + 1), [LABELS[variant] for variant in variants])
    axes.set_ylim(bottom=0)
    figure.savefig(path, dpi=150)


def _with_ci(mean: float, half_width: float, digits: int) -> str:
    if np.isnan(mean):
        return "n/a"
    if np.isnan(half_width):
        return f"{mean:.{digits}f}"
    return f"{mean:.{digits}f} ± {half_width:.{digits}f}"


def _percent(share: float) -> str:
    return "n/a" if np.isnan(share) else f"{100 * share:.1f}%"


def _markdown_table(header: Sequence[str], rows: Iterable[Sequence[object]]) -> str:
    lines = [" | ".join(header), " | ".join("---" for _ in header)]
    lines += [" | ".join(str(cell) for cell in row) for row in rows]
    return "\n".join(f"| {line} |" for line in lines)


def map_label(runs: pd.DataFrame) -> str:
    """Name of the map the runs come from; files made before maps were recorded have none."""
    if "map" not in runs:
        return "map not recorded"
    return ", ".join(sorted(runs["map"].unique()))


def scenario_label(runs: pd.DataFrame) -> str:
    """Scenario of the runs; with parties, t_90 counts their cans too."""
    if "scenario" not in runs:
        return "not recorded"
    return ", ".join(sorted(runs["scenario"].unique()))


def format_signal_summary(runs: pd.DataFrame) -> str:
    """P3 tables as Markdown."""
    table = signal_table(runs)
    measures = _markdown_table(
        ("Variant", "t_90", "Gini", *(f"J, w1 = {w1:g}" for w1 in J_WEIGHTS), "Reached 90%"),
        (
            (
                row["variant"],
                _with_ci(row["t_90_mean"], row["t_90_ci"], 0),
                _with_ci(row["gini_mean"], row["gini_ci"], 3),
                *(_with_ci(row[f"J_{w1:g}_mean"], row[f"J_{w1:g}_ci"], 3) for w1 in J_WEIGHTS),
                f"{row['t_90_reached']}/{row['runs']}",
            )
            for _, row in table.iterrows()
        ),
    )
    best = _markdown_table(
        ("w1", "Highest mean J", "J"),
        ((f"{row.w1:g}", row.variant, f"{row.J:.3f}") for row in best_by_weight(runs).itertuples()),
    )
    significance = _markdown_table(
        (
            "Signal",
            "Measure",
            "Mean",
            f"Mean of {ACO_SHARED}",
            "p-value",
            "Bonferroni threshold",
            "Significant",
        ),
        (
            (
                row.variant,
                row.metric,
                f"{row.mean:.3g}",
                f"{row.reference_mean:.3g}",
                f"{row.p_value:.3g}",
                f"{row.threshold:.3g}",
                "yes" if row.significant else "no",
            )
            for row in signal_significance(runs).itertuples()
        ),
    )
    return (
        "## Trail signals (P3)\n\n"
        f"Mean ± 95% interval. `{ACO_SHARED}` is the `source` signal. J = w1 · (1 − t_90 / T) "
        f"+ (1 − w1) · (1 − Gini), a run below 90% has no pace; runs.csv holds J for "
        f"w1 = {J_WEIGHT:g}.\n\n"
        f"{measures}\n\n"
        "Variant with the highest mean J for each weight (descriptive, no test):\n\n"
        f"{best}\n\n"
        f"Two-sided Mann-Whitney test of each signal against {ACO_SHARED} on its own measure, "
        "Bonferroni correction over these tests.\n\n"
        f"{significance}\n"
    )


def format_party_summary(results: Results) -> str:
    """P4 tables as Markdown."""
    table = _markdown_table(
        (
            "Variant",
            "Steps to first pick-up",
            "Steps to 50% of a party",
            "Agents per party",
            "Parties reaching 50%",
            "Cans landing on cans",
        ),
        (
            (
                row["variant"],
                _with_ci(row["latency_first_mean"], row["latency_first_ci"], 0),
                _with_ci(row["latency_50_mean"], row["latency_50_ci"], 0),
                _with_ci(row["agents_visited_mean"], row["agents_visited_ci"], 1),
                f"{row['reached_50']}/{row['parties']}",
                _percent(row["overlap_share_mean"]),
            )
            for _, row in party_table(results).iterrows()
        ),
    )
    significance = _markdown_table(
        ("Metric", "Variant A", "Variant B", "p-value"),
        (
            (row["metric"], row["variant_a"], row["variant_b"], f"{row['p_value']:.3g}")
            for _, row in party_significance(results).iterrows()
        ),
    )
    return (
        "## Parties (P4)\n\n"
        "Mean over the parties of a run, then mean ± 95% interval over runs. Steps count from a "
        "party to a pick-up. A party not reached by the limit counts as the steps it had.\n\n"
        f"{table}\n\n"
        "Two-sided Mann-Whitney test of the per-run means, no correction.\n\n"
        f"{significance}\n"
    )


def format_sweep_summary(runs: pd.DataFrame) -> str:
    """Tables of a sweep (P5, P7 to P9) as Markdown."""
    parameter = sweep_parameter(runs)
    comparison, name = SWEEP_TITLES[parameter]
    symbol = SWEEPS[parameter].symbol
    with_work = parameter == "n_agents"
    header = [symbol, "Variant", "t_90"]
    if with_work:
        header.append("Agent-steps N · t_90")
    header += ["Gini", "Reached 90%"]

    def row_cells(row) -> list:
        cells = [f"{row.value:g}", row.variant, _with_ci(row.t_90_mean, row.t_90_ci, 0)]
        if with_work:
            cells.append(_with_ci(row.work_mean, row.work_ci, 0))
        return [*cells, _with_ci(row.gini_mean, row.gini_ci, 3), f"{row.t_90_reached}/{row.runs}"]

    # itertuples keeps the integer columns integers, iterrows can make them floats
    table = _markdown_table(header, (row_cells(row) for row in sweep_table(runs).itertuples()))
    advantage = _markdown_table(
        (symbol, "t_90 random / t_90 ACO N1", "ACO N1 faster on"),
        (
            (f"{row.value:g}", f"{row.ratio:.2f}", f"{row.aco_faster}/{row.seeds}")
            for row in aco_advantage(runs).itertuples()
        ),
    )
    if parameter in TRAIL_SWEEPS:
        return _format_trail_sweep(runs, f"# {name} ({comparison})", symbol, table, advantage)
    tests = sweep_significance(runs)
    paired = parameter not in UNPAIRED_SWEEPS
    significance = _markdown_table(
        (symbol, *(("Pairs",) if paired else ()), "p-value", "Bonferroni threshold", "Significant"),
        (
            (
                f"{row.value:g}",
                *((row.pairs,) if paired else ()),
                f"{row.p_value:.3g}",
                f"{row.threshold:.3g}",
                "yes" if row.significant else "no",
            )
            for row in tests.itertuples()
        ),
    )
    variant_a, variant_b = P5_PAIR
    test = (
        "Two-sided Wilcoxon signed-rank test of t_90 paired by seed"
        if paired
        else "Two-sided Mann-Whitney test of t_90"
    )
    return (
        f"# {name} ({comparison})\n\n"
        f"Map: {map_label(runs)}. Scenario: {scenario_label(runs)}.\n\n"
        "Mean ± 95% confidence interval. A run below 90% counts as the step limit T.\n\n"
        f"{table}\n\n"
        "## Advantage of ACO N1\n\n"
        "Ratio of the mean t_90 values over the seeds both variants ran on.\n\n"
        f"{advantage}\n\n"
        "## Significance\n\n"
        f"{test}, {variant_a} vs {variant_b}, one test per {symbol}, "
        "Bonferroni correction over those tests.\n\n"
        f"{significance}\n"
    )


def _format_trail_sweep(
    runs: pd.DataFrame, heading: str, symbol: str, table: str, advantage: str
) -> str:
    default = default_value(sweep_parameter(runs))
    significance = _markdown_table(
        (
            symbol,
            "Pairs",
            f"t_90 / t_90 at {symbol} = {default}",
            "p-value",
            "Bonferroni threshold",
            "Significant",
        ),
        (
            (
                f"{row.value:g}",
                row.pairs,
                f"{row.t_90_ratio:.2f}",
                f"{row.p_value:.3g}",
                f"{row.threshold:.3g}",
                "yes" if row.significant else "no",
            )
            for row in trail_sweep_significance(runs).itertuples()
        ),
    )
    return (
        f"{heading}\n\n"
        f"Map: {map_label(runs)}. Scenario: {scenario_label(runs)}.\n\n"
        "Mean ± 95% confidence interval. A run below 90% counts as the step limit T. "
        f"{symbol} changes only {ACO_SHARED}; the other variants are a fixed reference.\n\n"
        f"{table}\n\n"
        "## Advantage of ACO N1\n\n"
        "Ratio of the mean t_90 values over the seeds both variants ran on.\n\n"
        f"{advantage}\n\n"
        "## Significance\n\n"
        f"Two-sided Wilcoxon signed-rank test of t_90 paired by seed, {ACO_SHARED} at each "
        f"{symbol} vs {ACO_SHARED} at the default {symbol} = {default}, Bonferroni correction "
        "over those tests.\n\n"
        f"{significance}\n"
    )


def format_layout_summary(runs: pd.DataFrame) -> str:
    """P6 tables as Markdown."""
    runs = with_layout(runs)
    table = _markdown_table(
        ("Layout", "Variant", "t_90", "Gini", "Reached 90%"),
        (
            (
                row.layout,
                row.variant,
                _with_ci(row.t_90_mean, row.t_90_ci, 0),
                _with_ci(row.gini_mean, row.gini_ci, 3),
                f"{row.t_90_reached}/{row.runs}",
            )
            for row in layout_table(runs).itertuples()
        ),
    )
    advantage = _markdown_table(
        ("Layout", "t_90 random / t_90 ACO N1", "ACO N1 faster on"),
        (
            (row.layout, f"{row.ratio:.2f}", f"{row.aco_faster}/{row.seeds}")
            for row in aco_advantage(runs, by="layout").itertuples()
        ),
    )
    significance = _markdown_table(
        ("Layout", "Metric", "Pairs", "p-value", "Bonferroni threshold", "Significant"),
        (
            (
                row.layout,
                row.metric,
                row.pairs,
                f"{row.p_value:.3g}",
                f"{row.threshold:.3g}",
                "yes" if row.significant else "no",
            )
            for row in layout_significance(runs).itertuples()
        ),
    )
    variant_a, variant_b = P5_PAIR
    return (
        "# Can layout (P6)\n\n"
        f"Map: {map_label(runs)}. Scenario: {scenario_label(runs)}.\n\n"
        "Mean ± 95% confidence interval. A run below 90% counts as the step limit T.\n\n"
        f"{table}\n\n"
        "## Advantage of ACO N1\n\n"
        "Ratio of the mean t_90 values over the seeds both variants ran on.\n\n"
        f"{advantage}\n\n"
        "## Significance\n\n"
        f"Two-sided Wilcoxon signed-rank test, {variant_a} vs {variant_b} paired by seed, for "
        "t_90 and Gini in each layout, Bonferroni correction over all of these tests. A seed "
        "with no difference drops out of its test.\n\n"
        f"{significance}\n"
    )


def report_text(results: Results) -> str:
    """Everything `summary.md` holds: P1 and P2 tables, and P4 in a run with parties.

    Runs of a sweep get only its tables (P5, P7 to P9), and with several layouts only the P6
    tables.
    """
    if has_layout_sweep(results):
        return format_layout_summary(results.runs)
    if has_sweep(results):
        return format_sweep_summary(results.runs)
    text = format_summary(results.runs)
    if has_trails(results):
        text += "\n" + format_signal_summary(results.runs)
    if has_parties(results):
        text += "\n" + format_party_summary(results)
    return text


def format_summary(runs: pd.DataFrame) -> str:
    """Summary and significance tables as Markdown."""
    summary = _markdown_table(
        (
            "Variant",
            "t_50",
            "t_90",
            "Path per can",
            "Trips",
            "Gini",
            "Cans per agent (min / max)",
            "Reached 90%",
            "Collected all",
        ),
        (
            (
                row["variant"],
                _with_ci(row["t_50_mean"], row["t_50_ci"], 0),
                _with_ci(row["t_90_mean"], row["t_90_ci"], 0),
                _with_ci(row["path_per_can_mean"], row["path_per_can_ci"], 1),
                _with_ci(row["trips_mean"], row["trips_ci"], 0),
                _with_ci(row["gini_mean"], row["gini_ci"], 3),
                f"{row['cans_min_mean']:.1f} / {row['cans_max_mean']:.1f}",
                f"{row['t_90_reached']}/{row['runs']}",
                f"{row['t_100_reached']}/{row['runs']}",
            )
            for _, row in summary_table(runs).iterrows()
        ),
    )
    significance = _markdown_table(
        ("Metric", "Variant A", "Variant B", "p-value"),
        (
            (row["metric"], row["variant_a"], row["variant_b"], f"{row['p_value']:.3g}")
            for _, row in significance_table(runs).iterrows()
        ),
    )
    return (
        "# Summary\n\n"
        f"Map: {map_label(runs)}.\n\n"
        "Mean ± 95% confidence interval. A run below a threshold counts as the step limit T.\n\n"
        f"{summary}\n\n"
        "## Significance\n\n"
        "Two-sided Mann-Whitney test, no correction for multiple comparisons.\n\n"
        f"{significance}\n"
    )


def write_report(results: Results, output_dir: str | Path) -> list[Path]:
    """Write the figures of every comparison whose variants are all present, and the summary."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    written = []
    label = map_label(results.runs)
    if has_layout_sweep(results):
        written += _write_layout_figures(with_layout(results.runs), label, output)
        available = set()  # P1, P2 and P4 would mix layouts
    elif has_sweep(results):
        written += _write_sweep_figures(results.runs, label, output)
        available = set()  # P1, P2 and P4 would mix runs of different settings
    else:
        available = set(results.runs["variant"])
    if available.issuperset(P1_VARIANTS):
        path = output / "p1_collection_curve.png"
        plot_collection_curves(results, P1_VARIANTS, f"P1: ACO vs random walk ({label})", path)
        written.append(path)
    if available.issuperset(P2_VARIANTS):
        path = output / "p2_collection_curve.png"
        title = f"P2: shared vs individual reward ({label})"
        plot_collection_curves(results, P2_VARIANTS, title, path)
        written.append(path)
        path = output / "p2_cans_per_agent.png"
        plot_cans_per_agent(results, P2_VARIANTS, f"P2: cans delivered per agent ({label})", path)
        written.append(path)
    if available and has_trails(results):
        signals = [variant for variant in P3_VARIANTS if variant in available]
        path = output / "p3_collection_curve.png"
        plot_collection_curves(results, signals, f"P3: trail signals of ACO N1 ({label})", path)
        written.append(path)
        path = output / "p3_tradeoff.png"
        plot_tradeoff(results.runs, f"P3: pace against equality ({label})", path)
        written.append(path)
    if available and has_parties(results) and available.issuperset(P2_VARIANTS):
        path = output / "p4_cans_on_map.png"
        plot_cans_on_map(results, P2_VARIANTS, f"P4: cans on the map with parties ({label})", path)
        written.append(path)
        path = output / "p4_party_latency.png"
        title = f"P4: how fast a party is taken up ({label})"
        plot_party_latency(results, P2_VARIANTS, title, path)
        written.append(path)
    path = output / "summary.md"
    path.write_text(report_text(results), encoding="utf-8")
    written.append(path)
    return written


def _write_sweep_figures(runs: pd.DataFrame, label: str, output: Path) -> list[Path]:
    """P5 keeps its file names; the other sweeps are named after their comparison and parameter."""
    parameter = sweep_parameter(runs)
    comparison, name = SWEEP_TITLES[parameter]
    if parameter == "n_agents":
        prefix, suffix = "p5", "agents"
    else:
        folder = SWEEPS[parameter].folder
        prefix = comparison.lower() if comparison != "P9" else f"p9_{folder}"
        suffix = folder
    symbol = SWEEPS[parameter].symbol
    paths = [output / f"{prefix}_t90_vs_{suffix}.png"]
    title = f"{comparison}: time to 90% of the cans by {symbol} ({label})"
    plot_sweep(runs, "t_90", title, "t_90 [steps]", paths[0])
    if parameter == "n_agents":
        paths.append(output / "p5_work_vs_agents.png")
        title = f"P5: agent-steps to 90% of the cans ({label})"
        plot_sweep(runs, "work", title, "N · t_90", paths[-1])
    else:
        paths.append(output / f"{prefix}_gini_vs_{suffix}.png")
        title = f"{comparison}: inequality of cans per agent by {symbol} ({label})"
        plot_sweep(runs, "gini", title, "Gini", paths[-1])
    if set(runs["variant"]).issuperset(P5_PAIR):
        paths.append(output / f"{prefix}_aco_advantage.png")
        title = f"{comparison}: how many times faster ACO N1 is ({label})"
        plot_aco_advantage(runs, title, paths[-1])
    return paths


def _write_layout_figures(runs: pd.DataFrame, label: str, output: Path) -> list[Path]:
    paths = [output / f"p6_{name}_by_layout.png" for name in ("t90", "gini")]
    title = f"P6: time to 90% of the cans ({label})"
    plot_by_layout(runs, "t_90", title, "t_90 [steps]", paths[0])
    title = f"P6: inequality of cans per agent ({label})"
    plot_by_layout(runs, "gini", title, "Gini", paths[1])
    if set(runs["variant"]).issuperset(P5_PAIR):
        path = output / "p6_aco_advantage.png"
        plot_aco_advantage_by_layout(runs, f"P6: how many times faster ACO N1 is ({label})", path)
        paths.append(path)
    return paths


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Make figures and tables from experiment CSVs")
    parser.add_argument(
        "--input",
        type=Path,
        nargs="+",
        default=[Path("results/test")],
        help="directory with CSVs; several directories, one layout each, make comparison P6",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="report directory (default: <input>/figures, required with several inputs)",
    )
    args = parser.parse_args(argv)
    if len(args.input) > 1 and args.output is None:
        parser.error("--output is required with several --input directories")

    parts = [load_results(directory) for directory in args.input]
    if len(parts) > 1:  # joining directories only makes sense for layouts
        problem = check_layout_inputs(parts)
        if problem is not None:
            parser.error(problem)
    results = parts[0] if len(parts) == 1 else combine_results(parts)
    output = args.output or args.input[0] / "figures"
    write_report(results, output)
    print(report_text(results))
    print(f"Report written to {output}")


if __name__ == "__main__":
    main()
