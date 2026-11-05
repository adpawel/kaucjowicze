import pytest

from kaucjowicze.config import SimulationConfig


def test_default_agent_parameters_match_milestones():
    config = SimulationConfig()
    assert config.n_agents == 20
    assert config.bag_capacity == 10
    assert config.vision_radius == 2
    assert config.return_patience == 50
    assert config.max_steps == 3000


@pytest.mark.parametrize(
    "kwargs",
    [
        {"vision_radius": -1},
        {"return_patience": 0},
        {"max_steps": 0},
        {"direction_persistence": -0.1},
        {"direction_persistence": 1.5},
    ],
)
def test_invalid_agent_parameters_rejected(kwargs):
    with pytest.raises(ValueError):
        SimulationConfig(**kwargs)


def test_default_pheromone_parameters_match_milestones():
    config = SimulationConfig()
    assert config.evaporation_rate == 0.02
    assert config.pheromone_alpha == 1.0
    assert config.pheromone_base == 0.01
    assert config.exploration_rate == 0.1
    assert config.trail_deposit > 0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"evaporation_rate": -0.01},
        {"evaporation_rate": 1.01},
        {"pheromone_alpha": -1.0},
        {"pheromone_base": 0.0},
        {"exploration_rate": -0.1},
        {"exploration_rate": 1.1},
        {"trail_deposit": -1.0},
    ],
)
def test_invalid_pheromone_parameters_rejected(kwargs):
    with pytest.raises(ValueError):
        SimulationConfig(**kwargs)


def test_crowd_avoidance_is_on_by_default():
    config = SimulationConfig()
    assert config.crowd_radius >= 0
    assert 0.0 <= config.crowd_penalty < 1.0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"crowd_radius": -1},
        {"crowd_penalty": -0.1},
        {"crowd_penalty": 1.1},
    ],
)
def test_invalid_crowd_parameters_rejected(kwargs):
    with pytest.raises(ValueError):
        SimulationConfig(**kwargs)
