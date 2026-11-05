"""Simulation parameters."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SimulationConfig:
    """All tunable parameters of a single simulation run."""

    # Map
    width: int = 100
    height: int = 60

    # Cans
    n_clusters: int = 6
    cans_per_cluster: int = 40
    cluster_spread: float = 3.0  # standard deviation of can positions around a cluster centre
    n_background_cans: int = 30  # cans scattered uniformly outside clusters

    # Agents
    n_agents: int = 20
    bag_capacity: int = 10  # k: cans an agent carries before returning to base
    vision_radius: int = 2  # r: agent sees cans within this Chebyshev distance
    return_patience: int = 50  # S: steps without a new can before returning with a partial bag
    direction_persistence: float = 0.5  # random walk: probability of keeping the current heading

    # Time
    max_steps: int = 3000  # T: simulation limit

    # Reproducibility
    seed: int | None = None

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Map dimensions must be positive")
        if self.bag_capacity <= 0:
            raise ValueError("Bag capacity must be positive")
        if min(self.n_clusters, self.cans_per_cluster, self.n_background_cans, self.n_agents) < 0:
            raise ValueError("Counts must not be negative")
        if self.vision_radius < 0:
            raise ValueError("Vision radius must not be negative")
        if self.return_patience <= 0:
            raise ValueError("Return patience must be positive")
        if self.max_steps <= 0:
            raise ValueError("Max steps must be positive")
        if not 0.0 <= self.direction_persistence <= 1.0:
            raise ValueError("Direction persistence must be in [0, 1]")
