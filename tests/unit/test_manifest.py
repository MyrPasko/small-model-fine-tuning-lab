import unittest
from dataclasses import FrozenInstanceError

from fine_tuning_lab.config import ExperimentConfig, RunVariant
from fine_tuning_lab.manifest import RunManifest


class TestRunManifest(unittest.TestCase):
    @staticmethod
    def _manifest(
        *,
        model_id: str = "Qwen/Qwen3-1.7B",
        model_revision: str = "model-rev-1",
        dataset_id: str = "Team-ACE/ToolACE",
        dataset_revision: str = "dataset-rev-1",
    ) -> RunManifest:
        return RunManifest(
            config=ExperimentConfig(
                experiment_id="EXP-001",
                variant=RunVariant.SMOKE,
                seed=42,
            ),
            model_id=model_id,
            model_revision=model_revision,
            dataset_id=dataset_id,
            dataset_revision=dataset_revision,
        )

    def test_to_json_returns_canonical_run_manifest(self) -> None:
        manifest = self._manifest()

        self.assertEqual(
            manifest.to_json(),
            '{"dataset":{"id":"Team-ACE/ToolACE","revision":"dataset-rev-1"},'
            '"experiment":{"id":"EXP-001","seed":42,"variant":"smoke"},'
            '"model":{"id":"Qwen/Qwen3-1.7B","revision":"model-rev-1"},'
            '"schema_version":1}',
        )

    def test_blank_model_id_is_rejected(self) -> None:
        for model_id in ("", "   "):
            with (
                self.subTest(model_id=model_id),
                self.assertRaisesRegex(ValueError, "model_id"),
            ):
                self._manifest(model_id=model_id)

    def test_blank_model_revision_is_rejected(self) -> None:
        for model_revision in ("", "   "):
            with (
                self.subTest(model_revision=model_revision),
                self.assertRaisesRegex(ValueError, "model_revision"),
            ):
                self._manifest(model_revision=model_revision)

    def test_blank_dataset_id_is_rejected(self) -> None:
        for dataset_id in ("", "   "):
            with (
                self.subTest(dataset_id=dataset_id),
                self.assertRaisesRegex(ValueError, "dataset_id"),
            ):
                self._manifest(dataset_id=dataset_id)

    def test_blank_dataset_revision_is_rejected(self) -> None:
        for dataset_revision in ("", "   "):
            with (
                self.subTest(dataset_revision=dataset_revision),
                self.assertRaisesRegex(ValueError, "dataset_revision"),
            ):
                self._manifest(dataset_revision=dataset_revision)

    def test_manifest_is_immutable(self) -> None:
        manifest = self._manifest()

        with self.assertRaises(FrozenInstanceError):
            field_name = "model_revision"
            setattr(manifest, field_name, "different-revision")
