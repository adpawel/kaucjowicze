import subprocess
import sys
import types

import pytest

from kaucjowicze.__main__ import build_simulation, main


def _fake_gui(monkeypatch) -> list[dict]:
    """Replace the pygame window with a recorder, so these tests need no pygame."""
    calls = []

    def run_gui(make_sim, variant, seed):
        calls.append({"make_sim": make_sim, "variant": variant, "seed": seed})

    module = types.ModuleType("kaucjowicze.gui")
    module.run_gui = run_gui
    monkeypatch.setitem(sys.modules, "kaucjowicze.gui", module)
    return calls


def test_build_simulation_is_deterministic():
    a = build_simulation("random", seed=3)
    b = build_simulation("random", seed=3)
    assert (a.grid.cans == b.grid.cans).all()
    for _ in range(50):
        a.step()
        b.step()
    assert [agent.pos for agent in a.agents] == [agent.pos for agent in b.agents]


def test_build_simulation_rejects_unknown_algorithm():
    with pytest.raises(ValueError, match="Unknown algorithm"):
        build_simulation("nope", seed=0)


def test_gui_flag_opens_window_instead_of_running(monkeypatch, capsys):
    calls = _fake_gui(monkeypatch)

    main(["--algorithm", "random", "--seed", "5", "--gui"])

    assert len(calls) == 1
    assert calls[0]["variant"] == "random"
    assert calls[0]["seed"] == 5
    assert calls[0]["make_sim"]().step_count == 0
    assert "Collected" not in capsys.readouterr().out


def test_restart_factory_recreates_the_same_map(monkeypatch):
    calls = _fake_gui(monkeypatch)
    main(["--seed", "5", "--gui"])
    make_sim = calls[0]["make_sim"]
    assert (make_sim().grid.cans == make_sim().grid.cans).all()


def test_gui_without_seed_uses_one_concrete_seed(monkeypatch):
    calls = _fake_gui(monkeypatch)

    main(["--gui"])

    assert isinstance(calls[0]["seed"], int)
    make_sim = calls[0]["make_sim"]
    assert (make_sim().grid.cans == make_sim().grid.cans).all()


def test_gui_without_pygame_explains_how_to_install(monkeypatch, capsys):
    monkeypatch.delitem(sys.modules, "kaucjowicze.gui", raising=False)
    monkeypatch.setitem(sys.modules, "pygame", None)

    with pytest.raises(SystemExit) as exc:
        main(["--seed", "0", "--gui"])

    assert exc.value.code != 0
    assert ".[gui]" in capsys.readouterr().err


def test_headless_run_does_not_import_pygame():
    code = (
        "import sys\n"
        "from kaucjowicze.__main__ import main\n"
        "main(['--seed', '0'])\n"
        "assert 'pygame' not in sys.modules\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "Collected" in result.stdout
