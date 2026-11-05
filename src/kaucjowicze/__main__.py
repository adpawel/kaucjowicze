"""Entry point: `python -m kaucjowicze` runs a simulation, headless or in a window (`--gui`)."""

import argparse
from collections.abc import Callable

import numpy as np

from kaucjowicze.cans import scatter_cans
from kaucjowicze.config import SimulationConfig
from kaucjowicze.maps import build_test_map
from kaucjowicze.pathfinding import distance_map
from kaucjowicze.policies import AcoPolicy, IndividualPolicy, RandomWalkPolicy
from kaucjowicze.rewards import INDIVIDUAL, REWARDS, SHARED, agent_rewards
from kaucjowicze.simulation import Simulation

ALGORITHMS = ("random", "aco")


def build_simulation(algorithm: str, seed: int | None, reward: str | None = None) -> Simulation:
    """A fresh simulation; the same arguments and an integer seed give an identical run.

    `reward` picks the variant of ACO, by default the shared one. The random walk has none.
    """
    config = SimulationConfig(seed=seed)
    rng = np.random.default_rng(config.seed)
    grid = build_test_map(config)
    scatter_cans(grid, config, rng)
    if algorithm == "random":
        if reward is not None:
            raise ValueError("The random walk does not use a reward")
        return Simulation(config, grid, RandomWalkPolicy(config.direction_persistence), rng)
    if algorithm == "aco":
        if reward in (None, SHARED):
            pheromone = np.zeros((grid.height, grid.width))
            policy = AcoPolicy(config, pheromone, distance_map(grid))
            return Simulation(config, grid, policy, rng, pheromone=pheromone)
        if reward == INDIVIDUAL:  # egoists leave no trail, so there is no pheromone at all
            return Simulation(config, grid, IndividualPolicy(config), rng)
        raise ValueError(f"Unknown reward: {reward}")
    raise ValueError(f"Unknown algorithm: {algorithm}")


def _load_run_gui(parser: argparse.ArgumentParser) -> Callable[..., None]:
    """Import the window lazily: headless runs and CI work without pygame."""
    try:
        from kaucjowicze.gui import run_gui
    except ModuleNotFoundError as exc:
        if exc.name != "pygame":
            raise
        parser.error('--gui requires pygame, install it with: pip install -e ".[gui]"')
    return run_gui


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Kaucjowicze: ACO can-collection simulation")
    parser.add_argument("--seed", type=int, default=None, help="random seed")
    parser.add_argument(
        "--algorithm", choices=ALGORITHMS, default="random", help="movement policy of agents"
    )
    parser.add_argument(
        "--reward", choices=REWARDS, default=None, help="reward of ACO agents (default: shared)"
    )
    parser.add_argument("--show-map", action="store_true", help="print the map before the run")
    parser.add_argument("--gui", action="store_true", help="show the simulation in a window")
    args = parser.parse_args(argv)

    if args.algorithm == "random" and args.reward is not None:
        parser.error("--reward applies only to --algorithm aco")
    reward = SHARED if args.algorithm == "aco" and args.reward is None else args.reward
    variant = args.algorithm if reward is None else f"{args.algorithm}/{reward}"

    seed = args.seed
    run_gui = None
    if args.gui:
        run_gui = _load_run_gui(parser)
        if seed is None:  # restart has to reproduce the same map, so the seed must be known
            seed = int(np.random.default_rng().integers(2**31))

    sim = build_simulation(args.algorithm, seed, reward)
    grid = sim.grid
    if args.show_map:
        print(grid.render_ascii())
        print()

    if run_gui is not None:
        run_gui(lambda: build_simulation(args.algorithm, seed, reward), variant, seed)
        return

    sim.run()

    per_agent = [agent.cans_collected for agent in sim.agents]
    reward_label = "" if reward is None else f", reward: {reward}"
    print(f"Algorithm: {args.algorithm}{reward_label}, seed: {args.seed}")
    print(f"Map: {grid.width}x{grid.height}, bases: {grid.bases}, agents: {len(sim.agents)}")
    print(f"Steps: {sim.step_count} (limit {sim.config.max_steps})")
    print(f"Collected: {sim.collected}/{sim.initial_cans} cans")
    print(f"Trips: {sum(agent.trips for agent in sim.agents)}")
    print(f"Path length: {sum(agent.path_length for agent in sim.agents)}")
    if per_agent:
        print(f"Cans per agent: min {min(per_agent)}, max {max(per_agent)}")
    if reward is not None and per_agent:
        rewards = agent_rewards(sim.agents, reward)
        print(f"Reward per agent: min {min(rewards):g}, max {max(rewards):g}")


if __name__ == "__main__":
    main()
