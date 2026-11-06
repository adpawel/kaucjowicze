import math

import pytest

pd = pytest.importorskip("pandas")
pytest.importorskip("matplotlib")
pytest.importorskip("scipy")

from kaucjowicze.config import SimulationConfig  # noqa: E402
from kaucjowicze.experiments import run_experiment, write_tables  # noqa: E402
from kaucjowicze.plots import (  # noqa: E402
    Results,
    censored,
    collection_curves,
    curve_band,
    load_results,
    main,
    mean_ci,
    significance_table,
    summary_table,
    write_report,
)


def _runs(rows: list[dict]) -> pd.DataFrame:
    """Rows of runs.csv with only the columns a test cares about."""
    defaults = {
        "max_steps": 100,
        "t_50": 10.0,
        "t_90": 20.0,
        "t_100": 30.0,
        "path_per_can": 5.0,
        "trips": 3,
        "gini": 0.5,
        "cans_min": 1,
        "cans_max": 9,
    }
    return pd.DataFrame([{**defaults, **row} for row in rows])


def _two_variants(a: list[float], b: list[float], column: str = "t_90") -> pd.DataFrame:
    rows = [{"run_id": i, "variant": "aco/shared", column: v} for i, v in enumerate(a)]
    rows += [{"run_id": 100 + i, "variant": "random", column: v} for i, v in enumerate(b)]
    return _runs(rows)


@pytest.fixture(scope="module")
def result_dir(tmp_path_factory):
    config = SimulationConfig(
        width=30,
        height=20,
        n_clusters=2,
        cans_per_cluster=5,
        n_background_cans=2,
        n_agents=3,
        max_steps=150,
    )
    output = tmp_path_factory.mktemp("results")
    write_tables(run_experiment(seeds=[0, 1, 2], config=config), output)
    return output


def test_mean_ci_uses_student_t():
    mean, half_width = mean_ci([1.0, 2.0, 3.0, 4.0, 5.0])
    assert mean == pytest.approx(3.0)
    # t(0.975, df=4) = 2.776, s = sqrt(2.5), n = 5
    assert half_width == pytest.approx(2.7764451 * math.sqrt(2.5) / math.sqrt(5))


def test_mean_ci_of_constant_values_is_zero():
    assert mean_ci([4.0, 4.0, 4.0]) == (4.0, 0.0)


def test_mean_ci_of_one_value_has_no_interval():
    mean, half_width = mean_ci([4.0])
    assert mean == 4.0
    assert math.isnan(half_width)


def test_mean_ci_skips_missing_values():
    mean, _ = mean_ci([1.0, float("nan"), 3.0])
    assert mean == pytest.approx(2.0)


def test_censored_counts_unreached_threshold_as_step_limit():
    runs = _runs([{"t_90": 40.0}, {"t_90": float("nan"), "max_steps": 75}])
    assert censored(runs, "t_90").tolist() == [40.0, 75.0]


def test_collection_curves_keep_finished_runs_flat():
    runs = _runs([{"run_id": 0, "variant": "a"}, {"run_id": 1, "variant": "a"}])
    timeline = pd.DataFrame(
        {
            "run_id": [0, 0, 1, 1, 1, 1],
            "step": [0, 1, 0, 1, 2, 3],
            "cans_collected": [0, 10, 0, 1, 2, 3],
        }
    )
    curves = collection_curves(Results(runs, timeline, pd.DataFrame()))

    assert curves.index.tolist() == [0, 1, 2, 3]
    assert curves[0].tolist() == [0, 10, 10, 10]  # finished early, the cans stay collected
    assert curves[1].tolist() == [0, 1, 2, 3]


def test_curve_band_is_mean_with_interval_at_every_step():
    curves = pd.DataFrame({0: [0.0, 2.0], 1: [0.0, 4.0], 2: [0.0, 6.0]}, index=[0, 1])

    band = curve_band(curves)

    assert band["mean"].tolist() == [0.0, 4.0]
    _, half_width = mean_ci([2.0, 4.0, 6.0])
    assert band.loc[0, "low"] == band.loc[0, "high"] == 0.0
    assert band.loc[1, "high"] == pytest.approx(4.0 + half_width)
    assert band.loc[1, "low"] == pytest.approx(4.0 - half_width)


def test_summary_counts_runs_reaching_each_threshold():
    runs = _two_variants([50.0, float("nan")], [80.0, 90.0])
    runs.loc[1, "t_100"] = float("nan")

    summary = summary_table(runs).set_index("variant")

    assert summary.loc["aco/shared", "runs"] == 2
    assert summary.loc["aco/shared", "t_90_reached"] == 1
    assert summary.loc["aco/shared", "t_100_reached"] == 1
    assert summary.loc["random", "t_90_reached"] == 2
    assert summary.loc["aco/shared", "t_90_mean"] == pytest.approx((50.0 + 100.0) / 2)  # censored
    assert summary.loc["random", "t_90_mean"] == pytest.approx(85.0)


def test_summary_lists_variants_in_a_fixed_order():
    runs = _runs(
        [
            {"run_id": 0, "variant": "aco/individual"},
            {"run_id": 1, "variant": "random"},
            {"run_id": 2, "variant": "aco/shared"},
        ]
    )
    assert summary_table(runs)["variant"].tolist() == ["random", "aco/shared", "aco/individual"]


def test_significance_separates_clearly_different_variants():
    fast = [float(v) for v in range(100, 130)]
    slow = [float(v) for v in range(200, 230)]

    table = significance_table(_two_variants(fast, slow))

    row = table[table["metric"] == "t_90"].iloc[0]
    assert (row["variant_a"], row["variant_b"]) == ("aco/shared", "random")
    assert row["p_value"] < 1e-6


def test_significance_does_not_separate_identical_variants():
    values = [float(v) for v in range(30)]
    table = significance_table(_two_variants(values, values))
    assert table[table["metric"] == "t_90"].iloc[0]["p_value"] == pytest.approx(1.0)


def test_significance_when_all_runs_hit_the_limit_shows_no_difference():
    missing = [float("nan")] * 5
    table = significance_table(_two_variants(missing, missing))
    assert table["p_value"].tolist() == [1.0, 1.0]  # Gini is equal in these runs as well


def test_significance_counts_unreached_runs_as_slowest():
    fast = [float(v) for v in range(10, 20)]
    never = [float("nan")] * 10
    table = significance_table(_two_variants(fast, never))
    assert table[table["metric"] == "t_90"].iloc[0]["p_value"] < 0.001


def test_significance_covers_gini_too():
    table = significance_table(_two_variants([0.1, 0.2, 0.3], [0.5, 0.6, 0.7], column="gini"))
    assert set(table["metric"]) == {"t_90", "gini"}


def test_significance_skips_absent_variants():
    runs = _runs([{"run_id": 0, "variant": "random"}, {"run_id": 1, "variant": "random"}])
    assert significance_table(runs).empty


def test_load_results_names_variants(result_dir):
    results = load_results(result_dir)
    assert set(results.runs["variant"]) == {"random", "aco/shared", "aco/individual"}
    assert len(results.runs) == 9


def test_load_results_explains_missing_files(tmp_path):
    with pytest.raises(FileNotFoundError, match="runs.csv"):
        load_results(tmp_path)


def test_report_writes_figures_and_summary(result_dir, tmp_path):
    written = write_report(load_results(result_dir), tmp_path)

    names = {path.name for path in written}
    assert names == {
        "p1_collection_curve.png",
        "p2_collection_curve.png",
        "p2_cans_per_agent.png",
        "summary.md",
    }
    for path in written:
        assert path.stat().st_size > 0
    assert (tmp_path / "p1_collection_curve.png").read_bytes().startswith(b"\x89PNG")
    summary = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert "aco/shared" in summary
    assert "p-value" in summary


def test_report_skips_comparisons_without_their_variants(result_dir, tmp_path):
    results = load_results(result_dir)
    kept = results.runs[results.runs["variant"].isin(["random", "aco/shared"])]
    partial = Results(
        kept,
        results.timeline[results.timeline["run_id"].isin(kept["run_id"])],
        results.agents[results.agents["run_id"].isin(kept["run_id"])],
    )

    names = {path.name for path in write_report(partial, tmp_path)}

    assert names == {"p1_collection_curve.png", "summary.md"}


def test_command_line_writes_report_to_chosen_directory(result_dir, tmp_path, capsys):
    main(["--input", str(result_dir), "--output", str(tmp_path / "figures")])

    assert (tmp_path / "figures" / "p2_cans_per_agent.png").exists()
    assert "t_90" in capsys.readouterr().out
