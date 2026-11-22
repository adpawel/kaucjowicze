"""Reward functions: what agents try to maximize.

Agents do not learn, so a reward does not change anything by itself. It is the reason for the rules
of its variant (see the policies) and the agent's earnings at the end of a run.
"""

from collections.abc import Sequence

from kaucjowicze.agent import Agent
from kaucjowicze.config import EQUAL, SOURCE, SPEED, SimulationConfig

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


def trail_amount(agent: Agent, config: SimulationConfig, mean_cans: float) -> float:
    """Trail a carrying agent lays on the cell it leaves, by the trail signal of `config`.

    - `source` (N1): q * n, with n the cans seen at the source after the last pick-up,
    - `speed`: q_s * b / L for a source with cans left (n > 0), with b the cans carried and L the
      length of the whole trip,
    - `equal`: q * n * ((c + 1) / (mean_cans + 1)) ** gamma, with c the cans the agent delivered
      so far and `mean_cans` the mean of the colony.

    No signal marks an exhausted source (n = 0), so its trail fades out as in N1.
    """
    n = agent.source_cans
    if config.trail_signal == SOURCE:
        return config.trail_deposit * n
    if n == 0:
        return 0.0
    if config.trail_signal == SPEED:
        return config.speed_deposit * agent.bag / agent.trip_length
    if config.trail_signal == EQUAL:
        weight = ((agent.cans_collected + 1) / (mean_cans + 1)) ** config.fairness_gamma
        return config.trail_deposit * n * weight
    raise ValueError(f"Unknown trail signal: {config.trail_signal}")
