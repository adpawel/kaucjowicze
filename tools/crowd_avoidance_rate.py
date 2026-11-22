"""How often crowd avoidance of ACO N1 acts: the share of trail decisions with a crowded direction.

A descriptive check of the limitation in ALGORITHM.md, point 10 (0.44% of trail decisions on the
test map), for several numbers of agents. Counting only reads the policy, so runs do not change.

    python tools/crowd_avoidance_rate.py --map campus --n-agents 20 40 80
"""

import argparse
from dataclasses import replace

from kaucjowicze.config import MAPS, SimulationConfig
from kaucjowicze.factory import build_simulation


def crowd_rate(config: SimulationConfig, seeds) -> tuple[int, int]:
    """(crowded decisions, trail decisions) of ACO N1 summed over `seeds`."""
    crowded = decisions = 0
    for seed in seeds:
        sim = build_simulation("aco", seed, config=config)
        sim.run()
        crowded += sim.policy.crowded_decisions
        decisions += sim.policy.trail_decisions
    return crowded, decisions


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--map", choices=MAPS, default="campus")
    parser.add_argument("--n-agents", type=int, nargs="+", default=[20])
    parser.add_argument("--seeds", type=int, default=30)
    parser.add_argument("--first-seed", type=int, default=200)
    args = parser.parse_args(argv)
    seeds = range(args.first_seed, args.first_seed + args.seeds)
    print("| N | Crowded decisions | Trail decisions | Share | Crowded per run |")
    print("|---|---|---|---|---|")
    for n_agents in args.n_agents:
        config = replace(SimulationConfig(map_name=args.map), n_agents=n_agents)
        crowded, decisions = crowd_rate(config, seeds)
        share = crowded / decisions if decisions else 0.0
        print(
            f"| {n_agents} | {crowded} | {decisions} | {100 * share:.2f}% "
            f"| {crowded / len(seeds):.1f} |"
        )


if __name__ == "__main__":
    main()
