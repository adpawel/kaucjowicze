"""Simulation parameters."""

from dataclasses import dataclass

TEST_MAP = "test"
CAMPUS_MAP = "campus"
MAPS = (TEST_MAP, CAMPUS_MAP)
STATIC = "static"
DYNAMIC = "dynamic"
SCENARIOS = (STATIC, DYNAMIC)
MAP_DEFAULTS = {
    TEST_MAP: {
        "cans_per_cluster": 40,
        "cluster_spread": 3.0,
        "n_background_cans": 30,
        "max_steps": 3000,
        "event_start": 250,
        "event_interval": 250,
    },
    CAMPUS_MAP: {
        "cans_per_cluster": 45,
        "cluster_spread": 2.0,
        "n_background_cans": 0,
        "max_steps": 20000,
        "event_start": 1000,
        "event_interval": 1000,
    },
}
# The dynamic scenario starts with half of the clusters and adds the rest as parties during a run,
# so the number of cans stays the same as in the static one
SCENARIO_DEFAULTS = {
    STATIC: {"n_clusters": 6, "n_events": 0},
    DYNAMIC: {"n_clusters": 3, "n_events": 3},
}


@dataclass(frozen=True)
class SimulationConfig:
    """All tunable parameters of a single simulation run."""

    # Map
    map_name: str = TEST_MAP  # the campus map has its own size, `width` and `height` are ignored
    width: int = 100
    height: int = 60

    # Scenario
    scenario: str = STATIC

    # Cans
    # `None` below stands for the value in `SCENARIO_DEFAULTS` or `MAP_DEFAULTS`
    n_clusters: int | None = None
    cans_per_cluster: int | None = None
    cluster_spread: float | None = None  # standard deviation of cans around a cluster centre
    n_background_cans: int | None = None  # cans scattered uniformly outside clusters
    cluster_dorm_distance: int = 4  # cluster centres lie this close to a dormitory, if any

    # Parties (dynamic scenario): new clusters appear during a run
    n_events: int | None = None
    event_start: int | None = None  # step at which the first party leaves its cans
    event_interval: int | None = None  # steps between consecutive parties
    cans_per_event: int | None = None  # `None` means `cans_per_cluster`

    # Agents
    n_agents: int = 20
    bag_capacity: int = 10  # k: cans an agent carries before returning to base
    vision_radius: int = 2  # r: agent sees cans within this Chebyshev distance
    return_patience: int = 50  # S: steps without a new can before returning with a partial bag
    direction_persistence: float = 0.5  # random walk: probability of keeping the current heading

    # Pheromone (ACO)
    trail_deposit: float = 1.0  # q: trail per step = q * cans the agent left at the source
    evaporation_rate: float = 0.02  # rho: each step tau <- (1 - rho) * tau
    pheromone_alpha: float = 1.0  # alpha: neighbour weight is (tau + tau0) ** alpha
    pheromone_base: float = 0.01  # tau0: weight of a cell without a trail
    exploration_rate: float = 0.1  # epsilon: probability of a random move instead of following
    crowd_radius: int = 3  # half-width of the window an agent checks for a crowd ahead of a move
    crowd_penalty: float = 0.0  # trail ahead of a crowd counts this much; 1 turns avoidance off

    # Time
    max_steps: int | None = None  # T: simulation limit

    # Reproducibility
    seed: int | None = None

    @property
    def last_event_step(self) -> int | None:
        """Step of the last party; `None` without parties."""
        if not self.n_events:
            return None
        return self.event_start + (self.n_events - 1) * self.event_interval

    def __post_init__(self) -> None:
        if self.map_name not in MAPS:
            raise ValueError(f"Unknown map: {self.map_name}")
        if self.scenario not in SCENARIOS:
            raise ValueError(f"Unknown scenario: {self.scenario}")
        for defaults in (SCENARIO_DEFAULTS[self.scenario], MAP_DEFAULTS[self.map_name]):
            for name, value in defaults.items():
                if getattr(self, name) is None:  # the dataclass is frozen
                    object.__setattr__(self, name, value)
        if self.cans_per_event is None:
            object.__setattr__(self, "cans_per_event", self.cans_per_cluster)
        if self.cluster_dorm_distance < 1:  # dormitories are obstacles, so a centre is never on one
            raise ValueError("Cluster distance from a dormitory must be positive")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Map dimensions must be positive")
        if self.bag_capacity <= 0:
            raise ValueError("Bag capacity must be positive")
        counts = (
            self.n_clusters,
            self.cans_per_cluster,
            self.n_background_cans,
            self.n_agents,
            self.n_events,
            self.cans_per_event,
        )
        if min(counts) < 0:
            raise ValueError("Counts must not be negative")
        if self.event_start < 0:
            raise ValueError("First party must not start before the run")
        if self.event_interval <= 0:
            raise ValueError("Interval between parties must be positive")
        if self.vision_radius < 0:
            raise ValueError("Vision radius must not be negative")
        if self.return_patience <= 0:
            raise ValueError("Return patience must be positive")
        if self.max_steps <= 0:
            raise ValueError("Max steps must be positive")
        if self.n_events and self.last_event_step >= self.max_steps:
            raise ValueError("Every party must start before the step limit")
        if not 0.0 <= self.direction_persistence <= 1.0:
            raise ValueError("Direction persistence must be in [0, 1]")
        if self.trail_deposit < 0:
            raise ValueError("Trail deposit must not be negative")
        if not 0.0 <= self.evaporation_rate <= 1.0:
            raise ValueError("Evaporation rate must be in [0, 1]")
        if self.pheromone_alpha < 0:
            raise ValueError("Pheromone alpha must not be negative")
        if self.pheromone_base <= 0:
            raise ValueError("Pheromone base level must be positive")
        if not 0.0 <= self.exploration_rate <= 1.0:
            raise ValueError("Exploration rate must be in [0, 1]")
        if self.crowd_radius < 0:
            raise ValueError("Crowd radius must not be negative")
        if not 0.0 <= self.crowd_penalty <= 1.0:
            raise ValueError("Crowd penalty must be in [0, 1]")
