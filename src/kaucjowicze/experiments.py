"""Run every variant on a shared list of seeds and save the measurements to CSV files.

`python -m kaucjowicze.experiments` writes `runs.csv`, `timeline.csv` and `agents.csv`.
"""

import argparse
import csv
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from kaucjowicze.config import MAPS, SimulationConfig
from kaucjowicze.factory import build_simulation
from kaucjowicze.metrics import RunRecord, record_run
from kaucjowicze.rewards import INDIVIDUAL, SHARED

Variant = tuple[str, str | None]  # algorithm, reward

VARIANTS: tuple[Variant, ...] = (("random", None), ("aco", SHARED), ("aco", INDIVIDUAL))
SCENARIO = "static"

RUNS_COLUMNS = (
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
TIMELINE_COLUMNS = (
    "run_id",
    "step",
    "cans_collected",
    "cans_on_map",
    "agents_searching",
    "agents_carrying",
)
AGENTS_COLUMNS = ("run_id", "agent_id", "cans", "path_length", "trips")


@dataclass(frozen=True)
class ExperimentTables:
    """Rows of the three CSV files; `None` stands for an empty value."""

    runs: list[dict]
    timeline: list[dict]
    agents: list[dict]


def _run_row(
    run_id: int, seed: int, variant: Variant, config: SimulationConfig, record: RunRecord
) -> dict:
    algorithm, reward = variant
    follows_trails = algorithm == "aco" and reward == SHARED
    return {
        "run_id": run_id,
        "seed": seed,
        "algorithm": algorithm,
        "reward": reward,
        "scenario": SCENARIO,
        "map": config.map_name,
        "n_agents": config.n_agents,
        "k": config.bag_capacity,
        "rho": config.evaporation_rate if follows_trails else None,
        "alpha": config.pheromone_alpha if follows_trails else None,
        "beta": None,  # the direction choice has no heuristic term
        "eps": config.exploration_rate if follows_trails else None,
        "max_steps": config.max_steps,
        "initial_cans": record.initial_cans,
        "steps": record.steps,
        "t_50": record.t_50,
        "t_90": record.t_90,
        "t_100": record.t_100,
        "cans_at_T": record.cans_collected,
        "total_path_length": record.total_path_length,
        "path_per_can": record.path_per_can,
        "trips": record.trips,
        "gini": record.gini,
        "cans_min": record.cans_min,
        "cans_max": record.cans_max,
        "J": None,  # objective C: its weights are not decided yet
    }


def _variant_label(variant: Variant) -> str:
    algorithm, reward = variant
    return algorithm if reward is None else f"{algorithm}/{reward}"


def run_experiment(
    seeds: Iterable[int],
    config: SimulationConfig | None = None,
    variants: Sequence[Variant] = VARIANTS,
    progress: Callable[[int, int, str], None] | None = None,
) -> ExperimentTables:
    """Run each variant on each seed. `progress` gets (runs done, all runs, finished run)."""
    config = config or SimulationConfig()
    seeds = list(seeds)
    # ACO without a reward runs the shared one, so that is what the results have to say
    variants = [(a, SHARED if a == "aco" and r is None else r) for a, r in variants]
    total = len(seeds) * len(variants)
    tables = ExperimentTables([], [], [])
    for run_id, (seed, variant) in enumerate((s, v) for s in seeds for v in variants):
        algorithm, reward = variant
        record = record_run(build_simulation(algorithm, seed, reward, config))
        tables.runs.append(_run_row(run_id, seed, variant, config, record))
        tables.timeline.extend(
            {
                "run_id": run_id,
                "step": row.step,
                "cans_collected": row.cans_collected,
                "cans_on_map": row.cans_on_map,
                "agents_searching": row.agents_searching,
                "agents_carrying": row.agents_carrying,
            }
            for row in record.timeline
        )
        tables.agents.extend(
            {
                "run_id": run_id,
                "agent_id": agent.agent_id,
                "cans": agent.cans,
                "path_length": agent.path_length,
                "trips": agent.trips,
            }
            for agent in record.agents
        )
        if progress is not None:
            progress(run_id + 1, total, f"{_variant_label(variant)}, seed {seed}")
    return tables


def _write_csv(path: Path, columns: Sequence[str], rows: Iterable[dict]) -> None:
    # A fixed line ending makes the files byte-identical on every system
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_tables(tables: ExperimentTables, output_dir: str | Path) -> None:
    """Write the CSV files to `output_dir`, replacing earlier ones."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "runs.csv", RUNS_COLUMNS, tables.runs)
    _write_csv(output / "timeline.csv", TIMELINE_COLUMNS, tables.timeline)
    _write_csv(output / "agents.csv", AGENTS_COLUMNS, tables.agents)


def main(argv: list[str] | None = None) -> None:
    defaults = SimulationConfig()
    parser = argparse.ArgumentParser(description="Compare the variants on a shared list of seeds")
    parser.add_argument("--seeds", type=int, default=30, help="number of seeds (maps)")
    parser.add_argument("--first-seed", type=int, default=0, help="first seed of the list")
    parser.add_argument("--max-steps", type=int, default=None, help="step limit T")
    parser.add_argument("--map", choices=MAPS, default=defaults.map_name, help="map to run on")
    parser.add_argument("--output", type=Path, default=Path("results"), help="output directory")
    args = parser.parse_args(argv)
    if args.seeds <= 0:
        parser.error("--seeds must be positive")
    if args.max_steps is not None and args.max_steps <= 0:
        parser.error("--max-steps must be positive")

    def report(done: int, total: int, label: str) -> None:
        print(f"[{done}/{total}] {label}", flush=True)

    config = SimulationConfig(map_name=args.map, max_steps=args.max_steps)
    seeds = range(args.first_seed, args.first_seed + args.seeds)
    write_tables(run_experiment(seeds, config, progress=report), args.output)
    print(f"Results written to {args.output}")


if __name__ == "__main__":
    main()
