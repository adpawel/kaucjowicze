"""Entry point: `python -m kaucjowicze` runs a simulation, headless or in a window (`--gui`)."""

import argparse
from collections.abc import Callable

import numpy as np

from kaucjowicze.config import (
    LAYOUTS,
    MAPS,
    SCENARIOS,
    SOURCE,
    STATIC,
    TEST_MAP,
    TRAILS,
    SimulationConfig,
)
from kaucjowicze.factory import ALGORITHMS, build_simulation
from kaucjowicze.rewards import REWARDS, SHARED, agent_rewards


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
    parser.add_argument(
        "--trail",
        choices=TRAILS,
        default=SOURCE,
        help="trail signal of ACO with the shared reward (default: %(default)s)",
    )
    parser.add_argument("--map", choices=MAPS, default=TEST_MAP, help="map to run on")
    parser.add_argument(
        "--scenario", choices=SCENARIOS, default=STATIC, help="static cans or parties during a run"
    )
    parser.add_argument(
        "--layout",
        choices=LAYOUTS,
        default=None,
        help="named can layout, static scenario only (default: the map's own)",
    )
    parser.add_argument("--show-map", action="store_true", help="print the map before the run")
    parser.add_argument("--gui", action="store_true", help="show the simulation in a window")
    args = parser.parse_args(argv)

    if args.algorithm == "random" and args.reward is not None:
        parser.error("--reward applies only to --algorithm aco")
    reward = SHARED if args.algorithm == "aco" and args.reward is None else args.reward
    if args.trail != SOURCE and reward != SHARED:
        parser.error("--trail applies only to --algorithm aco with the shared reward")
    variant = args.algorithm if reward is None else f"{args.algorithm}/{reward}"
    if args.trail != SOURCE:
        variant += f"/{args.trail}"

    seed = args.seed
    run_gui = None
    if args.gui:
        run_gui = _load_run_gui(parser)
        if seed is None:  # restart has to reproduce the same map, so the seed must be known
            seed = int(np.random.default_rng().integers(2**31))

    try:
        config = SimulationConfig(
            map_name=args.map, scenario=args.scenario, layout=args.layout, **TRAILS[args.trail]
        )
    except ValueError as error:  # a layout with parties
        parser.error(str(error))
    sim = build_simulation(args.algorithm, seed, reward, config)
    grid = sim.grid
    if args.show_map:
        print(grid.render_ascii())
        print()

    if run_gui is not None:
        run_gui(lambda: build_simulation(args.algorithm, seed, reward, config), variant, seed)
        return

    sim.run()

    per_agent = [agent.cans_collected for agent in sim.agents]
    reward_label = "" if reward is None else f", reward: {reward}"
    if args.trail != SOURCE:
        reward_label += f", trail: {args.trail}"
    print(f"Algorithm: {args.algorithm}{reward_label}, seed: {args.seed}")
    print(f"Map: {grid.width}x{grid.height}, bases: {grid.bases}, agents: {len(sim.agents)}")
    print(f"Steps: {sim.step_count} (limit {sim.config.max_steps})")
    print(f"Collected: {sim.collected}/{sim.total_cans} cans")
    print(f"Trips: {sum(agent.trips for agent in sim.agents)}")
    print(f"Path length: {sum(agent.path_length for agent in sim.agents)}")
    if per_agent:
        print(f"Cans per agent: min {min(per_agent)}, max {max(per_agent)}")
    if reward is not None and per_agent:
        rewards = agent_rewards(sim.agents, reward)
        print(f"Reward per agent: min {min(rewards):g}, max {max(rewards):g}")


if __name__ == "__main__":
    main()
