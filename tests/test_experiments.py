import csv
import subprocess
import sys
from dataclasses import replace

import pytest

from kaucjowicze.config import SimulationConfig
from kaucjowicze.experiments import (
    AGENTS_COLUMNS,
    EVENTS_COLUMNS,
    RUNS_COLUMNS,
    TIMELINE_COLUMNS,
    TRAIL_VARIANTS,
    VARIANTS,
    main,
    run_agent_counts,
    run_experiment,
    run_sweep,
    write_tables,
)
from kaucjowicze.factory import build_simulation

SMALL = SimulationConfig(
    width=30,
    height=20,
    n_clusters=2,
    cans_per_cluster=5,
    n_background_cans=2,
    n_agents=3,
    max_steps=60,
)


def _read(path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


@pytest.fixture(scope="module")
def tables():
    return run_experiment(seeds=[0, 1], config=SMALL)


def test_variants_are_those_of_the_comparisons():
    assert VARIANTS == (("random", None), ("aco", "shared"), ("aco", "individual"))


def test_every_seed_runs_every_variant(tables):
    pairs = [(row["seed"], row["algorithm"], row["reward"]) for row in tables.runs]
    assert pairs == [(seed, *variant) for seed in (0, 1) for variant in VARIANTS]
    assert len({row["run_id"] for row in tables.runs}) == 6


@pytest.mark.parametrize(("algorithm", "reward"), VARIANTS)
def test_variants_get_the_same_map_for_a_seed(algorithm, reward):
    reference = build_simulation("random", seed=3, config=SMALL)
    sim = build_simulation(algorithm, seed=3, reward=reward, config=SMALL)
    assert (sim.grid.cans == reference.grid.cans).all()


def test_build_simulation_keeps_config_and_uses_given_seed():
    sim = build_simulation("random", seed=3, config=SMALL)
    assert sim.config.seed == 3
    assert sim.config.n_agents == SMALL.n_agents


def test_columns_follow_the_documented_format():
    assert RUNS_COLUMNS == (
        "run_id",
        "seed",
        "algorithm",
        "reward",
        "scenario",
        "map",
        "n_agents",
        "k",
        "rho",
        "alpha",
        "beta",
        "eps",
        "max_steps",
        "initial_cans",
        "steps",
        "t_50",
        "t_90",
        "t_100",
        "cans_at_T",
        "total_path_length",
        "path_per_can",
        "trips",
        "gini",
        "cans_min",
        "cans_max",
        "J",
        "total_cans",
        "layout",
        "r",
        "sweep",
        "sweep_value",
        "trail",
    )
    assert TIMELINE_COLUMNS == (
        "run_id",
        "step",
        "cans_collected",
        "cans_on_map",
        "agents_searching",
        "agents_carrying",
    )
    assert AGENTS_COLUMNS == ("run_id", "agent_id", "cans", "path_length", "trips")
    assert EVENTS_COLUMNS == (
        "run_id",
        "event_id",
        "spawn_step",
        "x",
        "y",
        "cans",
        "overlap_share",
        "latency_first",
        "latency_50",
        "latency_90",
        "picked_up",
        "agents_visited",
    )


def test_rows_have_exactly_the_documented_columns(tables):
    assert all(tuple(row) == RUNS_COLUMNS for row in tables.runs)
    assert all(tuple(row) == TIMELINE_COLUMNS for row in tables.timeline)
    assert all(tuple(row) == AGENTS_COLUMNS for row in tables.agents)


def test_config_values_are_recorded(tables):
    row = tables.runs[0]
    assert row["scenario"] == "static"
    assert row["n_agents"] == SMALL.n_agents
    assert row["k"] == SMALL.bag_capacity
    assert row["r"] == SMALL.vision_radius
    assert row["max_steps"] == SMALL.max_steps
    assert row["initial_cans"] == 12
    assert row["total_cans"] == 12


def test_static_scenario_has_no_parties(tables):
    assert tables.events == []


def test_only_trail_following_variant_reports_pheromone_parameters(tables):
    by_reward = {row["reward"]: row for row in tables.runs}
    shared = by_reward["shared"]
    assert (shared["rho"], shared["alpha"], shared["eps"]) == (
        SMALL.evaporation_rate,
        SMALL.pheromone_alpha,
        SMALL.exploration_rate,
    )
    for reward in (None, "individual"):
        row = by_reward[reward]
        assert (row["rho"], row["alpha"], row["eps"]) == (None, None, None)


def test_aco_without_a_reward_is_recorded_as_the_shared_reward_it_runs():
    labels = []
    implicit = run_experiment(
        seeds=[0],
        config=SMALL,
        variants=(("aco", None),),
        progress=lambda done, total, label: labels.append(label),
    )
    explicit = run_experiment(seeds=[0], config=SMALL, variants=(("aco", "shared"),))

    assert implicit == explicit
    assert implicit.runs[0]["reward"] == "shared"
    assert implicit.runs[0]["rho"] == SMALL.evaporation_rate
    assert labels == ["aco/shared, seed 0"]


def test_beta_stays_empty_and_j_is_filled(tables):
    for row in tables.runs:
        assert row["beta"] is None
        t_90 = SMALL.max_steps if row["t_90"] is None else row["t_90"]
        expected = 0.5 * (1 - t_90 / SMALL.max_steps) + 0.5 * (1 - row["gini"])
        assert row["J"] == pytest.approx(expected)


def test_only_aco_n1_names_its_trail(tables):
    assert {row["reward"]: row["trail"] for row in tables.runs} == {
        None: None,
        "shared": "source",
        "individual": None,
    }


def test_trail_variants_run_aco_n1_with_another_signal():
    labels = []
    tables = run_experiment(
        seeds=[0],
        config=SMALL,
        variants=(("aco", "shared"), *TRAIL_VARIANTS),
        progress=lambda done, total, label: labels.append(label),
    )
    assert [row["trail"] for row in tables.runs] == ["source", "speed", "equal+", "equal-"]
    assert {row["reward"] for row in tables.runs} == {"shared"}
    assert labels[1] == "aco/shared/speed, seed 0"


@pytest.mark.parametrize("variant", [("random", None, "speed"), ("aco", "individual", "speed")])
def test_trail_signal_needs_aco_n1(variant):
    with pytest.raises(ValueError, match="only to ACO"):
        run_experiment(seeds=[0], config=SMALL, variants=(variant,))


def test_trails_get_their_own_directory_next_to_the_usual_variants(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    main(["--seeds", "1", "--max-steps", "2", "--trails", "speed", "equal-"])
    runs = _read(tmp_path / "results" / "test_trails" / "runs.csv")
    assert [(row["reward"], row["trail"]) for row in runs] == [
        ("", ""),
        ("shared", "source"),
        ("individual", ""),
        ("shared", "speed"),
        ("shared", "equal-"),
    ]
    assert not (tmp_path / "results" / "test").exists()


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (["--trails", "speed", "--sweep", "bag_capacity", "2"], "not with a sweep"),
        (["--trails", "speed", "--layout", "uniform"], "not with a sweep"),
        (["--trails", "speed", "speed"], "repeat"),
        (["--trails", "source"], "invalid choice"),
    ],
)
def test_command_line_rejects_invalid_trails(arguments, message, tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        main([*arguments, "--output", str(tmp_path)])
    assert exc.value.code != 0
    assert message in capsys.readouterr().err


def test_tables_of_one_run_agree(tables):
    for run in tables.runs:
        steps = [row for row in tables.timeline if row["run_id"] == run["run_id"]]
        agents = [row for row in tables.agents if row["run_id"] == run["run_id"]]
        assert len(steps) == run["steps"] + 1
        assert steps[-1]["cans_collected"] == run["cans_at_T"]
        assert len(agents) == SMALL.n_agents
        assert sum(agent["cans"] for agent in agents) == run["cans_at_T"]
        assert sum(agent["trips"] for agent in agents) == run["trips"]
        assert sum(agent["path_length"] for agent in agents) == run["total_path_length"]


def test_csv_files_round_trip_with_empty_values(tables, tmp_path):
    write_tables(tables, tmp_path)

    runs = _read(tmp_path / "runs.csv")
    assert tuple(runs[0]) == RUNS_COLUMNS
    assert len(runs) == len(tables.runs)
    assert len(_read(tmp_path / "timeline.csv")) == len(tables.timeline)
    assert len(_read(tmp_path / "agents.csv")) == len(tables.agents)
    random_run = runs[0]
    assert random_run["algorithm"] == "random"
    assert random_run["reward"] == ""
    assert random_run["rho"] == ""
    assert random_run["beta"] == ""


def test_threshold_not_reached_is_written_as_empty(tmp_path):
    config = SimulationConfig(
        width=30, height=20, n_clusters=2, cans_per_cluster=5, n_agents=1, max_steps=2
    )
    write_tables(run_experiment(seeds=[0], config=config), tmp_path)

    for row in _read(tmp_path / "runs.csv"):
        assert (row["t_50"], row["t_90"], row["t_100"]) == ("", "", "")
        assert row["path_per_can"] == ""


def test_experiment_is_reproducible(tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    write_tables(run_experiment(seeds=[2], config=SMALL), first)
    write_tables(run_experiment(seeds=[2], config=SMALL), second)

    for name in ("runs.csv", "timeline.csv", "agents.csv", "events.csv"):
        assert (first / name).read_bytes() == (second / name).read_bytes()


def test_progress_is_reported_once_per_run():
    calls = []
    run_experiment(
        seeds=[0],
        config=SMALL,
        variants=(("random", None),),
        progress=lambda done, total, label: calls.append((done, total, label)),
    )
    assert calls == [(1, 1, "random, seed 0")]


def test_command_line_writes_all_files(tmp_path, capsys):
    output = tmp_path / "nested" / "results"

    main(["--seeds", "2", "--first-seed", "5", "--max-steps", "5", "--output", str(output)])

    runs = _read(output / "runs.csv")
    assert {row["seed"] for row in runs} == {"5", "6"}
    assert {row["max_steps"] for row in runs} == {"5"}
    assert len(runs) == 2 * len(VARIANTS)
    assert (output / "timeline.csv").exists()
    assert (output / "agents.csv").exists()
    assert str(output) in capsys.readouterr().out


@pytest.mark.parametrize("arguments", [["--seeds", "0"], ["--max-steps", "0"]])
def test_command_line_rejects_invalid_counts(arguments, tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        main([*arguments, "--output", str(tmp_path)])
    assert exc.value.code != 0
    assert "positive" in capsys.readouterr().err


def test_experiments_work_without_the_analysis_libraries(tmp_path):
    code = (
        "import sys\n"
        "from kaucjowicze.experiments import main\n"
        f"main(['--seeds', '1', '--max-steps', '2', '--output', {str(tmp_path)!r}])\n"
        "for name in ('pandas', 'matplotlib', 'scipy', 'pygame'):\n"
        "    assert name not in sys.modules, name\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_maps_have_separate_default_directories(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    main(["--seeds", "1", "--max-steps", "2"])
    main(["--seeds", "1", "--max-steps", "2", "--map", "campus"])
    assert (tmp_path / "results" / "test" / "runs.csv").exists()
    assert (tmp_path / "results" / "campus" / "runs.csv").exists()


DYNAMIC = SimulationConfig(
    width=30,
    height=20,
    scenario="dynamic",
    n_clusters=1,
    cans_per_cluster=5,
    n_background_cans=0,
    n_events=2,
    event_start=10,
    event_interval=15,
    n_agents=3,
    max_steps=80,
)


@pytest.fixture(scope="module")
def dynamic_tables():
    return run_experiment(seeds=[0, 1], config=DYNAMIC)


def test_dynamic_runs_record_their_scenario_and_every_party(dynamic_tables):
    assert {row["scenario"] for row in dynamic_tables.runs} == {"dynamic"}
    assert all(row["total_cans"] == 15 for row in dynamic_tables.runs)
    assert all(row["initial_cans"] == 5 for row in dynamic_tables.runs)
    assert all(tuple(row) == EVENTS_COLUMNS for row in dynamic_tables.events)
    assert len(dynamic_tables.events) == 2 * len(dynamic_tables.runs)
    assert {row["spawn_step"] for row in dynamic_tables.events} == {10, 25}


def test_every_variant_gets_the_same_parties_for_a_seed(dynamic_tables):
    seed_of = {row["run_id"]: row["seed"] for row in dynamic_tables.runs}
    parties: dict[int, set] = {}
    for row in dynamic_tables.events:
        key = (row["event_id"], row["spawn_step"], row["x"], row["y"], row["cans"])
        parties.setdefault(seed_of[row["run_id"]], set()).add(key)
    assert all(len(found) == DYNAMIC.n_events for found in parties.values())
    assert parties[0] != parties[1]


def test_dynamic_scenario_has_its_own_default_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    main(["--seeds", "1", "--max-steps", "1100", "--map", "test", "--scenario", "dynamic"])
    output = tmp_path / "results" / "test_dynamic"
    assert len(_read(output / "events.csv")) == 3 * len(VARIANTS)


def test_command_line_rejects_a_limit_before_the_last_party(tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--scenario", "dynamic", "--max-steps", "5", "--output", str(tmp_path)])
    assert exc.value.code != 0
    assert "party" in capsys.readouterr().err


def test_agent_counts_share_seeds_and_number_runs_on():
    labels = []
    tables = run_agent_counts(
        seeds=[0, 1],
        counts=[2, 4],
        config=SMALL,
        progress=lambda done, total, label: labels.append((done, total, label)),
    )

    assert [row["run_id"] for row in tables.runs] == list(range(12))
    assert [row["n_agents"] for row in tables.runs] == [2] * 6 + [4] * 6
    assert {row["seed"] for row in tables.runs} == {0, 1}
    run_ids = {row["run_id"] for row in tables.runs}
    assert {row["run_id"] for row in tables.timeline} == run_ids
    for run in tables.runs:
        agents = [row for row in tables.agents if row["run_id"] == run["run_id"]]
        assert len(agents) == run["n_agents"]
    assert labels[0] == (1, 12, "N = 2, random, seed 0")
    assert labels[-1] == (12, 12, "N = 4, aco/individual, seed 1")


def test_one_agent_count_gives_the_plain_experiment_marked_as_a_sweep():
    swept = run_agent_counts([0, 1], [SMALL.n_agents], SMALL)
    plain = run_experiment([0, 1], SMALL)

    assert all(row["sweep"] is None and row["sweep_value"] is None for row in plain.runs)
    assert [(row["sweep"], row["sweep_value"]) for row in swept.runs] == [
        ("n_agents", SMALL.n_agents)
    ] * len(plain.runs)
    unmarked = [{**row, "sweep": None, "sweep_value": None} for row in swept.runs]
    assert unmarked == plain.runs
    assert (swept.timeline, swept.agents, swept.events) == (
        plain.timeline,
        plain.agents,
        plain.events,
    )


def test_run_ids_can_start_later():
    tables = run_experiment(seeds=[0], config=SMALL, first_run_id=7)
    assert [row["run_id"] for row in tables.runs] == [7, 8, 9]
    assert {row["run_id"] for row in tables.agents} == {7, 8, 9}


def test_several_agent_counts_get_their_own_default_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    main(["--seeds", "1", "--max-steps", "2", "--n-agents", "1", "3"])
    runs = _read(tmp_path / "results" / "test_agents" / "runs.csv")
    assert [row["n_agents"] for row in runs] == ["1"] * 3 + ["3"] * 3
    assert not (tmp_path / "results" / "test").exists()


@pytest.mark.parametrize(("values", "message"), [(["0"], "positive"), (["5", "5"], "repeat")])
def test_command_line_rejects_invalid_agent_counts(values, message, tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--n-agents", *values, "--output", str(tmp_path)])
    assert exc.value.code != 0
    assert message in capsys.readouterr().err


def test_one_count_other_than_the_default_never_replaces_the_default_results(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    main(["--seeds", "1", "--max-steps", "2", "--n-agents", "3"])
    assert (tmp_path / "results" / "test_agents" / "runs.csv").exists()
    assert not (tmp_path / "results" / "test").exists()


def test_layout_is_recorded_and_empty_without_one(tables):
    assert {row["layout"] for row in tables.runs} == {None}
    layout_tables = run_experiment(
        seeds=[0],
        config=SimulationConfig(width=30, height=20, n_agents=3, max_steps=5, layout="uniform"),
    )
    assert {row["layout"] for row in layout_tables.runs} == {"uniform"}
    assert {row["initial_cans"] for row in layout_tables.runs} == {270}


def test_each_layout_gets_its_own_default_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    main(["--seeds", "1", "--max-steps", "2", "--map", "campus", "--layout", "current"])
    runs = _read(tmp_path / "results" / "campus_layout_current" / "runs.csv")
    assert {row["layout"] for row in runs} == {"current"}
    assert not (tmp_path / "results" / "campus").exists()


def test_current_layout_reproduces_the_default_campus_runs():
    config = SimulationConfig(map_name="campus", n_agents=3, max_steps=200)
    default = run_experiment(seeds=[7], config=config)
    current = run_experiment(seeds=[7], config=replace(config, layout="current"))
    without_layout = [{k: v for k, v in row.items() if k != "layout"} for row in current.runs]
    assert without_layout == [
        {k: v for k, v in row.items() if k != "layout"} for row in default.runs
    ]
    assert current.timeline == default.timeline
    assert current.agents == default.agents


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (["--layout", "uniform", "--scenario", "dynamic"], "static"),
        (["--layout", "uniform", "--n-agents", "5"], "default parameters"),
        (["--layout", "uniform", "--sweep", "bag_capacity", "5"], "default parameters"),
        (["--layout", "nope"], "invalid choice"),
    ],
)
def test_command_line_rejects_layout_combinations(arguments, message, tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        main([*arguments, "--output", str(tmp_path)])
    assert exc.value.code != 0
    assert message in capsys.readouterr().err


def test_sweep_changes_only_its_parameter_and_records_it():
    labels = []
    tables = run_sweep(
        seeds=[0, 1],
        parameter="bag_capacity",
        values=[2, 5],
        config=SMALL,
        progress=lambda done, total, label: labels.append((done, total, label)),
    )

    assert [row["k"] for row in tables.runs] == [2] * 6 + [5] * 6
    assert {row["sweep"] for row in tables.runs} == {"bag_capacity"}
    assert [row["sweep_value"] for row in tables.runs] == [2] * 6 + [5] * 6
    assert {row["n_agents"] for row in tables.runs} == {SMALL.n_agents}
    assert labels[0] == (1, 12, "k = 2, random, seed 0")
    assert labels[-1] == (12, 12, "k = 5, aco/individual, seed 1")


def test_sweep_at_the_default_value_reproduces_the_plain_runs():
    swept = run_sweep([0, 1], "vision_radius", [1, SMALL.vision_radius], SMALL)
    plain = run_experiment([0, 1], SMALL)
    at_default = [row for row in swept.runs if row["sweep_value"] == SMALL.vision_radius]
    ids = {row["run_id"] for row in at_default}

    assert [{**row, "run_id": 0, "sweep": None, "sweep_value": None} for row in at_default] == [
        {**row, "run_id": 0} for row in plain.runs
    ]
    timeline = [{**row, "run_id": 0} for row in swept.timeline if row["run_id"] in ids]
    assert timeline == [{**row, "run_id": 0} for row in plain.timeline]


def test_sweep_of_a_trail_parameter_records_its_value_for_every_variant():
    tables = run_sweep([0], "evaporation_rate", [0.01, 0.05], SMALL)
    assert [row["sweep_value"] for row in tables.runs] == [0.01] * 3 + [0.05] * 3
    assert [row["rho"] for row in tables.runs] == [None, 0.01, None, None, 0.05, None]


def test_sweep_rejects_an_unknown_parameter():
    with pytest.raises(ValueError, match="Unknown sweep"):
        run_sweep([0], "max_steps", [5], SMALL)


def test_sweep_gets_its_own_default_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    main(["--seeds", "1", "--max-steps", "2", "--sweep", "bag_capacity", "2", "40"])
    runs = _read(tmp_path / "results" / "test_bag" / "runs.csv")
    assert [row["k"] for row in runs] == ["2"] * 3 + ["40"] * 3
    assert {row["sweep"] for row in runs} == {"bag_capacity"}
    assert not (tmp_path / "results" / "test").exists()


def test_sweep_of_agents_is_the_same_as_n_agents(tmp_path):
    main(
        [
            "--seeds",
            "1",
            "--max-steps",
            "2",
            "--n-agents",
            "1",
            "3",
            "--output",
            str(tmp_path / "a"),
        ]
    )
    main(
        [
            "--seeds",
            "1",
            "--max-steps",
            "2",
            "--sweep",
            "n_agents",
            "1",
            "3",
            "--output",
            str(tmp_path / "b"),
        ]
    )
    for name in ("runs.csv", "timeline.csv", "agents.csv"):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()


def test_sweep_of_a_rate_takes_fractions(tmp_path):
    main(
        [
            "--seeds",
            "1",
            "--max-steps",
            "2",
            "--sweep",
            "exploration_rate",
            "0",
            "0.3",
            "--output",
            str(tmp_path),
        ]
    )
    runs = _read(tmp_path / "runs.csv")
    assert [row["sweep_value"] for row in runs] == ["0.0"] * 3 + ["0.3"] * 3


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (["--sweep", "bag_capacity"], "then its values"),
        (["--sweep", "2", "5"], "then its values"),
        (["--sweep", "nope", "2"], "not a parameter"),
        (["--sweep", "bag_capacity", "2", "vision_radius", "1"], "then its values"),
        (["--sweep", "bag_capacity", "2.5"], "whole numbers"),
        (["--sweep", "bag_capacity", "2", "2"], "repeat"),
        (["--sweep", "bag_capacity", "0"], "Bag capacity"),
        (["--sweep", "exploration_rate", "1.5"], "Exploration rate"),
        (["--sweep", "n_agents", "0"], "positive"),
        (["--sweep", "bag_capacity", "2", "--n-agents", "5"], "cannot be combined"),
    ],
)
def test_command_line_rejects_invalid_sweeps(arguments, message, tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        main([*arguments, "--output", str(tmp_path)])
    assert exc.value.code != 0
    assert message in capsys.readouterr().err
