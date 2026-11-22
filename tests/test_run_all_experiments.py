import importlib.util
from pathlib import Path

import pytest

from kaucjowicze.experiments import main as experiments_main

_PATH = Path(__file__).resolve().parents[1] / "tools" / "run_all_experiments.py"
_SPEC = importlib.util.spec_from_file_location("run_all_experiments", _PATH)
tool = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(tool)


def test_every_comparison_is_run():
    names = " ".join(name for name, _ in tool.EXPERIMENTS)
    for comparison in ("P1", "P3", "P4", "P5", "P6", "P7", "P8", "P9", "P10", "P11"):
        assert comparison in names


def test_dry_run_prints_every_command(capsys):
    assert tool.main(["--dry-run"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == len(tool.EXPERIMENTS) + len(tool.REPORTS)
    assert lines[0].startswith("kaucjowicze.experiments")
    assert lines[-1].startswith("kaucjowicze.plots")


@pytest.mark.parametrize(("name", "args"), tool.EXPERIMENTS)
def test_every_experiment_command_is_accepted(name, args, tmp_path):
    # a tiny run with the same options checks that the options exist and fit together
    small = [*args[: args.index("--seeds")], *args[args.index("--seeds") + 2 :]]
    limit = "3001" if "dynamic" in args else "1"  # the last party of the campus comes at 3000
    experiments_main([*small, "--seeds", "1", "--max-steps", limit, "--output", str(tmp_path)])
    assert (tmp_path / "runs.csv").exists()
