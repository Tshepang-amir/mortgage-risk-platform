"""Phase 5 model features, score scaling and reproducibility constants."""

from typing import Final

SCORECARD_FEATURES: Final = (
    "CLASSIC_FICO",
    "OLTV",
    "DTI",
    "CURRENT_LTV",
    "SEASONING_MONTHS",
    "UNRATE",
    "MORTGAGE30US",
)
SCORECARD_TARGET: Final = "DEFAULT_IN_12M"
HAZARD_TARGET: Final = "DEFAULT_NEXT_MONTH"
RANDOM_SEED: Final = 20260921
BOOTSTRAP_REPLICATES: Final = 500
BOOTSTRAP_ALPHA: Final = 0.05

# Loan-level deterministic sample: 20 of 10,000 hash buckets, or 0.2%.
MODEL_SAMPLE_BUCKETS: Final = 10_000
MODEL_SAMPLE_KEEP: Final = 20

SCORECARD_PDO: Final = 20
SCORECARD_ODDS: Final = 50
SCORECARD_POINTS: Final = 600
SCORECARD_MAX_PREBINS: Final = 12
SCORECARD_MIN_PREBIN_SIZE: Final = 0.03

MLFLOW_EXPERIMENT_NAME: Final = "mortgage-risk-phase-5"
CHALLENGER_MONOTONIC_DIRECTIONS: Final[dict[str, int]] = {
    "CLASSIC_FICO": -1,
    "OLTV": 1,
    "DTI": 1,
    "CURRENT_LTV": 1,
}
CHALLENGER_N_ESTIMATORS: Final = 300
CHALLENGER_LEARNING_RATE: Final = 0.05
CHALLENGER_NUM_LEAVES: Final = 15
CHALLENGER_MAX_DEPTH: Final = 5
CHALLENGER_MIN_CHILD_SAMPLES: Final = 50
CHALLENGER_CALIBRATION_METHOD: Final = "sigmoid"
CHALLENGER_EXPERIMENT_NAME: Final = "mortgage-risk-phase-6"
