import math

import pytest

pd = pytest.importorskip("pandas")
pytest.importorskip("matplotlib")
pytest.importorskip("scipy")

from kaucjowicze.config import SimulationConfig  # noqa: E402
from kaucjowicze.experiments import run_agent_counts, run_experiment, write_tables  # noqa: E402
from kaucjowicze.plots import (  # noqa: E402
    Results,
    _percent,
    _with_ci,
    aco_advantage,
    agent_sweep_significance,
    agent_sweep_table,
    censored,
    collection_curves,
    combine_results,
    curve_band,
    format_summary,
    has_agent_sweep,
    has_layout_sweep,
    layout_order,
    layout_significance,
    layout_table,
    load_results,
    main,
    mean_ci,
    party_latencies,
    report_text,
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


def test_summary_names_the_map(result_dir):
    runs = load_results(result_dir).runs
    assert "Map: test." in format_summary(runs)
    assert "Map: map not recorded." in format_summary(runs.drop(columns="map"))


def test_report_goes_next_to_the_results_by_default(result_dir):
    main(["--input", str(result_dir)])
    assert (result_dir / "figures" / "summary.md").exists()


@pytest.fixture(scope="module")
def dynamic_dir(tmp_path_factory):
    config = SimulationConfig(
        width=30,
        height=20,
        scenario="dynamic",
        n_clusters=1,
        cans_per_cluster=5,
        n_background_cans=0,
        n_events=2,
        event_start=20,
        event_interval=20,
        n_agents=3,
        max_steps=200,
    )
    output = tmp_path_factory.mktemp("dynamic")
    write_tables(run_experiment(seeds=[0, 1, 2], config=config), output)
    return output


def test_static_report_has_no_party_comparison(result_dir, tmp_path):
    results = load_results(result_dir)
    assert results.events is not None and results.events.empty
    names = {path.name for path in write_report(results, tmp_path)}
    assert not any(name.startswith("p4_") for name in names)
    assert "Parties" not in (tmp_path / "summary.md").read_text(encoding="utf-8")


def test_dynamic_report_adds_the_party_comparison(dynamic_dir, tmp_path):
    names = {path.name for path in write_report(load_results(dynamic_dir), tmp_path)}
    assert {"p4_cans_on_map.png", "p4_party_latency.png"} <= names
    summary = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert "## Parties (P4)" in summary
    assert "latency_50" in summary


def test_party_latencies_have_one_row_per_run(dynamic_dir):
    results = load_results(dynamic_dir)
    per_run = party_latencies(results)
    assert len(per_run) == len(results.runs)
    assert (per_run["parties"] == 2).all()


def test_party_never_reached_counts_the_steps_it_had():
    runs = pd.DataFrame([{"run_id": 0, "variant": "random", "max_steps": 100}])
    events = pd.DataFrame(
        [
            {
                "run_id": 0,
                "event_id": 1,
                "spawn_step": 20,
                "latency_first": 5.0,
                "latency_50": 10.0,
                "agents_visited": 2,
                "overlap_share": 0.0,
            },
            {
                "run_id": 0,
                "event_id": 2,
                "spawn_step": 60,
                "latency_first": None,
                "latency_50": None,
                "agents_visited": 0,
                "overlap_share": 0.0,
            },
        ]
    )
    results = Results(runs, pd.DataFrame(), pd.DataFrame(), events)
    (row,) = party_latencies(results).to_dict("records")
    assert row["latency_50"] == pytest.approx((10 + 40) / 2)
    # the first pick-up is censored the same way, so both means cover the same parties
    assert row["latency_first"] == pytest.approx((5 + 40) / 2)
    assert row["reached_50"] == 1


def test_missing_values_are_shown_as_not_available():
    assert _with_ci(float("nan"), float("nan"), 0) == "n/a"
    assert _percent(float("nan")) == "n/a"
    assert _percent(0.125) == "12.5%"


def test_results_without_party_file_still_load(result_dir, tmp_path):
    for name in ("runs.csv", "timeline.csv", "agents.csv"):
        (tmp_path / name).write_bytes((result_dir / name).read_bytes())
    results = load_results(tmp_path)
    assert results.events is None
    write_report(results, tmp_path / "figures")


def _sweep(rows: list[dict]) -> pd.DataFrame:
    """Runs of the agent sweep: `t_90` given per (N, variant, seed)."""
    return _runs([{"run_id": i, **row} for i, row in enumerate(rows)])


def test_agent_sweep_table_has_a_row_per_count_and_variant():
    runs = _sweep(
        [
            {"n_agents": n, "variant": v, "seed": s, "t_90": t}
            for n, times in ((10, (40.0, 60.0)), (5, (80.0, None)))
            for v in ("aco/shared", "random")
            for s, t in enumerate(times)
        ]
    )
    table = agent_sweep_table(runs)

    assert list(zip(table["n_agents"], table["variant"], strict=True)) == [
        (5, "random"),
        (5, "aco/shared"),
        (10, "random"),
        (10, "aco/shared"),
    ]
    five = table.iloc[0]
    assert five["t_90_mean"] == pytest.approx((80 + 100) / 2)  # unreached counts as T = 100
    assert five["work_mean"] == pytest.approx(5 * 90)
    assert five["t_90_reached"] == 1


def test_aco_advantage_pairs_seeds():
    runs = _sweep(
        [
            {"n_agents": 5, "variant": "random", "seed": 0, "t_90": 90.0},
            {"n_agents": 5, "variant": "random", "seed": 1, "t_90": 30.0},
            {"n_agents": 5, "variant": "aco/shared", "seed": 0, "t_90": 30.0},
            {"n_agents": 5, "variant": "aco/shared", "seed": 1, "t_90": 50.0},
        ]
    )
    (row,) = aco_advantage(runs).to_dict("records")
    assert row["ratio"] == pytest.approx(60 / 40)
    assert (row["aco_faster"], row["seeds"]) == (1, 2)


def test_agent_sweep_tests_each_count_with_bonferroni():
    rows = []
    for n in (5, 10):
        rows += [
            {"n_agents": n, "variant": "aco/shared", "seed": s, "t_90": 10.0 + s} for s in range(8)
        ]
        rows += [
            {"n_agents": n, "variant": "random", "seed": s, "t_90": 50.0 + s} for s in range(8)
        ]
    table = agent_sweep_significance(_sweep(rows))

    assert table["n_agents"].tolist() == [5, 10]
    assert (table["threshold"] == 0.025).all()
    assert table["significant"].all()


@pytest.fixture(scope="module")
def sweep_dir(tmp_path_factory):
    config = SimulationConfig(
        width=30, height=20, n_clusters=2, cans_per_cluster=5, n_background_cans=2, max_steps=150
    )
    output = tmp_path_factory.mktemp("sweep")
    write_tables(run_agent_counts(seeds=[0, 1, 2], counts=[2, 4], config=config), output)
    return output


def test_sweep_report_replaces_the_other_comparisons(sweep_dir, result_dir, tmp_path):
    results = load_results(sweep_dir)
    assert has_agent_sweep(results)
    assert not has_agent_sweep(load_results(result_dir))

    names = {path.name for path in write_report(results, tmp_path)}

    assert names == {
        "p5_t90_vs_agents.png",
        "p5_work_vs_agents.png",
        "p5_aco_advantage.png",
        "summary.md",
    }
    summary = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert summary.startswith("# Number of agents (P5)")
    assert "Bonferroni" in summary
    assert "# Summary" not in summary


def test_aco_advantage_uses_only_seeds_both_variants_ran_on():
    runs = _sweep(
        [
            {"n_agents": 5, "variant": "random", "seed": 0, "t_90": 60.0},
            {"n_agents": 5, "variant": "random", "seed": 1, "t_90": 90.0},
            {"n_agents": 5, "variant": "aco/shared", "seed": 0, "t_90": 30.0},
        ]
    )
    (row,) = aco_advantage(runs).to_dict("records")
    assert row["ratio"] == pytest.approx(60 / 30)  # seed 1 has no ACO run, so it is left out
    assert (row["aco_faster"], row["seeds"]) == (1, 1)


def test_sweep_summary_names_the_scenario(sweep_dir):
    summary = report_text(load_results(sweep_dir))
    assert "Map: test. Scenario: static." in summary
    advantage = summary.split("## Advantage")[1]
    assert "| 2 | " in advantage and "| 4 | " in advantage  # counts stay integers
    assert ".0/" not in advantage


def _layouts(rows: list[dict]) -> pd.DataFrame:
    """Runs of the layout comparison: `t_90` and `gini` given per (layout, variant, seed)."""
    return _runs([{"run_id": i, **row} for i, row in enumerate(rows)])


def test_layouts_are_ordered_from_the_most_clustered():
    runs = _layouts([{"layout": name} for name in ("uniform", "current", "few-large", "odd")])
    assert layout_order(runs) == ["few-large", "current", "uniform", "odd"]


def test_layout_table_has_a_row_per_layout_and_variant():
    runs = _layouts(
        [
            {"layout": layout, "variant": variant, "seed": seed, "t_90": t_90}
            for layout in ("uniform", "few-large")
            for variant in ("aco/shared", "random")
            for seed, t_90 in enumerate((40.0, None))
        ]
    )
    table = layout_table(runs)

    assert list(zip(table["layout"], table["variant"], strict=True)) == [
        ("few-large", "random"),
        ("few-large", "aco/shared"),
        ("uniform", "random"),
        ("uniform", "aco/shared"),
    ]
    assert table.loc[0, "t_90_mean"] == pytest.approx((40 + 100) / 2)  # unreached counts as T
    assert table.loc[0, "t_90_reached"] == 1


def test_layout_tests_are_paired_by_seed_with_bonferroni_over_all():
    rows = []
    for layout in ("few-large", "uniform"):
        for seed in range(10):
            # ACO is faster on every seed, although the two samples overlap almost entirely
            rows.append(
                {"layout": layout, "variant": "random", "seed": seed, "t_90": 10.0 * seed + 5}
            )
            rows.append(
                {"layout": layout, "variant": "aco/shared", "seed": seed, "t_90": 10.0 * seed}
            )
            rows[-1]["gini"] = rows[-2]["gini"] = 0.5  # no difference at all
    table = layout_significance(_layouts(rows))

    assert table[["layout", "metric"]].values.tolist() == [
        ["few-large", "t_90"],
        ["few-large", "gini"],
        ["uniform", "t_90"],
        ["uniform", "gini"],
    ]
    assert (table["threshold"] == 0.05 / 4).all()
    assert (table["pairs"] == 10).all()
    t_90 = table[table["metric"] == "t_90"]
    assert t_90["significant"].all()  # an unpaired test would not see this difference
    assert (table.loc[table["metric"] == "gini", "p_value"] == 1.0).all()


def test_aco_advantage_by_layout():
    runs = _layouts(
        [
            {"layout": "uniform", "variant": "random", "seed": 0, "t_90": 60.0},
            {"layout": "uniform", "variant": "aco/shared", "seed": 0, "t_90": 30.0},
            {"layout": "few-large", "variant": "random", "seed": 0, "t_90": 90.0},
            {"layout": "few-large", "variant": "aco/shared", "seed": 0, "t_90": 30.0},
        ]
    )
    table = aco_advantage(runs, by="layout")
    assert table["layout"].tolist() == ["few-large", "uniform"]
    assert table["ratio"].tolist() == pytest.approx([3.0, 2.0])


@pytest.fixture(scope="module")
def layout_dirs(tmp_path_factory):
    dirs = []
    for name in ("few-large", "uniform"):
        config = SimulationConfig(width=30, height=20, n_agents=3, max_steps=150, layout=name)
        output = tmp_path_factory.mktemp(name)
        write_tables(run_experiment(seeds=[0, 1, 2], config=config), output)
        dirs.append(output)
    return dirs


def test_combined_layouts_keep_run_ids_apart(layout_dirs):
    parts = [load_results(directory) for directory in layout_dirs]
    results = combine_results(parts)

    assert results.runs["run_id"].is_unique
    assert len(results.runs) == sum(len(part.runs) for part in parts)
    assert set(results.timeline["run_id"]) == set(results.runs["run_id"])
    assert set(results.agents["run_id"]) == set(results.runs["run_id"])
    assert has_layout_sweep(results)
    assert not has_layout_sweep(parts[0])


def test_layout_report_replaces_the_other_comparisons(layout_dirs, tmp_path, capsys):
    main(["--input", *map(str, layout_dirs), "--output", str(tmp_path)])

    names = {path.name for path in tmp_path.iterdir()}
    assert names == {
        "p6_t90_by_layout.png",
        "p6_gini_by_layout.png",
        "p6_aco_advantage.png",
        "summary.md",
    }
    summary = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert summary.startswith("# Can layout (P6)")
    assert "Wilcoxon" in summary
    assert "# Summary" not in summary
    assert "Can layout (P6)" in capsys.readouterr().out


def test_several_inputs_need_an_output(layout_dirs, capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--input", *map(str, layout_dirs)])
    assert exc.value.code != 0
    assert "--output" in capsys.readouterr().err


def test_several_inputs_must_be_different_layouts(layout_dirs, result_dir, tmp_path, capsys):
    for inputs in ([layout_dirs[0], layout_dirs[0]], [result_dir, result_dir]):
        with pytest.raises(SystemExit) as exc:
            main(["--input", *map(str, inputs), "--output", str(tmp_path)])
        assert exc.value.code != 0
        assert "layout" in capsys.readouterr().err
