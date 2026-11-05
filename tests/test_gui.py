import numpy as np
import pytest

pygame = pytest.importorskip("pygame")

from kaucjowicze import gui  # noqa: E402
from kaucjowicze.agent import AgentState  # noqa: E402
from kaucjowicze.config import SimulationConfig  # noqa: E402
from kaucjowicze.grid import Grid  # noqa: E402
from kaucjowicze.policies import RandomWalkPolicy  # noqa: E402
from kaucjowicze.simulation import Simulation  # noqa: E402
from kaucjowicze.view import Playback, agent_color  # noqa: E402


def _make_sim(max_steps: int = 3000) -> Simulation:
    grid = Grid(20, 10)
    grid.add_obstacle(5, 2, 3, 3)
    grid.add_base((10, 5))
    grid.add_can((12, 5), 8)
    config = SimulationConfig(width=20, height=10, n_agents=2, max_steps=max_steps, seed=0)
    policy = RandomWalkPolicy(config.direction_persistence)
    return Simulation(config, grid, policy, np.random.default_rng(0))


def _recording_factory(max_steps: int = 3000) -> tuple[list[Simulation], object]:
    sims: list[Simulation] = []

    def make_sim() -> Simulation:
        sims.append(_make_sim(max_steps))
        return sims[-1]

    return sims, make_sim


def _key(key: int):
    return pygame.event.Event(pygame.KEYDOWN, key=key)


def _script_events(monkeypatch, frames: list[list]) -> None:
    """Feed one list of events per frame, then close the window."""
    remaining = iter(frames)
    quit_event = pygame.event.Event(pygame.QUIT)
    monkeypatch.setattr(pygame.event, "get", lambda: next(remaining, [quit_event]))


@pytest.fixture(autouse=True)
def _headless_sdl(monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")


@pytest.fixture
def window(_headless_sdl):
    pygame.init()
    yield pygame.display.set_mode((200, 200)), pygame.font.Font(None, 20)
    pygame.quit()


def test_space_toggles_pause():
    playback = Playback()
    assert gui.apply_key(pygame.K_SPACE, playback) is gui.Action.NONE
    assert playback.paused
    gui.apply_key(pygame.K_SPACE, playback)
    assert not playback.paused


@pytest.mark.parametrize("key", ["K_PLUS", "K_EQUALS", "K_KP_PLUS"])
def test_plus_keys_speed_up(key):
    playback = Playback()
    before = playback.speed
    gui.apply_key(getattr(pygame, key), playback)
    assert playback.speed > before


@pytest.mark.parametrize("key", ["K_MINUS", "K_KP_MINUS"])
def test_minus_keys_slow_down(key):
    playback = Playback()
    before = playback.speed
    gui.apply_key(getattr(pygame, key), playback)
    assert playback.speed < before


def test_p_toggles_pheromone():
    playback = Playback()
    gui.apply_key(pygame.K_p, playback)
    assert not playback.show_pheromone
    gui.apply_key(pygame.K_p, playback)
    assert playback.show_pheromone


def test_action_keys():
    playback = Playback()
    assert gui.apply_key(pygame.K_r, playback) is gui.Action.RESTART
    assert gui.apply_key(pygame.K_ESCAPE, playback) is gui.Action.QUIT
    assert gui.apply_key(pygame.K_a, playback) is gui.Action.NONE


def test_window_size_fits_map_and_hud():
    width, height = gui.window_size(_make_sim().grid, cell_size=10)
    assert width == 200
    assert height == 100 + gui.HUD_HEIGHT


def test_draw_only_reads_the_simulation(window):
    screen, font = window
    sim = _make_sim()
    sim.pheromone = np.ones((10, 20))
    for _ in range(5):
        sim.step()
    cans = sim.grid.cans.copy()
    agents = [(a.pos, a.state, a.bag, a.path_length) for a in sim.agents]
    rng_state = sim.rng.bit_generator.state

    gui.draw(screen, font, sim, Playback(), "random", 0)

    assert np.array_equal(sim.grid.cans, cans)
    assert [(a.pos, a.state, a.bag, a.path_length) for a in sim.agents] == agents
    assert sim.step_count == 5
    assert sim.rng.bit_generator.state == rng_state


def test_draw_paints_agents_in_the_color_of_their_state(window):
    screen, font = window
    sim = _make_sim()
    sim.agents[0].pos = (1, 1)
    sim.agents[1].pos = (3, 1)
    sim.agents[1].state = AgentState.CARRYING

    gui.draw(screen, font, sim, Playback(), "random", 0, cell_size=10)

    assert screen.get_at((15, 15))[:3] == agent_color(AgentState.SEARCHING)
    assert screen.get_at((35, 15))[:3] == agent_color(AgentState.CARRYING)


def test_loop_closes_on_quit_event(monkeypatch):
    _script_events(monkeypatch, [])
    gui.run_gui(_make_sim, "random", 0)
    assert not pygame.get_init()


def test_loop_closes_on_escape(monkeypatch):
    next_frame = [_key(pygame.K_SPACE)]
    _script_events(monkeypatch, [[_key(pygame.K_ESCAPE)], next_frame])
    gui.run_gui(_make_sim, "random", 0)
    assert pygame.event.get() is next_frame  # the loop never asked for the following frame


def test_loop_advances_the_simulation(monkeypatch):
    sims, make_sim = _recording_factory()
    _script_events(monkeypatch, [[] for _ in range(15)])
    gui.run_gui(make_sim, "random", 0)
    assert sims[0].step_count > 0


def test_paused_loop_does_not_advance(monkeypatch):
    sims, make_sim = _recording_factory()
    _script_events(monkeypatch, [[_key(pygame.K_SPACE)]] + [[] for _ in range(15)])
    gui.run_gui(make_sim, "random", 0)
    assert sims[0].step_count == 0


def test_loop_stops_stepping_when_finished(monkeypatch):
    sims, make_sim = _recording_factory(max_steps=2)
    _script_events(monkeypatch, [[] for _ in range(30)])
    gui.run_gui(make_sim, "random", 0)
    assert sims[0].step_count == 2


def test_restart_builds_a_new_simulation_and_keeps_view_settings(monkeypatch):
    sims, make_sim = _recording_factory()
    frames = [[_key(pygame.K_SPACE)], [_key(pygame.K_r)]] + [[] for _ in range(15)]
    _script_events(monkeypatch, frames)
    gui.run_gui(make_sim, "random", 0)
    assert len(sims) == 2
    assert sims[1].step_count == 0  # still paused after the restart
