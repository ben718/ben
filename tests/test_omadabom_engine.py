from __future__ import annotations

import pytest

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.omadabom_engine import generate_plan


def test_generate_plan_requires_surface_positive() -> None:
    payload = {
        "surface": 0,
        "environment": "bureau",
        "density": "moyenne",
        "services": {},
    }
    with pytest.raises(ValueError, match="surface"):
        generate_plan(payload)


def test_generate_plan_requires_cameras_when_cctv_enabled() -> None:
    payload = {
        "surface": 200,
        "environment": "bureau",
        "density": "moyenne",
        "services": {},
        "cctv": {
            "enabled": True,
            "interior": 0,
            "exterior": 0,
            "retention": 15,
            "resolution": "4MP",
            "mode": "continu",
        },
    }
    with pytest.raises(ValueError, match="caméra"):
        generate_plan(payload)
