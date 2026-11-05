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
