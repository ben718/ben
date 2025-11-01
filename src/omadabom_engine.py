"""Core rule engine powering the OmadaBOM configurateur.

The module now relies on an external catalogue (JSON file) that can be refreshed
without touching the Python code.  The rule engine reads it on demand, caches it
and recomputes the bill of materials, the downloadable archive (CSV + PDF) and
all metrics presented in the UI.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from io import BytesIO, StringIO
from math import ceil
from pathlib import Path
from typing import Dict, Iterable, List, Sequence
from zipfile import ZIP_DEFLATED, ZipFile

import csv


@dataclass(frozen=True)
class AccessPoint:
    modele: str
    sku: str
    poe: int
    prix: int
    multi_gig: bool = False


@dataclass(frozen=True)
class Switch:
    modele: str
    sku: str
    ports_total: int
    ports_poe: int
    budget: int
    prix: int
    ports_2_5g: int = 0
    ports_10g: int = 0
    idle_w: int = 35


@dataclass(frozen=True)
class Router:
    modele: str
    sku: str
    prix: int
    conso: int
    sfp_plus: bool = False


@dataclass(frozen=True)
class Controller:
    modele: str
    sku: str
    prix: int
    conso: int


@dataclass(frozen=True)
class Camera:
    modele: str
    sku: str
    prix: int
    poe: int


@dataclass(frozen=True)
class NVR:
    modele: str
    sku: str
    canaux: int
    prix: int
    conso: int


@dataclass(frozen=True)
class StorageOption:
    capacite: int
    prix: int


@dataclass(frozen=True)
class Catalogue:
    """Container loading the equipment list from ``data/catalogue.json``."""

    access_points: Dict[str, AccessPoint]
    switches: Sequence[Switch]
    routers: Dict[str, Router]
    controllers: Dict[str, Controller]
    cameras: Dict[str, Camera]
    nvrs: Sequence[NVR]
    storage: Sequence[StorageOption]
    source: Path

    @classmethod
    def from_dict(cls, payload: dict, *, source: Path) -> "Catalogue":
        try:
            aps = {
                entry["id"]: AccessPoint(
                    entry["modele"],
                    entry["sku"],
                    poe=int(entry["poe"]),
                    prix=int(entry["prix"]),
                    multi_gig=bool(entry.get("multi_gig", False)),
                )
                for entry in payload["access_points"]
            }
            switches = [
                Switch(
                    entry["modele"],
                    entry["sku"],
                    ports_total=int(entry["ports_total"]),
                    ports_poe=int(entry["ports_poe"]),
                    budget=int(entry["budget"]),
                    prix=int(entry["prix"]),
                    ports_2_5g=int(entry.get("ports_2_5g", 0)),
                    ports_10g=int(entry.get("ports_10g", 0)),
                    idle_w=int(entry.get("idle_w", 35)),
                )
                for entry in payload["switches"]
            ]
            routers = {
                entry["id"]: Router(
                    entry["modele"],
                    entry.get("sku", entry["id"].upper()),
                    prix=int(entry["prix"]),
                    conso=int(entry.get("conso", 18)),
                    sfp_plus=bool(entry.get("sfp_plus", False)),
                )
                for entry in payload["routers"]
            }
            controllers = {
                entry["id"]: Controller(
                    entry["modele"],
                    entry.get("sku", entry["id"].upper()),
                    prix=int(entry["prix"]),
                    conso=int(entry.get("conso", 12)),
                )
                for entry in payload["controllers"]
            }
            cameras = {
                entry["id"]: Camera(
                    entry["modele"],
                    entry["sku"],
                    prix=int(entry["prix"]),
                    poe=int(entry.get("poe", 0)),
                )
                for entry in payload["cameras"]
            }
            nvrs = [
                NVR(
                    entry["modele"],
                    entry["sku"],
                    canaux=int(entry["canaux"]),
                    prix=int(entry["prix"]),
                    conso=int(entry.get("conso", 20)),
                )
                for entry in payload["nvrs"]
            ]
            storage = [
                StorageOption(int(entry["capacite"]), int(entry["prix"]))
                for entry in payload["storage"]
            ]
        except (KeyError, TypeError, ValueError) as exc:  # pragma: no cover - defensive
            raise ValueError(
                "Catalogue invalide – vérifiez la structure de data/catalogue.json"
            ) from exc

        if not aps or not switches or not routers or not controllers:
            raise ValueError("Catalogue incomplet : équipements essentiels manquants.")

        return cls(aps, switches, routers, controllers, cameras, nvrs, storage, source)


CATALOG_ENV_VAR = "OMADABOM_CATALOGUE_PATH"
DEFAULT_CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "catalogue.json"

_CATALOGUE_OVERRIDE: Path | None = None
_CATALOGUE_CACHE: tuple[float, Catalogue] | None = None


def set_catalogue_path(path: Path | str | None) -> None:
    """Override the catalogue location (used by tests or admin tooling)."""

    global _CATALOGUE_OVERRIDE, _CATALOGUE_CACHE
    _CATALOGUE_OVERRIDE = Path(path) if path is not None else None
    _CATALOGUE_CACHE = None


def _catalogue_path() -> Path:
    if _CATALOGUE_OVERRIDE is not None:
        return _CATALOGUE_OVERRIDE
    env_path = os.environ.get(CATALOG_ENV_VAR)
    if env_path:
        return Path(env_path)
    return DEFAULT_CATALOG_PATH


def _load_catalogue(path: Path) -> Catalogue:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return Catalogue.from_dict(payload, source=path)


def _get_catalogue() -> Catalogue:
    global _CATALOGUE_CACHE
    path = _catalogue_path()
    mtime = path.stat().st_mtime
    if _CATALOGUE_CACHE and _CATALOGUE_CACHE[0] == mtime:
        return _CATALOGUE_CACHE[1]
    catalogue = _load_catalogue(path)
    _CATALOGUE_CACHE = (mtime, catalogue)
    return catalogue

MAX_SURFACE_M2 = 50_000


QOS_LABELS = {
    "voip": "Téléphonie (VoIP)",
    "visioconference": "Visioconférence",
    "navigation": "Navigation Web",
    "streaming": "Streaming vidéo",
    "iot": "IoT & capteurs",
}


def _base_ratio(environment: str | None) -> float:
    return {
        "bureau": 120.0,
        "maison": 100.0,
        "entrepot": 250.0,
        "hotel": 30.0,
        "exterieur": 500.0,
    }.get(environment or "", 120.0)


def _density_factor(density: str | None) -> float:
    return {"faible": 1.2, "moyenne": 1.0, "elevee": 0.75}.get(density or "", 1.0)


def _structure_factor(structure: str | None) -> float:
    return {"cloisons": 1.0, "murs": 0.85, "metal": 0.7}.get(structure or "", 1.0)


def _height_factor(height: str | None) -> float:
    return {"standard": 1.0, "elevee": 0.95, "tres": 1.15}.get(height or "", 1.0)


def _safe_number(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _validate_payload(payload: dict) -> None:
    if not isinstance(payload, dict):
        raise ValueError("Données de configuration invalides.")

    zones = payload.get("zones") or []
    if zones:
        has_positive_zone = any(_safe_number(zone.get("surface")) > 0 for zone in zones)
        if not has_positive_zone:
            raise ValueError("Chaque zone doit posséder une surface positive.")
        total_surface = sum(max(_safe_number(zone.get("surface")), 0.0) for zone in zones)
    else:
        total_surface = _safe_number(payload.get("surface"))
        if total_surface <= 0:
            raise ValueError("La surface totale doit être supérieure à 0 m².")

    if total_surface > MAX_SURFACE_M2:
        raise ValueError("La surface totale dépasse la limite prise en charge (50 000 m²).")

    cctv = payload.get("cctv") or {}
    if cctv.get("enabled"):
        interior = max(_safe_number(cctv.get("interior")), 0.0)
        exterior = max(_safe_number(cctv.get("exterior")), 0.0)
        if interior + exterior <= 0:
            raise ValueError("Activez au moins une caméra si la vidéosurveillance est activée.")
        retention = _safe_number(cctv.get("retention"))
        if retention <= 0:
            raise ValueError("La durée de rétention doit être supérieure à zéro.")
        resolution = str(cctv.get("resolution") or "").upper()
        if resolution not in {"1080P", "4MP", "8MP"}:
            raise ValueError("Résolution de caméra inconnue.")
        mode = str(cctv.get("mode") or "").lower()
        if mode not in {"continu", "mouvement"}:
            raise ValueError("Mode d'enregistrement inconnu.")


def _compute_access_points(payload: dict) -> int:
    structure = payload.get("structure")
    height = payload.get("height")
    base_factor = _structure_factor(structure) * _height_factor(height)
    zones = payload.get("zones") or []
    if not zones:
        zones = [
            {
                "surface": payload.get("surface", 0),
                "density": payload.get("density"),
                "environment": payload.get("environment"),
            }
        ]

    total = 0
    for zone in zones:
        surface = max(_safe_number(zone.get("surface")), 0.0)
        if surface == 0:
            continue
        environment = (zone.get("environment") or payload.get("environment")) or ""
        density = (zone.get("density") or payload.get("density")) or ""
        ratio = max(35.0, _base_ratio(environment) * base_factor * _density_factor(density))
        total += ceil(surface / ratio)

    return max(total, 1)


def _pick_access_point(payload: dict, ap_count: int, catalogue: Catalogue) -> AccessPoint:
    environment = payload.get("environment")
    density = payload.get("density")
    services = payload.get("services") or {}
    if environment == "hotel":
        return catalogue.access_points["eap615"]
    if environment == "exterieur":
        return catalogue.access_points["eap610_outdoor"]
    if density == "elevee" or services.get("haute_vitesse"):
        return catalogue.access_points["eap690"]
    if ap_count >= 6:
        return catalogue.access_points["eap673"]
    if density == "faible":
        return catalogue.access_points["eap610"]
    return catalogue.access_points["eap650"]


def _compute_bandwidth(payload: dict) -> dict[str, float]:
    bandwidth = payload.get("bandwidth") or {}
    users = max(_safe_number(bandwidth.get("postes")), 0.0)
    per_user = max(_safe_number(bandwidth.get("mbpsParPoste")), 0.0)
    cameras = max(_safe_number(bandwidth.get("cameras")), 0.0)
    per_camera = max(_safe_number(bandwidth.get("mbpsParCamera")), 0.0)
    return {
        "users": users * per_user,
        "video": cameras * per_camera,
    }


def _pick_router(payload: dict, total_bandwidth: float, ap: AccessPoint, catalogue: Catalogue) -> Router:
    services = payload.get("services") or {}
    high_speed = services.get("haute_vitesse") or total_bandwidth > 1000
    if high_speed:
        key = "er7206" if ap.multi_gig else "er8411"
        return catalogue.routers[key]
    if total_bandwidth > 600:
        return catalogue.routers["er7206"]
    return catalogue.routers["er605"]


def _pick_controller(ap_count: int, camera_count: int, catalogue: Catalogue) -> Controller:
    devices = ap_count + camera_count + 1
    return catalogue.controllers["oc300" if devices > 25 else "oc200"]


def _pick_switch(
    ap_count: int,
    camera_count: int,
    poe_budget_required: float,
    min_speed: str,
    catalogue: Catalogue,
) -> Switch:
    poe_ports = ap_count + camera_count
    uplinks = 1 + (1 if camera_count > 0 else 0)
    ports_total = poe_ports + uplinks + ceil(poe_ports * 0.25)

    candidates = [
        switch
        for switch in catalogue.switches
        if switch.ports_poe >= poe_ports
        and switch.ports_total >= ports_total
        and switch.budget >= poe_budget_required
        and (
            min_speed == "1G"
            or (min_speed == "2.5G" and (switch.ports_2_5g > 0 or switch.ports_10g > 0))
            or (min_speed == "10G" and switch.ports_10g > 0)
        )
    ]

    return (candidates or [catalogue.switches[-1]])[0]


def _derive_cameras(payload: dict, catalogue: Catalogue) -> dict:
    cctv = payload.get("cctv") or {}
    if not cctv.get("enabled"):
        return {"entries": [], "poe": 0.0, "price": 0.0, "count": 0}

    entries: List[dict] = []
    interior_total = max(_safe_number(cctv.get("interior")), 0.0)
    interior_mix = cctv.get("interiorTypes") or {}
    mix_sum = max(
        _safe_number(interior_mix.get("dome"))
        + _safe_number(interior_mix.get("turret"))
        + _safe_number(interior_mix.get("bullet")),
        1.0,
    )
    scale = interior_total / mix_sum
    dome_qty = round(_safe_number(interior_mix.get("dome")) * scale)
    turret_qty = round(_safe_number(interior_mix.get("turret")) * scale)
    bullet_qty = round(_safe_number(interior_mix.get("bullet")) * scale)
    if dome_qty > 0:
        entries.append({"item": catalogue.cameras["dome"], "quantite": dome_qty})
    if turret_qty > 0:
        entries.append({"item": catalogue.cameras["turret"], "quantite": turret_qty})
    if bullet_qty > 0:
        entries.append({"item": catalogue.cameras["interior_bullet"], "quantite": bullet_qty})

    exterior_total = max(_safe_number(cctv.get("exterior")), 0.0)
    if exterior_total > 0:
        exterior_mix = cctv.get("exteriorTypes") or {}
        ai_enabled = bool(exterior_mix.get("ai"))
        ai_qty = max(1, round(exterior_total * 0.5)) if ai_enabled else 0
        classic_qty = max(round(exterior_total) - ai_qty, 0)
        if classic_qty > 0:
            entries.append({"item": catalogue.cameras["exterior"], "quantite": classic_qty})
        if ai_qty > 0:
            entries.append({"item": catalogue.cameras["exterior_ai"], "quantite": ai_qty})

    poe = 0.0
    price = 0.0
    count = 0
    normalized: List[dict] = []
    for entry in entries:
        item = entry["item"]
        qty = int(entry["quantite"])
        if qty <= 0:
            continue
        poe += item.poe * qty
        price += item.prix * qty
        count += qty
        normalized.append({
            "modele": item.modele,
            "sku": item.sku,
            "quantite": qty,
            "prix": item.prix,
            "poe": item.poe,
        })

    return {"entries": normalized, "poe": poe, "price": price, "count": count}


def _pick_nvr(camera_count: int, catalogue: Catalogue) -> NVR | None:
    if camera_count <= 0:
        return None
    for candidate in catalogue.nvrs:
        if candidate.canaux >= camera_count:
            return candidate
    return catalogue.nvrs[-1]


def _compute_storage_tb(camera_count: int, resolution: str | None, mode: str | None, retention: float) -> float:
    if camera_count <= 0 or retention <= 0:
        return 0.0
    bitrate_map = {"1080P": 5.0, "4MP": 8.0, "8MP": 12.0}
    bitrate = bitrate_map.get((resolution or "").upper(), 8.0)
    activity_factor = 0.3 if mode == "mouvement" else 1.0
    storage_mo = camera_count * bitrate * 3600 * 24 * retention * activity_factor / 8
    return storage_mo / (1024 * 1024)


def _pick_storage(required_tb: float, catalogue: Catalogue) -> StorageOption | None:
    if required_tb <= 0:
        return None
    for option in catalogue.storage:
        if option.capacite >= required_tb:
            return option
    return catalogue.storage[-1]


def _services_summary(payload: dict) -> List[str]:
    services = payload.get("services") or {}
    security = payload.get("security") or {}
    qos_order = payload.get("qosOrder") or []

    lines: List[str] = []
    if services.get("invites"):
        lines.append("VLAN invités isolé + portail captif")
    if services.get("voip"):
        lines.append("QoS prioritaire VoIP")
    if services.get("iot"):
        lines.append("Segment IoT dédié et ACL restrictives")
    if services.get("haute_vitesse"):
        lines.append("Backbone multi-gigabit recommandé")
    if security.get("isolation"):
        lines.append("Client isolation activée")
    if security.get("filtrage"):
        lines.append("Filtrage MAC / 802.1X envisagé")
    if security.get("portail"):
        lines.append("Portail captif avancé avec vouchers")

    priorities = " → ".join(
        QOS_LABELS.get(item, item.upper()) for item in qos_order if item in QOS_LABELS
    )
    if priorities:
        lines.append(f"Priorités QoS : {priorities}")

    return lines


def generate_plan(payload: dict) -> dict:
    """Compute the full bill of materials and human readable summary."""

    _validate_payload(payload)

    ap_count = _compute_access_points(payload)
    catalogue = _get_catalogue()

    ap_entry = _pick_access_point(payload, ap_count, catalogue)
    cameras = _derive_cameras(payload, catalogue)
    camera_count = cameras["count"]

    poe_budget_devices = ap_count * ap_entry.poe + cameras["poe"]
    poe_budget_required = ceil(poe_budget_devices * 1.2)

    bandwidth = _compute_bandwidth(payload)
    total_bandwidth = bandwidth["users"] + bandwidth["video"]
    router_entry = _pick_router(payload, total_bandwidth, ap_entry, catalogue)
    min_speed = "10G" if router_entry.sfp_plus else "2.5G" if (payload.get("services", {}).get("haute_vitesse") or ap_entry.multi_gig) else "1G"
    switch_entry = _pick_switch(
        ap_count,
        camera_count,
        poe_budget_required,
        min_speed,
        catalogue,
    )
    controller_entry = _pick_controller(ap_count, camera_count, catalogue)
    nvr_entry = _pick_nvr(camera_count, catalogue)

    cctv = payload.get("cctv") or {}
    storage_tb = _compute_storage_tb(
        camera_count,
        cctv.get("resolution"),
        cctv.get("mode"),
        _safe_number(cctv.get("retention"), 0),
    )
    storage_option = _pick_storage(storage_tb, catalogue)

    modules = []
    if router_entry.sfp_plus and switch_entry.ports_10g > 0:
        modules.append({"modele": "TXM431-SR", "sku": "TXM431SR", "quantite": 2, "prix": 99})

    price_total = (
        ap_count * ap_entry.prix
        + switch_entry.prix
        + router_entry.prix
        + controller_entry.prix
        + cameras["price"]
        + (nvr_entry.prix if nvr_entry else 0)
        + (storage_option.prix if storage_option else 0)
        + sum(module["prix"] * module["quantite"] for module in modules)
    )

    conso_totale = (
        ap_count * ap_entry.poe
        + switch_entry.idle_w
        + router_entry.conso
        + controller_entry.conso
        + sum(entry["poe"] for entry in cameras["entries"])
        + (nvr_entry.conso if nvr_entry else 0)
    )

    opex_kwh = (conso_totale / 1000) * 24 * 365
    opex_euros = opex_kwh * 0.25

    hardware_lines = [
        f"{ap_count} × {ap_entry.modele} ({ap_entry.sku})",
        f"{switch_entry.modele} · {switch_entry.ports_poe} ports PoE / {switch_entry.budget} W",
        f"{router_entry.modele} ({router_entry.sku})",
        f"{controller_entry.modele} ({controller_entry.sku})",
    ]
    for camera in cameras["entries"]:
        hardware_lines.append(f"{camera['quantite']} × {camera['modele']}")
    if nvr_entry:
        hardware_lines.append(f"{nvr_entry.modele} ({nvr_entry.sku})")
    if storage_option:
        hardware_lines.append(
            f"HDD surveillance {storage_option.capacite} To (besoin {storage_tb:.2f} To)"
        )
    for module in modules:
        hardware_lines.append(f"{module['quantite']} × {module['modele']}")

    metrics_lines = [
        f"Budget PoE requis : {int(poe_budget_required)} W",
        f"Budget PoE disponible : {switch_entry.budget} W",
        f"Consommation totale estimée : {int(conso_totale)} W",
        f"OPEX annuel : {opex_kwh:.0f} kWh · {opex_euros:.0f} €",
        f"Bande passante agrégée : {total_bandwidth:.0f} Mbps",
        f"Investissement estimé (HT) : {price_total:.0f} €",
    ]

    return {
        "hardware": hardware_lines,
        "metrics": metrics_lines,
        "services": _services_summary(payload),
        "details": {
            "aps": {
                "modele": ap_entry.modele,
                "sku": ap_entry.sku,
                "quantite": ap_count,
                "poe": ap_entry.poe,
                "prix": ap_entry.prix,
            },
            "switch": {
                "modele": switch_entry.modele,
                "sku": switch_entry.sku,
                "ports_poe": switch_entry.ports_poe,
                "ports_total": switch_entry.ports_total,
                "budget": switch_entry.budget,
                "prix": switch_entry.prix,
            },
            "routeur": {
                "modele": router_entry.modele,
                "sku": router_entry.sku,
                "prix": router_entry.prix,
            },
            "controleur": {
                "modele": controller_entry.modele,
                "sku": controller_entry.sku,
                "prix": controller_entry.prix,
            },
            "cameras": cameras["entries"],
            "nvr": ({
                "modele": nvr_entry.modele,
                "sku": nvr_entry.sku,
                "prix": nvr_entry.prix,
            }
            if nvr_entry
            else None),
            "stockage": (
                {
                    "capacite": storage_option.capacite,
                    "prix": storage_option.prix,
                    "requis": storage_tb,
                }
                if storage_option
                else None
            ),
            "modules": modules,
            "synthese": {
                "poe_requis": poe_budget_required,
                "poe_disponible": switch_entry.budget,
                "conso_totale": conso_totale,
                "opex_kwh": opex_kwh,
                "opex_euros": opex_euros,
                "bande_passante": total_bandwidth,
                "prix_total": price_total,
            },
        },
    }


def _csv_rows(plan: dict) -> Iterable[List[str]]:
    details = plan["details"]
    yield ["Catégorie", "Modèle", "SKU", "Quantité", "Remarques"]
    yield [
        "Points d'accès",
        details["aps"]["modele"],
        details["aps"]["sku"],
        str(details["aps"]["quantite"]),
        f"PoE {details['aps']['poe']} W",
    ]
    yield [
        "Switch",
        details["switch"]["modele"],
        details["switch"]["sku"],
        "1",
        f"{details['switch']['ports_poe']} ports PoE / {details['switch']['budget']} W",
    ]
    yield [
        "Routeur",
        details["routeur"]["modele"],
        details["routeur"]["sku"],
        "1",
        "",
    ]
    yield [
        "Contrôleur",
        details["controleur"]["modele"],
        details["controleur"]["sku"],
        "1",
        "",
    ]
    for camera in details["cameras"]:
        yield [
            "Caméra",
            camera["modele"],
            camera["sku"],
            str(camera["quantite"]),
            "PoE %s W" % camera["poe"],
        ]
    if details["nvr"]:
        yield ["NVR", details["nvr"]["modele"], details["nvr"]["sku"], "1", ""]
    if details["stockage"]:
        storage = details["stockage"]
        yield [
            "Stockage",
            f"Disque surveillance {storage['capacite']} To",
            "-",
            "1",
            f"Besoin théorique {storage['requis']:.2f} To",
        ]
    for module in details["modules"]:
        yield ["Module", module["modele"], module["sku"], str(module["quantite"]), ""]


def _format_synthese(plan: dict) -> str:
    synthese = plan["details"]["synthese"]
    lines = [
        "Synthèse technique",
        "===================",
        f"Budget PoE requis : {synthese['poe_requis']} W",
        f"Budget PoE disponible : {synthese['poe_disponible']} W",
        f"Consommation totale estimée : {synthese['conso_totale']:.0f} W",
        f"OPEX annuel : {synthese['opex_kwh']:.0f} kWh / {synthese['opex_euros']:.0f} €",
        f"Bande passante agrégée : {synthese['bande_passante']:.0f} Mbps",
        f"Investissement estimé (HT) : {synthese['prix_total']:.0f} €",
        "",
        "Services recommandés",
        "---------------------",
    ]
    lines.extend(plan["services"] or ["Aucun service spécifique sélectionné."])
    return "\n".join(lines) + "\n"


def _format_portmap(plan: dict) -> str:
    details = plan["details"]
    lines = [
        "Port-map recommandé",
        "====================",
        "1 · Uplink vers routeur",
    ]
    offset = 2
    for idx in range(details["aps"]["quantite"]):
        lines.append(f"{offset + idx} · Point d'accès #{idx + 1}")
    offset += details["aps"]["quantite"]
    camera_entries = details["cameras"]
    camera_total = sum(entry["quantite"] for entry in camera_entries)
    for idx in range(camera_total):
        lines.append(f"{offset + idx} · Caméra #{idx + 1}")
    if details["nvr"]:
        lines.append(f"{offset + camera_total} · Uplink NVR")
    return "\n".join(lines) + "\n"


def _format_vlan_plan(plan: dict) -> str:
    services = plan["services"]
    qos = plan["details"]["synthese"]
    return "\n".join(
        [
            "Plan d'adressage VLAN suggéré",
            "===============================",
            "VLAN 10 · Management (contrôleur + AP)",
            "VLAN 20 · Employés",
            "VLAN 30 · Invités",
            "VLAN 40 · IoT & capteurs",
            "VLAN 50 · Vidéosurveillance",
            "",
            "Rappel OPEX annuel estimé : %.0f kWh / %.0f €" % (qos["opex_kwh"], qos["opex_euros"]),
            "Services pris en compte :",
        ]
        + (services or ["- Aucun"])
    ) + "\n"


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _render_pdf(title: str, lines: Sequence[str]) -> bytes:
    """Generate a minimal single-page PDF using Helvetica without dependencies."""

    content_lines = [title] + list(lines)
    operators = ["BT", "/F1 12 Tf", "1 0 0 1 72 770 Tm"]
    first = True
    for line in content_lines:
        escaped = _pdf_escape(line)
        if first:
            operators.append(f"({escaped}) Tj")
            first = False
        else:
            operators.append("T*")
            operators.append(f"({escaped}) Tj")
    operators.append("ET")
    stream = "\n".join(operators) + "\n"
    stream_bytes = stream.encode("latin-1", "replace")

    objects: List[bytes] = []

    def add_object(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    add_object(b"<< /Type /Catalog /Pages 2 0 R >>")
    add_object(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    add_object(
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>"
    )
    add_object(
        b"<< /Length %d >>\nstream\n" % len(stream_bytes)
        + stream_bytes
        + b"endstream"
    )
    add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    buffer = BytesIO()
    buffer.write(b"%PDF-1.4\n")
    offsets = [0]
    for index, body in enumerate(objects, start=1):
        offsets.append(buffer.tell())
        buffer.write(f"{index} 0 obj\n".encode("ascii"))
        buffer.write(body)
        if not body.endswith(b"\n"):
            buffer.write(b"\n")
        buffer.write(b"endobj\n")
    xref_offset = buffer.tell()
    buffer.write(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    buffer.write(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        buffer.write(f"{offset:010} 00000 n \n".encode("ascii"))
    buffer.write(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode(
            "ascii"
        )
    )
    return buffer.getvalue()


def build_archive(plan: dict) -> bytes:
    """Create the ZIP archive bundling CSV + synthèse + plans."""

    csv_rows = list(_csv_rows(plan))
    synthese_text = _format_synthese(plan)
    portmap_text = _format_portmap(plan)
    vlan_text = _format_vlan_plan(plan)

    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        csv_buffer = StringIO()
        writer = csv.writer(csv_buffer)
        for row in csv_rows:
            writer.writerow(row)
        archive.writestr("bom.csv", csv_buffer.getvalue())
        archive.writestr("synthese.txt", synthese_text)
        archive.writestr("portmap.txt", portmap_text)
        archive.writestr("plan_vlan.txt", vlan_text)
        archive.writestr(
            "bom.pdf",
            _render_pdf("BOM détaillée", [" | ".join(row) for row in csv_rows]),
        )
        archive.writestr(
            "synthese.pdf",
            _render_pdf("Synthèse technique", synthese_text.strip().splitlines()),
        )
        archive.writestr(
            "plan_vlan.pdf",
            _render_pdf("Plan VLAN & Port-map", (portmap_text + "\n" + vlan_text).strip().splitlines()),
        )

    return buffer.getvalue()

