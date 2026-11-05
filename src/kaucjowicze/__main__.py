"""Entry point: `python -m kaucjowicze` runs a headless simulation and prints a summary."""

import argparse

import numpy as np

from kaucjowicze.cans import scatter_cans
from kaucjowicze.config import SimulationConfig
from kaucjowicze.maps import build_test_map
from kaucjowicze.policies import MovementPolicy, RandomWalkPolicy
from kaucjowicze.simulation import Simulation

ALGORITHMS = ("random",)


def build_policy(algorithm: str, config: SimulationConfig) -> MovementPolicy:
    if algorithm == "random":
        return RandomWalkPolicy(config.direction_persistence)
    raise ValueError(f"Unknown algorithm: {algorithm}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Kaucjowicze: ACO can-collection simulation")
    parser.add_argument("--seed", type=int, default=None, help="random seed")
    parser.add_argument(
        "--algorithm", choices=ALGORITHMS, default="random", help="movement policy of agents"
    )
    parser.add_argument("--show-map", action="store_true", help="print the map before the run")
    args = parser.parse_args(argv)

    config = SimulationConfig(seed=args.seed)
    rng = np.random.default_rng(config.seed)

    grid = build_test_map(config)
    scatter_cans(grid, config, rng)
    if args.show_map:
        print(grid.render_ascii())
        print()

    sim = Simulation(config, grid, build_policy(args.algorithm, config), rng)
    sim.run()

    per_agent = [agent.cans_collected for agent in sim.agents]
    print(f"Algorithm: {args.algorithm}, seed: {args.seed}")
    print(f"Map: {grid.width}x{grid.height}, bases: {grid.bases}, agents: {len(sim.agents)}")
    print(f"Steps: {sim.step_count} (limit {config.max_steps})")
    print(f"Collected: {sim.collected}/{sim.initial_cans} cans")
    print(f"Trips: {sum(agent.trips for agent in sim.agents)}")
    print(f"Path length: {sum(agent.path_length for agent in sim.agents)}")
    if per_agent:
        print(f"Cans per agent: min {min(per_agent)}, max {max(per_agent)}")


if __name__ == "__main__":
    main()
