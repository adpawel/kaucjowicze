"""Figures and summary tables of comparisons P1, P2, P4 and P5, made from experiment CSV files.

P4 compares how fast the variants take up the cans of parties in the dynamic scenario. P5 runs
the variants with several numbers of agents and replaces the other comparisons, which would
otherwise mix runs of different sizes.

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

CONFIDENCE = 0.95

RANDOM = "random"
ACO_SHARED = "aco/shared"
ACO_INDIVIDUAL = "aco/individual"
VARIANT_ORDER = (RANDOM, ACO_SHARED, ACO_INDIVIDUAL)
LABELS = {
    RANDOM: "Random walk",
    ACO_SHARED: "ACO, shared reward (N1)",
    ACO_INDIVIDUAL: "Individual reward (N2)",
}
# A variant keeps its color in every figure
COLORS = {RANDOM: "#2a78d6", ACO_SHARED: "#eb6834", ACO_INDIVIDUAL: "#1baf7a"}
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3df"

P1_VARIANTS = (RANDOM, ACO_SHARED)
P2_VARIANTS = (RANDOM, ACO_SHARED, ACO_INDIVIDUAL)
TESTED_PAIRS = (
    (ACO_SHARED, RANDOM),
    (ACO_SHARED, ACO_INDIVIDUAL),
    (ACO_INDIVIDUAL, RANDOM),
)
# P5 tests only this pair, once per number of agents, as decided before the measurement
P5_PAIR = (ACO_SHARED, RANDOM)
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
    return Results(runs, timeline, agents, events)


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


def has_agent_sweep(results: Results) -> bool:
    """Whether the runs come with more than one number of agents (comparison P5)."""
    return results.runs["n_agents"].nunique() > 1


def agent_sweep_table(runs: pd.DataFrame) -> pd.DataFrame:
    """One row per number of agents and variant.

    `work` is N · t_90, the agent-steps spent until 90% of the cans are delivered: if it grows
    with N, each extra agent adds less than the ones before.
    """
    rows = []
    for n_agents in sorted(runs["n_agents"].unique()):
        same_n = runs[runs["n_agents"] == n_agents]
        for variant in _present(same_n, VARIANT_ORDER):
            group = same_n[same_n["variant"] == variant]
            t_90 = censored(group, "t_90")
            row: dict[str, object] = {"n_agents": int(n_agents), "variant": variant}
            row["runs"] = len(group)
            row["t_90_mean"], row["t_90_ci"] = mean_ci(t_90)
            row["work_mean"], row["work_ci"] = mean_ci(t_90 * n_agents)
            row["gini_mean"], row["gini_ci"] = mean_ci(group["gini"])
            row["t_90_reached"] = int(group["t_90"].notna().sum())
            rows.append(row)
    return pd.DataFrame(rows)


def aco_advantage(runs: pd.DataFrame) -> pd.DataFrame:
    """Per number of agents: mean t_90 of the random walk over that of ACO N1, and on how many
    seeds ACO N1 is faster. Both use only the seeds that both variants ran on.
    """
    faster, slower = P5_PAIR
    rows = []
    for n_agents in sorted(runs["n_agents"].unique()):
        same_n = runs[runs["n_agents"] == n_agents]
        by_seed = {}
        for variant in (slower, faster):
            group = same_n[same_n["variant"] == variant]
            by_seed[variant] = censored(group, "t_90").set_axis(group["seed"])
        if by_seed[slower].empty or by_seed[faster].empty:
            continue
        paired = pd.concat(by_seed, axis=1, join="inner")
        rows.append(
            {
                "n_agents": int(n_agents),
                "ratio": paired[slower].mean() / paired[faster].mean(),
                "aco_faster": int((paired[faster] < paired[slower]).sum()),
                "seeds": len(paired),
            }
        )
    return pd.DataFrame(rows, columns=["n_agents", "ratio", "aco_faster", "seeds"])


def agent_sweep_significance(runs: pd.DataFrame) -> pd.DataFrame:
    """Two-sided Mann-Whitney test of t_90, ACO N1 vs random walk, for each number of agents,
    with the Bonferroni threshold over those tests.
    """
    variant_a, variant_b = P5_PAIR
    rows = []
    for n_agents in sorted(runs["n_agents"].unique()):
        same_n = runs[runs["n_agents"] == n_agents]
        a = same_n[same_n["variant"] == variant_a]
        b = same_n[same_n["variant"] == variant_b]
        if a.empty or b.empty:
            continue
        p_value = _mann_whitney_p(censored(a, "t_90"), censored(b, "t_90"))
        rows.append({"n_agents": int(n_agents), "p_value": p_value})
    table = pd.DataFrame(rows, columns=["n_agents", "p_value"])
    table["threshold"] = SIGNIFICANCE_LEVEL / max(len(table), 1)
    table["significant"] = table["p_value"] < table["threshold"]
    return table


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
        axes.plot(band.index, band["mean"], color=color, linewidth=2, label=LABELS[variant])
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


def _agent_axis(axes, counts: Sequence[int]) -> None:
    axes.set_xscale("log", base=2)
    axes.set_xticks(counts, [str(count) for count in counts])
    axes.minorticks_off()


def plot_against_agents(
    runs: pd.DataFrame, column: str, title: str, ylabel: str, path: Path
) -> None:
    """Mean of `column` from `agent_sweep_table` for each variant, with its 95% band."""
    table = agent_sweep_table(runs)
    figure = Figure(figsize=(8, 4.5), layout="constrained")
    axes = _style_axes(figure, title, "Number of agents N", ylabel)
    for variant in _present(table, VARIANT_ORDER):
        rows = table[table["variant"] == variant]
        mean, half_width = rows[f"{column}_mean"], rows[f"{column}_ci"].fillna(0)
        color = COLORS[variant]
        axes.fill_between(
            rows["n_agents"], mean - half_width, mean + half_width, color=color, alpha=0.18, lw=0
        )
        axes.plot(
            rows["n_agents"], mean, color=color, linewidth=2, marker="o", label=LABELS[variant]
        )
    _agent_axis(axes, sorted(table["n_agents"].unique()))
    axes.set_ylim(bottom=0)
    axes.legend(frameon=False, loc="best", labelcolor=TEXT_PRIMARY)
    figure.savefig(path, dpi=150)


def plot_aco_advantage(runs: pd.DataFrame, title: str, path: Path) -> None:
    """How many times faster ACO N1 reaches 90% than the random walk, per number of agents."""
    table = aco_advantage(runs)
    figure = Figure(figsize=(8, 4.5), layout="constrained")
    axes = _style_axes(figure, title, "Number of agents N", "t_90 random walk / t_90 ACO N1")
    axes.axhline(1, color=TEXT_SECONDARY, linewidth=1, linestyle=":")
    axes.plot(table["n_agents"], table["ratio"], color=COLORS[ACO_SHARED], linewidth=2, marker="o")
    _agent_axis(axes, table["n_agents"].tolist())
    axes.set_ylim(bottom=0)
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


def format_agent_summary(runs: pd.DataFrame) -> str:
    """P5 tables as Markdown."""
    table = _markdown_table(
        ("N", "Variant", "t_90", "Agent-steps N · t_90", "Gini", "Reached 90%"),
        (
            (
                row.n_agents,
                row.variant,
                _with_ci(row.t_90_mean, row.t_90_ci, 0),
                _with_ci(row.work_mean, row.work_ci, 0),
                _with_ci(row.gini_mean, row.gini_ci, 3),
                f"{row.t_90_reached}/{row.runs}",
            )
            # itertuples keeps the integer columns integers, iterrows can make them floats
            for row in agent_sweep_table(runs).itertuples()
        ),
    )
    advantage = _markdown_table(
        ("N", "t_90 random / t_90 ACO N1", "ACO N1 faster on"),
        (
            (row.n_agents, f"{row.ratio:.2f}", f"{row.aco_faster}/{row.seeds}")
            for row in aco_advantage(runs).itertuples()
        ),
    )
    significance = _markdown_table(
        ("N", "p-value", "Bonferroni threshold", "Significant"),
        (
            (
                row.n_agents,
                f"{row.p_value:.3g}",
                f"{row.threshold:.3g}",
                "yes" if row.significant else "no",
            )
            for row in agent_sweep_significance(runs).itertuples()
        ),
    )
    variant_a, variant_b = P5_PAIR
    return (
        "# Number of agents (P5)\n\n"
        f"Map: {map_label(runs)}. Scenario: {scenario_label(runs)}.\n\n"
        "Mean ± 95% confidence interval. A run below 90% counts as the step limit T.\n\n"
        f"{table}\n\n"
        "## Advantage of ACO N1\n\n"
        "Ratio of the mean t_90 values over the seeds both variants ran on.\n\n"
        f"{advantage}\n\n"
        "## Significance\n\n"
        f"Two-sided Mann-Whitney test of t_90, {variant_a} vs {variant_b}, one test per N, "
        "Bonferroni correction over those tests.\n\n"
        f"{significance}\n"
    )


def report_text(results: Results) -> str:
    """Everything `summary.md` holds: P1 and P2 tables, and P4 in a run with parties.

    Runs with several numbers of agents get only the P5 tables.
    """
    if has_agent_sweep(results):
        return format_agent_summary(results.runs)
    text = format_summary(results.runs)
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
    if has_agent_sweep(results):
        written += _write_agent_figures(results.runs, label, output)
        available = set()  # P1, P2 and P4 would mix runs of different sizes
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


def _write_agent_figures(runs: pd.DataFrame, label: str, output: Path) -> list[Path]:
    paths = [output / f"p5_{name}.png" for name in ("t90_vs_agents", "work_vs_agents")]
    title = f"P5: time to 90% of the cans ({label})"
    plot_against_agents(runs, "t_90", title, "t_90 [steps]", paths[0])
    title = f"P5: agent-steps to 90% of the cans ({label})"
    plot_against_agents(runs, "work", title, "N · t_90", paths[1])
    if set(runs["variant"]).issuperset(P5_PAIR):
        path = output / "p5_aco_advantage.png"
        plot_aco_advantage(runs, f"P5: how many times faster ACO N1 is ({label})", path)
        paths.append(path)
    return paths


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Make figures and tables from experiment CSVs")
    parser.add_argument(
        "--input", type=Path, default=Path("results/test"), help="directory with CSVs"
    )
    parser.add_argument(
        "--output", type=Path, default=None, help="report directory (default: <input>/figures)"
    )
    args = parser.parse_args(argv)

    results = load_results(args.input)
    output = args.output or args.input / "figures"
    write_report(results, output)
    print(report_text(results))
    print(f"Report written to {output}")


if __name__ == "__main__":
    main()
