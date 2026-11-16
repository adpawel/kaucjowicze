from dataclasses import replace

import pytest

from kaucjowicze.config import CURRENT_LAYOUT, LAYOUTS, SimulationConfig


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


def test_step_limit_defaults_to_the_one_of_the_map():
    assert SimulationConfig().max_steps == 3000
    assert SimulationConfig(map_name="campus").max_steps == 20000
    assert SimulationConfig(map_name="campus", max_steps=5).max_steps == 5


def test_can_layout_defaults_depend_on_the_map_and_can_be_overridden():
    test_map = SimulationConfig()
    assert (test_map.cans_per_cluster, test_map.cluster_spread) == (40, 3.0)
    assert test_map.n_background_cans == 30
    campus = SimulationConfig(map_name="campus")
    assert (campus.n_clusters, campus.cans_per_cluster, campus.n_background_cans) == (6, 45, 0)
    assert SimulationConfig(map_name="campus", n_background_cans=7).n_background_cans == 7


@pytest.mark.parametrize("distance", [0, -1])
def test_dormitory_distance_must_be_positive(distance):
    with pytest.raises(ValueError, match="dormitory"):
        SimulationConfig(cluster_dorm_distance=distance)


def test_dynamic_scenario_keeps_the_number_of_cans():
    static = SimulationConfig(map_name="campus")
    dynamic = SimulationConfig(map_name="campus", scenario="dynamic")
    assert (static.n_clusters, static.n_events) == (6, 0)
    assert (dynamic.n_clusters, dynamic.n_events) == (3, 3)
    assert dynamic.cans_per_event == dynamic.cans_per_cluster == 45
    assert (dynamic.event_start, dynamic.event_interval) == (1000, 1000)
    assert dynamic.last_event_step == 3000
    assert static.last_event_step is None


def test_scenario_defaults_can_be_overridden():
    config = SimulationConfig(scenario="dynamic", n_clusters=5, n_events=1, cans_per_event=3)
    assert (config.n_clusters, config.n_events, config.cans_per_event) == (5, 1, 3)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"scenario": "party"},
        {"scenario": "dynamic", "n_events": -1},
        {"scenario": "dynamic", "cans_per_event": -1},
        {"scenario": "dynamic", "cans_per_event": 0},
        {"scenario": "dynamic", "event_start": -1},
        {"scenario": "dynamic", "event_interval": 0},
        {"scenario": "dynamic", "max_steps": 750},  # the last party comes at step 750
    ],
)
def test_invalid_party_parameters_rejected(kwargs):
    with pytest.raises(ValueError):
        SimulationConfig(**kwargs)


def test_static_scenario_ignores_party_fields():
    config = SimulationConfig(event_start=-1, event_interval=0, cans_per_event=0)
    assert config.n_events == 0


def test_every_layout_has_the_same_number_of_cans():
    for counts in LAYOUTS.values():
        clustered = counts["n_clusters"] * counts["cans_per_cluster"]
        assert clustered + counts["n_background_cans"] == 270


def test_current_layout_is_the_default_of_the_campus_map():
    campus = SimulationConfig(map_name="campus")
    with_layout = SimulationConfig(map_name="campus", layout=CURRENT_LAYOUT)
    assert replace(with_layout, layout=None) == campus


@pytest.mark.parametrize("name", list(LAYOUTS))
def test_layout_sets_its_counts_and_survives_replace(name):
    config = SimulationConfig(map_name="campus", layout=name)
    for field, value in LAYOUTS[name].items():
        assert getattr(config, field) == value
    assert replace(config, seed=3).n_clusters == config.n_clusters


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"layout": "nope"}, "Unknown layout"),
        ({"layout": "uniform", "scenario": "dynamic"}, "static"),
    ],
)
def test_invalid_layouts_rejected(kwargs, message):
    with pytest.raises(ValueError, match=message):
        SimulationConfig(**kwargs)


def test_layout_replaces_counts_already_set():
    campus = SimulationConfig(map_name="campus")  # n_clusters is 6 here already
    few = replace(campus, layout="few-large")
    assert (few.n_clusters, few.cans_per_cluster) == (2, 135)
    uniform = replace(few, layout="uniform")
    assert (uniform.n_clusters, uniform.n_background_cans) == (0, 270)
    assert SimulationConfig(layout="few-large", n_clusters=3).n_clusters == 2
