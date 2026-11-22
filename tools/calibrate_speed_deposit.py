"""Calibrate q_s, the strength of the `speed` trail signal (ALGORITHM.md, point 20).

`speed` lays q_s * b / L per cell and `source` lays q * n, which are of a very different size. So
that comparison P3 measures the objective and not the strength of the trail, q_s is chosen to make
the mean trail per cell left by a carrying agent equal to that of `source`. Cells where nothing is
laid (an exhausted source) count as zero in both.

The trail laid depends on how the colony moves, which depends on q_s, so q_s is rescaled and the
runs repeated until the mean matches within the tolerance. Calibration uses seeds of its own
(100-109 by default), never those of a measurement.

    python tools/calibrate_speed_deposit.py --map campus
"""

import argparse
from collections.abc import Sequence
from dataclasses import replace

from kaucjowicze.config import MAPS, TRAILS, SimulationConfig
from kaucjowicze.factory import build_simulation


def mean_trail(config: SimulationConfig, seeds: Sequence[int]) -> float:
    """Trail laid per cell left by a carrying agent, over all runs of ACO N1 on `seeds`."""
    laid = steps = 0.0
    for seed in seeds:
        sim = build_simulation("aco", seed, config=config)
        sim.run()
        laid += sim.trail_laid
        steps += sim.trail_steps
    return laid / steps


def calibrate(
    config: SimulationConfig,
    seeds: Sequence[int],
    tolerance: float = 0.02,
    max_rounds: int = 10,
    report=None,
) -> tuple[float, float, float]:
    """q_s with the mean `speed` trail within `tolerance` of the `source` one.

    Returns (q_s, mean trail of `speed`, mean trail of `source`).
    """
    target = mean_trail(replace(config, **TRAILS["source"]), seeds)
    speed = replace(config, **TRAILS["speed"])
    q_s = 1.0
    for round_ in range(1, max_rounds + 1):
        mean = mean_trail(replace(speed, speed_deposit=q_s), seeds)
        if report is not None:
            report(round_, q_s, mean, target)
        if abs(mean / target - 1) <= tolerance:
            return q_s, mean, target
        q_s *= target / mean
    raise RuntimeError(f"q_s did not settle in {max_rounds} rounds")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--map", choices=MAPS, default="campus", help="map to calibrate on")
    parser.add_argument("--seeds", type=int, default=10, help="number of calibration seeds")
    parser.add_argument("--first-seed", type=int, default=100, help="first calibration seed")
    parser.add_argument("--tolerance", type=float, default=0.02, help="relative tolerance")
    args = parser.parse_args(argv)
    seeds = range(args.first_seed, args.first_seed + args.seeds)

    def report(round_: int, q_s: float, mean: float, target: float) -> None:
        print(f"round {round_}: q_s = {q_s:.4g}, trail per cell {mean:.4g} (source {target:.4g})")

    q_s, _, _ = calibrate(SimulationConfig(map_name=args.map), seeds, args.tolerance, report=report)
    print(f"q_s = {q_s:.3g} on the {args.map} map, seeds {seeds.start}-{seeds.stop - 1}")


if __name__ == "__main__":
    main()
