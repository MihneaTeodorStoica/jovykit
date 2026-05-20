from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from jovykit.config import JovyKitError
from jovykit.images import (
    image_level_from_reference,
    python_version_from_image,
    resolve_image_level,
)
from jovykit.templates import (
    render_compose,
    render_containerfile,
    render_devcontainer,
    render_requirements,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
IMAGE_DIR = REPO_ROOT / "image"


def requirement_names(path: Path) -> set[str]:
    names = set()
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        line = line.split(";", 1)[0].strip()
        for separator in ("==", ">=", "<=", "~=", "!=", ">", "<"):
            if separator in line:
                line = line.split(separator, 1)[0]
                break
        names.add(line.lower())
    return names


def test_render_compose_is_small_and_watch_enabled() -> None:
    compose = yaml.safe_load(
        render_compose(
            project_name="My Project",
            level="base",
            python_version="3.13",
            gpu="none",
            port=8888,
            token="jovykit",
        )
    )

    service = compose["services"]["jovy"]
    assert set(service) == {
        "build",
        "environment",
        "ports",
        "volumes",
        "working_dir",
        "stdin_open",
        "tty",
        "develop",
    }
    assert "gpus" not in service
    assert service["environment"] == {"JUPYTER_TOKEN": "jovykit"}
    assert service["develop"]["watch"] == [
        {"action": "rebuild", "path": "./Dockerfile"},
        {"action": "rebuild", "path": "./requirements.txt"},
    ]


def test_render_containerfile_uses_requirements_txt_and_uv() -> None:
    text = render_containerfile(level="full", python_version="3.12")

    assert (
        "ARG JOVY_BASE_IMAGE=ghcr.io/mihneateodorstoica/jovykit:full-python-3.12"
        in text
    )
    assert "FROM ${JOVY_BASE_IMAGE}" in text
    assert "ARG PYTHON_VERSION" not in text
    assert "VIRTUAL_ENV=/opt/jovy" in text
    assert "NB_USER=jovyan" in text
    assert "uv" in text
    assert "UV_LINK_MODE=hardlink" in text
    assert "UV_PYTHON_DOWNLOADS=never" in text
    assert 'ENV PATH="${VIRTUAL_ENV}/bin:${HOME}/.local/bin:${PATH}"' in text
    assert "uv pip install --only-binary=:all:" in text
    assert "--mount=type=cache,target=/root/.cache/uv,sharing=locked" in text
    assert "source=requirements.txt,target=/tmp/jovy-requirements.txt,readonly" in text
    assert "if [ -s /tmp/jovy-requirements.txt ]; then \\" in text
    assert "chown -R" not in text
    assert "/usr/local/share/jovykit/base-requirements.txt" not in text
    assert "mamba" not in text
    assert "conda" not in text
    assert "environment.yml" not in text
    assert "jovy-install-environment" not in text
    assert "required=false" not in text


def test_render_requirements_is_empty_by_default() -> None:
    assert render_requirements() == ""


def test_render_devcontainer_points_to_compose_service() -> None:
    config = yaml.safe_load(render_devcontainer("My Project"))

    assert config == {
        "name": "My Project",
        "dockerComposeFile": "../compose.yaml",
        "service": "jovy",
        "workspaceFolder": "/home/jovyan/work",
        "shutdownAction": "stopCompose",
        "overrideCommand": False,
        "customizations": {
            "vscode": {
                "extensions": [
                    "ms-python.python",
                    "ms-toolsai.jupyter",
                ],
                "settings": {
                    "python.defaultInterpreterPath": "/opt/jovy/bin/python",
                    "jupyter.jupyterServerType": "local",
                },
            }
        },
    }


def test_arbitrary_image_source_is_rejected() -> None:
    with pytest.raises(JovyKitError, match="Unknown image level"):
        resolve_image_level("quay.io/jupyter/minimal-notebook")


def test_latest_points_to_minimal_python_314() -> None:
    reference = "ghcr.io/mihneateodorstoica/jovykit:latest"

    assert image_level_from_reference(reference) == "minimal"
    assert python_version_from_image(reference) == "3.14"


def test_python_version_must_be_published_for_image_level() -> None:
    with pytest.raises(
        JovyKitError, match="full images support Python versions: 3.11, 3.12, 3.13"
    ):
        resolve_image_level("full", "3.14")

    assert (
        resolve_image_level("minimal", "3.14")
        == "ghcr.io/mihneateodorstoica/jovykit:minimal-python-3.14"
    )


def test_minimal_image_keeps_only_runtime_kernel_basics() -> None:
    dockerfile = (IMAGE_DIR / "Dockerfile").read_text()
    minimal_stage = dockerfile.split("FROM minimal AS base", 1)[0]
    requirements = requirement_names(IMAGE_DIR / "requirements-minimal.txt")

    assert {"jupyterlab", "ipykernel", "jupyterlab-nitro-ai-judge"} <= requirements
    assert "pip" not in requirements
    assert "nitro-ai-judge-cli" in requirements
    assert {"notebook", "ipywidgets", "jupyter-server-proxy"} & requirements == set()
    assert "SHELL=/bin/bash" in minimal_stage
    assert " git \\" not in minimal_stage
    assert "openssh-client" not in minimal_stage


def test_image_builds_prune_caches_and_do_not_rebuild_jupyterlab() -> None:
    dockerfile = (IMAGE_DIR / "Dockerfile").read_text()
    full_stage = dockerfile.split("FROM extended AS full", 1)[1]

    assert (
        "FROM ghcr.io/astral-sh/uv:python${PYTHON_VERSION}-bookworm-slim" in dockerfile
    )
    assert "uv python install" not in dockerfile
    assert "--python /usr/local/bin/python" in dockerfile
    assert 'ln -sf "${VIRTUAL_ENV}/bin/jupyter" /usr/local/bin/jupyter' in dockerfile
    assert "exec /opt/jovy/bin/jupyter lab" in dockerfile
    assert "UV_LINK_MODE=hardlink" in dockerfile
    assert 'ENV PATH="${VIRTUAL_ENV}/bin:${HOME}/.local/bin:${PATH}"' in dockerfile
    assert (
        'uv pip install --python "${VIRTUAL_ENV}/bin/python" pip==26.1.1' in dockerfile
    )
    assert 'exec "%s" -m pip "$@"' in dockerfile
    assert 'ln -sf pip "${VIRTUAL_ENV}/bin/pip3"' in dockerfile
    assert 'ln -sf pip "${VIRTUAL_ENV}/bin/pip${PYTHON_VERSION}"' in dockerfile
    assert 'ln -sf "${VIRTUAL_ENV}/bin/pip" /usr/local/bin/pip' in dockerfile
    assert 'ln -sf "${VIRTUAL_ENV}/bin/pip3" /usr/local/bin/pip3' in dockerfile
    assert "--mount=type=cache,target=/var/cache/apt,sharing=locked" in dockerfile
    assert "--mount=type=cache,target=/var/lib/apt/lists,sharing=locked" in dockerfile
    assert "/usr/share/doc/*" in dockerfile
    assert "jovy-prune-image" in dockerfile
    assert (
        'rm -rf /root/.cache/pip "$home_dir/.cache/pip" "$home_dir/.cache/uv"'
        in dockerfile
    )
    assert "share/jupyter/lab/staging" in dockerfile
    assert "jupyter lab build" not in dockerfile
    assert " git \\" not in full_stage
    assert "openssh-client" not in full_stage


def test_extended_image_includes_medium_packages_without_giant_packages() -> None:
    dockerfile = (IMAGE_DIR / "Dockerfile").read_text()
    base_stage = dockerfile.split("FROM base AS extended", 1)[0].split(
        "FROM minimal AS base", 1
    )[1]
    extended = requirement_names(IMAGE_DIR / "requirements-extended.txt")
    full = requirement_names(IMAGE_DIR / "requirements-full.txt")
    medium_packages = {
        "accelerate",
        "adlfs",
        "arch",
        "dask",
        "datasets",
        "distributed",
        "evaluate",
        "fsspec",
        "gcsfs",
        "imageio",
        "lightning",
        "lightgbm",
        "mlflow",
        "modin",
        "onnxruntime",
        "opencv-python-headless",
        "pillow",
        "pyarrow",
        "ray",
        "s3fs",
        "scikit-image",
        "sentence-transformers",
        "sktime",
        "streamlit",
        "tokenizers",
        "torch",
        "torchaudio",
        "torchmetrics",
        "torchvision",
        "transformers",
        "xgboost",
        "albumentations",
        "autoviz",
        "catboost",
        "cvxpy",
        "dvc",
        "einops",
        "evidently",
        "fasttext-wheel",
        "flaml",
        "gradio",
        "graphviz",
        "h5py",
        "librosa",
        "networkx",
        "onnx",
        "prophet",
        "pymc",
        "soundfile",
        "sympy",
        "tsfresh",
        "xarray",
    }
    full_packages = {
        "delta-spark",
        "flax",
        "great-expectations",
        "jax",
        "jaxlib",
        "keras",
        "optax",
        "orbax-checkpoint",
        "pytorch-lightning",
        "pyspark",
        "tensorboard",
        "tensorflow",
    }
    giant_packages = {
        "tensorflow",
        "jax",
        "jaxlib",
    }
    dropped_packages = {"eli5", "missingno", "scikit-plot"}

    assert medium_packages <= extended
    assert full_packages <= full
    assert giant_packages <= full
    assert extended & giant_packages == set()
    assert extended & dropped_packages == set()
    assert "apt-get install" not in base_stage
    assert "apt-get install" not in dockerfile.split("FROM extended AS full", 1)[1]
    assert " git \\" not in base_stage
    assert "openssh-client" not in base_stage
