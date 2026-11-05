"""Reward functions: what agents try to maximize.

Agents do not learn, so a reward does not change anything by itself. It is the reason for the rules
of its variant (see the policies) and the agent's earnings at the end of a run.
"""

from collections.abc import Sequence

from kaucjowicze.agent import Agent

SHARED = "shared"  # N1: all delivered cans are split equally
INDIVIDUAL = "individual"  # N2: each agent keeps what it delivered
REWARDS = (SHARED, INDIVIDUAL)


def agent_rewards(agents: Sequence[Agent], reward: str) -> list[float]:
    """Reward of each agent, counting only cans delivered to a base."""
    if reward == SHARED:
        total = sum(agent.cans_collected for agent in agents)
        return [total / len(agents) for _ in agents]
    if reward == INDIVIDUAL:
        return [float(agent.cans_collected) for agent in agents]
    raise ValueError(f"Unknown reward: {reward}")
