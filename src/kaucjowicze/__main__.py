"""Entry point: `python -m kaucjowicze` builds a map, scatters cans and prints it."""

import argparse

import numpy as np

from kaucjowicze.cans import scatter_cans
from kaucjowicze.config import SimulationConfig
from kaucjowicze.maps import build_test_map


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Kaucjowicze: ACO can-collection simulation")
    parser.add_argument("--seed", type=int, default=None, help="random seed")
    args = parser.parse_args(argv)

    config = SimulationConfig(seed=args.seed)
    rng = np.random.default_rng(config.seed)

    grid = build_test_map(config)
    scatter_cans(grid, config, rng)

    print(grid.render_ascii())
    print(f"\nMap: {grid.width}x{grid.height}, bases: {grid.bases}, cans: {grid.total_cans}")


if __name__ == "__main__":
    main()
