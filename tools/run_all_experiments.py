"""Run every experiment of the project and make every report, one command for all results.

Experiments are independent, so `--jobs` runs several at once; reports come after all of them,
because P6 joins four directories. `--dry-run` only prints the commands. Results go to
`results/`, as with the single commands in README.md and ZMIANY_ZAJECIA3.md.

    python tools/run_all_experiments.py --jobs 4
"""

import argparse
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

CAMPUS = ["--seeds", "30", "--first-seed", "200", "--map", "campus"]
TEST = ["--seeds", "30"]
LAYOUTS = ("few-large", "current", "many-small", "uniform")
TRAILS = ["--trails", "speed", "equal+", "equal-"]

# (comparison, arguments of kaucjowicze.experiments)
EXPERIMENTS = [
    ("P1, P2 (test map)", TEST),
    ("P1, P2", CAMPUS),
    ("P3", [*CAMPUS, *TRAILS]),
    ("P3 (test map)", [*TEST, *TRAILS]),
    ("P4", [*CAMPUS, "--scenario", "dynamic"]),
    ("P5", [*CAMPUS, "--n-agents", "5", "10", "20", "40", "80"]),
    *((f"P6 {name}", [*CAMPUS, "--layout", name]) for name in LAYOUTS),
    ("P7", [*CAMPUS, "--sweep", "bag_capacity", "2", "5", "10", "20", "40"]),
    ("P8", [*CAMPUS, "--sweep", "vision_radius", "1", "2", "4", "8"]),
    ("P9 rho", [*CAMPUS, "--sweep", "evaporation_rate", "0.005", "0.01", "0.02", "0.05"]),
    ("P9 alpha", [*CAMPUS, "--sweep", "pheromone_alpha", "0.5", "1", "2", "4"]),
    ("P9 eps", [*CAMPUS, "--sweep", "exploration_rate", "0", "0.05", "0.1", "0.3"]),
    ("P10", [*CAMPUS, "--sweep", "egoist_share", "0", "0.25", "0.5", "0.75", "1"]),
    ("P11", [*CAMPUS, "--sweep", "pheromone_max", "0.1", "0.5", "2", "10", "inf"]),
]

# arguments of kaucjowicze.plots
REPORTS = [
    ["--input", "results/test"],
    ["--input", "results/campus"],
    ["--input", "results/campus_trails"],
    ["--input", "results/test_trails"],
    ["--input", "results/campus_dynamic"],
    ["--input", "results/campus_agents"],
    [
        "--input",
        *(f"results/campus_layout_{name}" for name in LAYOUTS),
        "--output",
        "results/campus_layouts",
    ],
    *(
        ["--input", f"results/campus_{name}"]
        for name in ("bag", "vision", "rho", "alpha", "eps", "mixed", "maxmin")
    ),
]


def commands() -> tuple[list[list[str]], list[list[str]]]:
    python = [sys.executable, "-m"]
    experiments = [[*python, "kaucjowicze.experiments", *args] for _, args in EXPERIMENTS]
    reports = [[*python, "kaucjowicze.plots", *args] for args in REPORTS]
    return experiments, reports


def _run(command: list[str]) -> int:
    print("$ python -m", " ".join(command[2:]), flush=True)
    return subprocess.run(command, stdout=subprocess.DEVNULL).returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--jobs", type=int, default=1, help="experiments run at once")
    parser.add_argument("--dry-run", action="store_true", help="only print the commands")
    args = parser.parse_args(argv)
    if args.jobs <= 0:
        parser.error("--jobs must be positive")
    experiments, reports = commands()
    if args.dry_run:
        for command in experiments + reports:
            print(" ".join(command[2:]))
        return 0
    with ThreadPoolExecutor(args.jobs) as pool:
        codes = list(pool.map(_run, experiments))
    failed = [c for c, code in zip(experiments, codes, strict=True) if code]
    if failed:
        print(f"{len(failed)} experiments failed, no reports made", file=sys.stderr)
        return 1
    failed = [command for command in reports if _run(command)]
    if failed:
        print(f"{len(failed)} reports failed", file=sys.stderr)
        return 1
    print("All results and reports are in results/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
