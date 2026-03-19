from __future__ import annotations

from pathlib import Path
import warnings

import joblib
import sklearn
from sklearn.exceptions import InconsistentVersionWarning


ARTIFACT_SCHEMA_VERSION = "baseline_artifact_v1"


def current_runtime_versions() -> dict[str, str]:
    return {
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "sklearn_version": sklearn.__version__,
        "joblib_version": joblib.__version__,
    }


def load_compatible_artifact(path: str | Path) -> dict:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", InconsistentVersionWarning)
        artifact = joblib.load(Path(path))
    if not isinstance(artifact, dict) or "pipeline" not in artifact:
        raise ValueError(f"Model artifact at {path} is invalid or incomplete.")
    for warning in caught:
        if not isinstance(warning.message, InconsistentVersionWarning):
            continue
        original_version = getattr(warning.message, "original_sklearn_version", None)
        if original_version is None:
            original_version = "an incompatible scikit-learn version"
        raise ValueError(
            f"Model artifact at {path} was built with scikit-learn {original_version}; "
            f"current runtime is {sklearn.__version__}. Retrain the model in the current environment."
        )
    sklearn_version = artifact.get("sklearn_version")
    joblib_version = artifact.get("joblib_version")
    if sklearn_version and sklearn_version != sklearn.__version__:
        raise ValueError(
            f"Model artifact at {path} was built with scikit-learn {sklearn_version}; "
            f"current runtime is {sklearn.__version__}. Retrain the model in the current environment."
        )
    if joblib_version and joblib_version != joblib.__version__:
        raise ValueError(
            f"Model artifact at {path} was built with joblib {joblib_version}; "
            f"current runtime is {joblib.__version__}. Retrain the model in the current environment."
        )
    return artifact


__all__ = ["ARTIFACT_SCHEMA_VERSION", "current_runtime_versions", "load_compatible_artifact"]
