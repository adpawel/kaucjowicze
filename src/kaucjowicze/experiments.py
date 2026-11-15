"""Run every variant on a shared list of seeds and save the measurements to CSV files.

`python -m kaucjowicze.experiments` writes `runs.csv`, `timeline.csv`, `agents.csv` and
`events.csv` (parties of the dynamic scenario; only a header in the static one). With several
`--n-agents` values every count runs on the same seeds and the files hold all of them (P5).
"""

import argparse
import csv
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from kaucjowicze.config import MAPS, SCENARIOS, STATIC, SimulationConfig
from kaucjowicze.factory import build_simulation
from kaucjowicze.metrics import RunRecord, record_run
from kaucjowicze.rewards import INDIVIDUAL, SHARED

Variant = tuple[str, str | None]  # algorithm, reward

VARIANTS: tuple[Variant, ...] = (("random", None), ("aco", SHARED), ("aco", INDIVIDUAL))

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
    "total_cans",
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
EVENTS_COLUMNS = (
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


@dataclass(frozen=True)
class ExperimentTables:
    """Rows of the CSV files; `None` stands for an empty value."""

    runs: list[dict]
    timeline: list[dict]
    agents: list[dict]
    events: list[dict]


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
        "scenario": config.scenario,
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
        "total_cans": record.total_cans,
    }


def _variant_label(variant: Variant) -> str:
    algorithm, reward = variant
    return algorithm if reward is None else f"{algorithm}/{reward}"


def run_experiment(
    seeds: Iterable[int],
    config: SimulationConfig | None = None,
    variants: Sequence[Variant] = VARIANTS,
    progress: Callable[[int, int, str], None] | None = None,
    first_run_id: int = 0,
) -> ExperimentTables:
    """Run each variant on each seed. `progress` gets (runs done, all runs, finished run).

    Run ids start at `first_run_id`, so tables of several calls can be joined.
    """
    config = config or SimulationConfig()
    seeds = list(seeds)
    # ACO without a reward runs the shared one, so that is what the results have to say
    variants = [(a, SHARED if a == "aco" and r is None else r) for a, r in variants]
    total = len(seeds) * len(variants)
    tables = ExperimentTables([], [], [], [])
    pairs = ((s, v) for s in seeds for v in variants)
    for run_id, (seed, variant) in enumerate(pairs, start=first_run_id):
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
        tables.events.extend(
            {
                "run_id": run_id,
                "event_id": event.event_id,
                "spawn_step": event.spawn_step,
                "x": event.x,
                "y": event.y,
                "cans": event.cans,
                "overlap_share": event.overlap_share,
                "latency_first": event.latency_first,
                "latency_50": event.latency_50,
                "latency_90": event.latency_90,
                "picked_up": event.picked_up,
                "agents_visited": event.agents_visited,
            }
            for event in record.events
        )
        if progress is not None:
            done = run_id - first_run_id + 1
            progress(done, total, f"{_variant_label(variant)}, seed {seed}")
    return tables


def run_agent_counts(
    seeds: Iterable[int],
    counts: Sequence[int],
    config: SimulationConfig | None = None,
    variants: Sequence[Variant] = VARIANTS,
    progress: Callable[[int, int, str], None] | None = None,
) -> ExperimentTables:
    """Run the experiment once per number of agents, on the same seeds, in one set of tables."""
    config = config or SimulationConfig()
    seeds = list(seeds)
    total = len(counts) * len(seeds) * len(variants)
    tables = ExperimentTables([], [], [], [])
    for count in counts:
        first = len(tables.runs)

        def report(done: int, _: int, label: str, count: int = count, first: int = first) -> None:
            progress(first + done, total, f"N = {count}, {label}")

        part = run_experiment(
            seeds,
            replace(config, n_agents=count),
            variants,
            report if progress is not None else None,
            first_run_id=first,
        )
        tables.runs.extend(part.runs)
        tables.timeline.extend(part.timeline)
        tables.agents.extend(part.agents)
        tables.events.extend(part.events)
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
    _write_csv(output / "events.csv", EVENTS_COLUMNS, tables.events)


def main(argv: list[str] | None = None) -> None:
    defaults = SimulationConfig()
    parser = argparse.ArgumentParser(description="Compare the variants on a shared list of seeds")
    parser.add_argument("--seeds", type=int, default=30, help="number of seeds (maps)")
    parser.add_argument("--first-seed", type=int, default=0, help="first seed of the list")
    parser.add_argument("--max-steps", type=int, default=None, help="step limit T")
    parser.add_argument("--map", choices=MAPS, default=defaults.map_name, help="map to run on")
    parser.add_argument(
        "--scenario", choices=SCENARIOS, default=STATIC, help="static cans or parties during a run"
    )
    parser.add_argument(
        "--n-agents",
        type=int,
        nargs="+",
        default=[defaults.n_agents],
        help="number of agents; several values run each of them (default: %(default)s)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="output directory (default: results/<map>, with _dynamic for parties and _agents "
        "for --n-agents other than the default)",
    )
    args = parser.parse_args(argv)
    if args.seeds <= 0:
        parser.error("--seeds must be positive")
    if args.max_steps is not None and args.max_steps <= 0:
        parser.error("--max-steps must be positive")
    if min(args.n_agents) <= 0:
        parser.error("--n-agents must be positive")
    if len(set(args.n_agents)) != len(args.n_agents):
        parser.error("--n-agents must not repeat a value")

    def report(done: int, total: int, label: str) -> None:
        print(f"[{done}/{total}] {label}", flush=True)

    try:
        config = SimulationConfig(
            map_name=args.map, scenario=args.scenario, max_steps=args.max_steps
        )
    except ValueError as error:  # e.g. a step limit that comes before the last party
        parser.error(str(error))
    seeds = range(args.first_seed, args.first_seed + args.seeds)
    folder = args.map if args.scenario == STATIC else f"{args.map}_{args.scenario}"
    # Any other count gets its own directory, so it never replaces the measurement at the default
    if args.n_agents != [defaults.n_agents]:
        folder += "_agents"
    output = args.output or Path("results") / folder
    write_tables(run_agent_counts(seeds, args.n_agents, config, progress=report), output)
    print(f"Results written to {output}")


if __name__ == "__main__":
    main()
