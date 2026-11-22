"""Run every variant on a shared list of seeds and save the measurements to CSV files.

`python -m kaucjowicze.experiments` writes `runs.csv`, `timeline.csv`, `agents.csv` and
`events.csv` (parties of the dynamic scenario; only a header in the static one). `--sweep`
varies one parameter: every value runs on the same seeds and the files hold all of them (P5 for
the number of agents, P7 to P9 for the others; `--n-agents` is the same as `--sweep n_agents`).
`--layout` picks a named can layout of comparison P6, each written to a directory of its own.
"""

import argparse
import csv
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from kaucjowicze.config import LAYOUTS, MAPS, SCENARIOS, STATIC, SimulationConfig
from kaucjowicze.factory import build_simulation
from kaucjowicze.metrics import RunRecord, record_run
from kaucjowicze.rewards import INDIVIDUAL, SHARED

Variant = tuple[str, str | None]  # algorithm, reward


@dataclass(frozen=True)
class Sweep:
    """A parameter of `SimulationConfig` that a sensitivity sweep varies, one at a time."""

    kind: type  # type of its values on the command line
    symbol: str  # short name in progress messages and reports
    folder: str  # suffix of the default results directory


SWEEPS = {
    "n_agents": Sweep(int, "N", "agents"),
    "bag_capacity": Sweep(int, "k", "bag"),
    "vision_radius": Sweep(int, "r", "vision"),
    "evaporation_rate": Sweep(float, "rho", "rho"),
    "pheromone_alpha": Sweep(float, "alpha", "alpha"),
    "exploration_rate": Sweep(float, "eps", "eps"),
}

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
    "layout",
    "r",
    "sweep",
    "sweep_value",
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
        "layout": config.layout,  # empty: the counts of the map and scenario
        "r": config.vision_radius,
        "sweep": None,  # filled in by `run_sweep`
        "sweep_value": None,
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


def run_sweep(
    seeds: Iterable[int],
    parameter: str,
    values: Sequence[float],
    config: SimulationConfig | None = None,
    variants: Sequence[Variant] = VARIANTS,
    progress: Callable[[int, int, str], None] | None = None,
) -> ExperimentTables:
    """Run the experiment once per value of `parameter`, on the same seeds, in one set of tables.

    Every run row names the parameter (`sweep`) and its value (`sweep_value`), so a report can
    group the runs by value also for parameters that `runs.csv` records only for ACO N1.
    """
    if parameter not in SWEEPS:
        raise ValueError(f"Unknown sweep parameter: {parameter}")
    config = config or SimulationConfig()
    seeds = list(seeds)
    symbol = SWEEPS[parameter].symbol
    total = len(values) * len(seeds) * len(variants)
    tables = ExperimentTables([], [], [], [])
    for value in values:
        first = len(tables.runs)

        def report(done: int, _: int, label: str, value=value, first: int = first) -> None:
            progress(first + done, total, f"{symbol} = {value:g}, {label}")

        part = run_experiment(
            seeds,
            replace(config, **{parameter: value}),
            variants,
            report if progress is not None else None,
            first_run_id=first,
        )
        for row in part.runs:
            row["sweep"] = parameter
            row["sweep_value"] = value
        tables.runs.extend(part.runs)
        tables.timeline.extend(part.timeline)
        tables.agents.extend(part.agents)
        tables.events.extend(part.events)
    return tables


def run_agent_counts(
    seeds: Iterable[int],
    counts: Sequence[int],
    config: SimulationConfig | None = None,
    variants: Sequence[Variant] = VARIANTS,
    progress: Callable[[int, int, str], None] | None = None,
) -> ExperimentTables:
    """The sweep of the number of agents (comparison P5)."""
    return run_sweep(seeds, "n_agents", counts, config, variants, progress)


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


def _sweep_argument(text: str) -> str | float:
    """First word of `--sweep` is a parameter name, the rest are its values."""
    if text in SWEEPS:
        return text
    try:
        return float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a parameter or a number: {text}") from None


def _parse_sweep(
    parser: argparse.ArgumentParser, args: argparse.Namespace, default_agents: int
) -> tuple[str, list] | None:
    """The swept parameter and its values; `None` for a plain run at the defaults."""
    if args.sweep is not None:
        if args.n_agents != [default_agents]:
            parser.error("--sweep and --n-agents cannot be combined, use --sweep n_agents")
        parameter, *values = args.sweep
        if parameter not in SWEEPS or not values or any(v in SWEEPS for v in values):
            parser.error(f"--sweep takes one of {', '.join(SWEEPS)} and then its values")
        kind = SWEEPS[parameter].kind
        if kind is int and any(not float(v).is_integer() for v in values):
            parser.error(f"--sweep {parameter} takes whole numbers")
        values = [kind(v) for v in values]
    elif args.n_agents != [default_agents]:
        parameter, values = "n_agents", args.n_agents
    else:
        return None
    if len(set(values)) != len(values):
        parser.error(f"--sweep {parameter} must not repeat a value")
    if parameter == "n_agents" and min(values) <= 0:
        parser.error("--n-agents must be positive")
    if args.layout is not None:
        parser.error("--layout runs with the default parameters only, not with a sweep")
    return parameter, values


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
        "--sweep",
        type=_sweep_argument,
        nargs="+",
        default=None,
        metavar="PARAMETER VALUE",
        help=f"vary one parameter ({', '.join(SWEEPS)}) over the given values, "
        "e.g. --sweep bag_capacity 2 5 10 20 40",
    )
    parser.add_argument(
        "--layout",
        choices=LAYOUTS,
        default=None,
        help="named can layout of comparison P6, static scenario only (default: the map's own)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="output directory (default: results/<map>, with _dynamic for parties, _agents "
        "for --n-agents other than the default, _<name> for another --sweep and "
        "_layout_<name> for --layout)",
    )
    args = parser.parse_args(argv)
    if args.seeds <= 0:
        parser.error("--seeds must be positive")
    if args.max_steps is not None and args.max_steps <= 0:
        parser.error("--max-steps must be positive")
    sweep = _parse_sweep(parser, args, defaults.n_agents)

    def report(done: int, total: int, label: str) -> None:
        print(f"[{done}/{total}] {label}", flush=True)

    try:
        config = SimulationConfig(
            map_name=args.map, scenario=args.scenario, layout=args.layout, max_steps=args.max_steps
        )
        if sweep is not None:  # every value must make a valid configuration before any run
            for value in sweep[1]:
                replace(config, **{sweep[0]: value})
    except ValueError as error:  # e.g. a step limit that comes before the last party
        parser.error(str(error))
    seeds = range(args.first_seed, args.first_seed + args.seeds)
    folder = args.map if args.scenario == STATIC else f"{args.map}_{args.scenario}"
    # A sweep gets its own directory, so it never replaces the measurement at the defaults
    if sweep is not None:
        folder += f"_{SWEEPS[sweep[0]].folder}"
    if args.layout is not None:  # `current` too, so the default results stay as they are
        folder += f"_layout_{args.layout}"
    output = args.output or Path("results") / folder
    if sweep is None:
        tables = run_experiment(seeds, config, progress=report)
    else:
        tables = run_sweep(seeds, *sweep, config, progress=report)
    write_tables(tables, output)
    print(f"Results written to {output}")


if __name__ == "__main__":
    main()
