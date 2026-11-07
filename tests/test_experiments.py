import csv
import subprocess
import sys

import pytest

from kaucjowicze.config import SimulationConfig
from kaucjowicze.experiments import (
    AGENTS_COLUMNS,
    RUNS_COLUMNS,
    TIMELINE_COLUMNS,
    VARIANTS,
    main,
    run_experiment,
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


def test_rows_have_exactly_the_documented_columns(tables):
    assert all(tuple(row) == RUNS_COLUMNS for row in tables.runs)
    assert all(tuple(row) == TIMELINE_COLUMNS for row in tables.timeline)
    assert all(tuple(row) == AGENTS_COLUMNS for row in tables.agents)


def test_config_values_are_recorded(tables):
    row = tables.runs[0]
    assert row["scenario"] == "static"
    assert row["n_agents"] == SMALL.n_agents
    assert row["k"] == SMALL.bag_capacity
    assert row["max_steps"] == SMALL.max_steps
    assert row["initial_cans"] == 12


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


def test_columns_without_a_definition_yet_stay_empty(tables):
    assert all(row["beta"] is None and row["J"] is None for row in tables.runs)


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
    assert random_run["J"] == ""


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

    for name in ("runs.csv", "timeline.csv", "agents.csv"):
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
