import pytest

from kaucjowicze.agent import Agent
from kaucjowicze.rewards import agent_rewards


def test_shared_reward_splits_all_delivered_cans_equally():
    agents = [Agent(id=0, pos=(0, 0), cans_collected=30), Agent(id=1, pos=(0, 0))]
    assert agent_rewards(agents, "shared") == [15.0, 15.0]


def test_individual_reward_is_what_the_agent_delivered():
    agents = [Agent(id=0, pos=(0, 0), cans_collected=30), Agent(id=1, pos=(0, 0))]
    assert agent_rewards(agents, "individual") == [30.0, 0.0]


def test_cans_in_the_bag_earn_nothing_yet():
    agents = [Agent(id=0, pos=(0, 0), bag=5, cans_collected=2)]
    assert agent_rewards(agents, "individual") == [2.0]
    assert agent_rewards(agents, "shared") == [2.0]


def test_rewards_without_agents_are_empty():
    assert agent_rewards([], "shared") == []


def test_unknown_reward_is_rejected():
    with pytest.raises(ValueError, match="Unknown reward"):
        agent_rewards([], "nope")
