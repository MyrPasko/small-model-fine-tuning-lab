import unittest
from dataclasses import FrozenInstanceError

from fine_tuning_lab.config import ExperimentConfig, RunVariant


class TestExperimentConfig(unittest.TestCase):
    def test_run_variants_have_expected_string_values(self) -> None:
        self.assertEqual(
            [variant.value for variant in RunVariant],
            ["baseline", "smoke", "full"],
        )
        self.assertTrue(all(isinstance(variant, str) for variant in RunVariant))

    def test_valid_config_preserves_values(self) -> None:
        config = ExperimentConfig(
            experiment_id="EXP-001",
            variant=RunVariant.BASELINE,
            seed=42,
        )

        self.assertEqual(config.experiment_id, "EXP-001")
        self.assertEqual(config.variant, RunVariant.BASELINE)
        self.assertEqual(config.seed, 42)

    def test_blank_experiment_id_is_rejected(self) -> None:
        for experiment_id in ("", "   "):
            with (
                self.subTest(experiment_id=experiment_id),
                self.assertRaises(ValueError),
            ):
                ExperimentConfig(
                    experiment_id=experiment_id,
                    variant=RunVariant.BASELINE,
                    seed=42,
                )

    def test_negative_seed_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ExperimentConfig(
                experiment_id="EXP-001",
                variant=RunVariant.BASELINE,
                seed=-1,
            )

    def test_zero_seed_is_allowed(self) -> None:
        config = ExperimentConfig(
            experiment_id="EXP-001",
            variant=RunVariant.SMOKE,
            seed=0,
        )

        self.assertEqual(config.seed, 0)

    def test_config_is_immutable(self) -> None:
        config = ExperimentConfig(
            experiment_id="EXP-001",
            variant=RunVariant.FULL,
            seed=42,
        )

        with self.assertRaises(FrozenInstanceError):
            field_name = "seed"
            setattr(config, field_name, 100)
