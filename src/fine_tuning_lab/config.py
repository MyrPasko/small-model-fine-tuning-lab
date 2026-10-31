from dataclasses import dataclass
from enum import StrEnum


class RunVariant(StrEnum):
    BASELINE = "baseline"
    SMOKE = "smoke"
    FULL = "full"


@dataclass(frozen=True)
class ExperimentConfig:
    experiment_id: str
    variant: RunVariant
    seed: int

    def __post_init__(self) -> None:
        if not self.experiment_id.strip():
            raise ValueError("experiment_id must not be blank")

        if self.seed < 0:
            raise ValueError("seed must not be negative")
