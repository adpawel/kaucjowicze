import subprocess
import sys
import types

import pytest

from kaucjowicze.__main__ import build_simulation, main
from kaucjowicze.policies import AcoPolicy, IndividualPolicy


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


def test_only_aco_simulation_has_a_pheromone_field():
    assert build_simulation("random", seed=0).pheromone is None
    sim = build_simulation("aco", seed=0)
    assert sim.pheromone.shape == (sim.grid.height, sim.grid.width)
    assert sim.pheromone.sum() == 0.0


def test_aco_runs_from_command_line(capsys):
    main(["--algorithm", "aco", "--seed", "0"])
    output = capsys.readouterr().out
    assert "Algorithm: aco" in output
    assert "Collected" in output


def test_aco_restart_reproduces_the_run(monkeypatch):
    calls = _fake_gui(monkeypatch)
    main(["--algorithm", "aco", "--seed", "5", "--gui"])
    make_sim = calls[0]["make_sim"]
    a, b = make_sim(), make_sim()
    for _ in range(200):
        a.step()
        b.step()
    assert [agent.pos for agent in a.agents] == [agent.pos for agent in b.agents]
    assert (a.pheromone == b.pheromone).all()


def test_aco_uses_the_shared_reward_by_default():
    assert isinstance(build_simulation("aco", seed=0).policy, AcoPolicy)
    assert isinstance(build_simulation("aco", seed=0, reward="shared").policy, AcoPolicy)


def test_individual_reward_leaves_no_trails():
    sim = build_simulation("aco", seed=0, reward="individual")
    assert isinstance(sim.policy, IndividualPolicy)
    assert sim.pheromone is None


def test_random_walk_has_no_reward_variants():
    with pytest.raises(ValueError, match="reward"):
        build_simulation("random", seed=0, reward="shared")


def test_build_simulation_rejects_unknown_reward():
    with pytest.raises(ValueError, match="Unknown reward"):
        build_simulation("aco", seed=0, reward="nope")


@pytest.mark.parametrize("reward", ["shared", "individual"])
def test_reward_variant_runs_from_command_line(capsys, reward):
    main(["--algorithm", "aco", "--reward", reward, "--seed", "0"])
    output = capsys.readouterr().out
    assert f"reward: {reward}" in output
    assert "Collected" in output
    assert "Reward per agent: min" in output


def test_random_walk_output_shows_no_reward(capsys):
    main(["--seed", "0"])
    assert "eward" not in capsys.readouterr().out


def test_reward_with_random_walk_is_a_usage_error(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--algorithm", "random", "--reward", "shared", "--seed", "0"])
    assert exc.value.code != 0
    assert "--reward" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("args", "variant"),
    [
        (["--algorithm", "random"], "random"),
        (["--algorithm", "aco"], "aco/shared"),
        (["--algorithm", "aco", "--reward", "shared"], "aco/shared"),
        (["--algorithm", "aco", "--reward", "individual"], "aco/individual"),
    ],
)
def test_window_shows_the_variant_name(monkeypatch, args, variant):
    calls = _fake_gui(monkeypatch)
    main([*args, "--seed", "5", "--gui"])
    assert calls[0]["variant"] == variant


def test_individual_restart_reproduces_the_run(monkeypatch):
    calls = _fake_gui(monkeypatch)
    main(["--algorithm", "aco", "--reward", "individual", "--seed", "5", "--gui"])
    make_sim = calls[0]["make_sim"]
    a, b = make_sim(), make_sim()
    assert isinstance(a.policy, IndividualPolicy)
    for _ in range(200):
        a.step()
        b.step()
    assert [agent.pos for agent in a.agents] == [agent.pos for agent in b.agents]
