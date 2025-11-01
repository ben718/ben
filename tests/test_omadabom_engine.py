from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.omadabom_engine import generate_plan, set_catalogue_path


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


def test_generate_plan_reads_external_catalogue(tmp_path: Path) -> None:
    catalogue = {
        "access_points": [
            {
                "id": "eap610",
                "modele": "Custom AP",
                "sku": "CUSTOMAP",
                "poe": 20,
                "prix": 200,
                "multi_gig": False,
            },
            {
                "id": "eap650",
                "modele": "Fallback AP",
                "sku": "FALLBACK",
                "poe": 15,
                "prix": 150,
                "multi_gig": False,
            },
            {
                "id": "eap673",
                "modele": "Dense AP",
                "sku": "DENSE",
                "poe": 19,
                "prix": 239,
                "multi_gig": True,
            },
            {
                "id": "eap690",
                "modele": "Premium AP",
                "sku": "PREMIUM",
                "poe": 23,
                "prix": 400,
                "multi_gig": True,
            },
            {
                "id": "eap615",
                "modele": "Hotel AP",
                "sku": "HOTEL",
                "poe": 13,
                "prix": 139,
                "multi_gig": False,
            },
            {
                "id": "eap610_outdoor",
                "modele": "Outdoor AP",
                "sku": "OUTDOOR",
                "poe": 16,
                "prix": 180,
                "multi_gig": False,
            },
        ],
        "switches": [
            {
                "modele": "Custom Switch",
                "sku": "CUSW",
                "ports_total": 16,
                "ports_poe": 12,
                "budget": 300,
                "prix": 400,
                "ports_2_5g": 0,
                "ports_10g": 0,
                "idle_w": 25,
            }
        ],
        "routers": [
            {"id": "er605", "modele": "Custom Router", "sku": "CR", "prix": 100, "conso": 10},
            {"id": "er7206", "modele": "Multi Router", "sku": "MR", "prix": 200, "conso": 12},
            {"id": "er8411", "modele": "10G Router", "sku": "TR", "prix": 300, "conso": 18, "sfp_plus": True},
        ],
        "controllers": [
            {"id": "oc200", "modele": "Custom Controller", "sku": "CC", "prix": 90, "conso": 8},
            {"id": "oc300", "modele": "Big Controller", "sku": "BC", "prix": 180, "conso": 12},
        ],
        "cameras": [
            {"id": "dome", "modele": "Cam Dome", "sku": "CD", "prix": 100, "poe": 10},
            {"id": "turret", "modele": "Cam Turret", "sku": "CT", "prix": 90, "poe": 9},
            {"id": "interior_bullet", "modele": "Cam Bullet", "sku": "CB", "prix": 80, "poe": 8},
            {"id": "exterior", "modele": "Cam Outdoor", "sku": "CO", "prix": 120, "poe": 12},
            {"id": "exterior_ai", "modele": "Cam AI", "sku": "CAI", "prix": 150, "poe": 13},
        ],
        "nvrs": [
            {"modele": "Mini NVR", "sku": "MNVR", "canaux": 8, "prix": 220, "conso": 15},
        ],
        "storage": [
            {"capacite": 4, "prix": 120},
            {"capacite": 8, "prix": 160},
        ],
    }

    catalogue_path = tmp_path / "catalogue.json"
    catalogue_path.write_text(json.dumps(catalogue), encoding="utf-8")

    set_catalogue_path(catalogue_path)
    try:
        plan = generate_plan(
            {
                "surface": 200,
                "environment": "bureau",
                "density": "faible",
                "services": {},
            }
        )
    finally:
        set_catalogue_path(None)

    assert plan["details"]["aps"]["modele"] == "Custom AP"
    assert plan["details"]["switch"]["modele"] == "Custom Switch"
