import json
from dataclasses import dataclass

from fine_tuning_lab.config import ExperimentConfig


@dataclass(frozen=True)
class RunManifest:
    config: ExperimentConfig
    model_id: str
    model_revision: str
    dataset_id: str
    dataset_revision: str

    def __post_init__(self) -> None:
        if not self.model_id.strip():
            raise ValueError("model_id must not be blank")

        if not self.model_revision.strip():
            raise ValueError("model_revision must not be blank")

        if not self.dataset_id.strip():
            raise ValueError("dataset_id must not be blank")

        if not self.dataset_revision.strip():
            raise ValueError("dataset_revision must not be blank")

    def to_json(self) -> str:
        payload = {
            "schema_version": 1,
            "experiment": {
                "id": self.config.experiment_id,
                "variant": self.config.variant.value,
                "seed": self.config.seed,
            },
            "model": {
                "id": self.model_id,
                "revision": self.model_revision,
            },
            "dataset": {
                "id": self.dataset_id,
                "revision": self.dataset_revision,
            },
        }

        return json.dumps(payload, sort_keys=True, separators=(",", ":"))
