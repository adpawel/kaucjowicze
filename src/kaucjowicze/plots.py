"""Figures and summary tables of comparisons P1 and P2, made from the CSV files of an experiment.

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


@dataclass(frozen=True)
class Results:
    runs: pd.DataFrame
    timeline: pd.DataFrame
    agents: pd.DataFrame


def load_results(input_dir: str | Path) -> Results:
    """Read the CSV files written by `kaucjowicze.experiments`."""
    directory = Path(input_dir)
    runs = pd.read_csv(directory / "runs.csv")
    timeline = pd.read_csv(directory / "timeline.csv")
    agents = pd.read_csv(directory / "agents.csv")
    has_reward = runs["reward"].notna()
    runs["variant"] = runs["algorithm"].where(~has_reward, runs["algorithm"] + "/" + runs["reward"])
    return Results(runs, timeline, agents)


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
    curves = collection_curves(results)
    figure = Figure(figsize=(8, 4.5), layout="constrained")
    axes = _style_axes(figure, title, "Step", "Cans delivered to the base")
    for variant in variants:
        run_ids = results.runs.loc[results.runs["variant"] == variant, "run_id"]
        band = curve_band(curves[run_ids.tolist()])
        color = COLORS[variant]
        axes.fill_between(band.index, band["low"], band["high"], color=color, alpha=0.18, lw=0)
        axes.plot(band.index, band["mean"], color=color, linewidth=2, label=LABELS[variant])
    axes.set_xlim(left=0)
    axes.set_ylim(bottom=0)
    axes.legend(frameon=False, loc="lower right", labelcolor=TEXT_PRIMARY)
    figure.savefig(path, dpi=150)


def plot_cans_per_agent(results: Results, variants: Sequence[str], title: str, path: Path) -> None:
    """Distribution of cans delivered per agent, pooled over all runs of a variant."""
    figure = Figure(figsize=(8, 4.5), layout="constrained")
    axes = _style_axes(figure, title, "", "Cans delivered per agent")
    axes.grid(axis="x", visible=False)
    data = []
    for variant in variants:
        run_ids = results.runs.loc[results.runs["variant"] == variant, "run_id"]
        data.append(results.agents.loc[results.agents["run_id"].isin(run_ids), "cans"])
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
    if np.isnan(half_width):
        return f"{mean:.{digits}f}"
    return f"{mean:.{digits}f} ± {half_width:.{digits}f}"


def _markdown_table(header: Sequence[str], rows: Iterable[Sequence[object]]) -> str:
    lines = [" | ".join(header), " | ".join("---" for _ in header)]
    lines += [" | ".join(str(cell) for cell in row) for row in rows]
    return "\n".join(f"| {line} |" for line in lines)


def map_label(runs: pd.DataFrame) -> str:
    """Name of the map the runs come from; files made before maps were recorded have none."""
    if "map" not in runs:
        return "map not recorded"
    return ", ".join(sorted(runs["map"].unique()))


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
    available = set(results.runs["variant"])
    label = map_label(results.runs)
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
    path = output / "summary.md"
    path.write_text(format_summary(results.runs), encoding="utf-8")
    written.append(path)
    return written


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
    print(format_summary(results.runs))
    print(f"Report written to {output}")


if __name__ == "__main__":
    main()
