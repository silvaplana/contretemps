"""Brands ("enseignes", Seb 17/11/2026): one server, one web domain per
brand. Each school has a nature (dance, combat...) that ties it to one
brand: its address is https://<sous_domaine>.<brand domain>, and a school
without its own colours or logo takes the brand's (spec/core.md §2.7 bis).

Contretemps is the default brand and stays exactly as before; adding a brand
(Assodance, Assomountain...) is one more entry below, plus its default logo
and icons in `defaut-<key>/`, and its domain on the gateway.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_HERE = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Brand:
    key: str
    nature: str  # école.nature that belongs to this brand
    name: str
    domain: str
    slogan: str
    background: str
    text: str
    accent: str
    # Installed app bar and splash screen when the school has no logo/colour.
    app_colour: str
    defaults_dir: Path
    logo_file: str
    # Mail sender name and address; None = the server's (SMTP_FROM_NAME /
    # SMTP_FROM_EMAIL), as before brands existed.
    sender_name: str | None
    sender_email: str | None


CONTRETEMPS = Brand(
    key="contretemps",
    nature="danse",
    name="Contretemps",
    domain=os.environ.get("DOMAINE_ECOLES", "contretemps.silvaplana.cloud"),
    slogan="Gestion d'école de danse du cours au gala",
    background="#FDECD8",
    text="#3A2410",
    accent="#D8722A",
    app_colour="#F46E19",
    defaults_dir=_HERE / "defaut",
    logo_file="logo-contretemps.png",
    sender_name=None,
    sender_email=None,
)

ASSOFIGHT = Brand(
    key="assofight",
    nature="combat",
    name="Assofight",
    domain=os.environ.get("DOMAINE_ASSOFIGHT", "assofight.silvaplana.cloud"),
    slogan="Gestion et enseignement pour association de sports de combat",
    background="#16171D",
    text="#F3F4F6",
    accent="#F4EA4B",
    app_colour="#16171D",
    defaults_dir=_HERE / "defaut-assofight",
    logo_file="logo-assofight.png",
    sender_name="Assofight",
    sender_email=os.environ.get("SMTP_FROM_EMAIL_ASSOFIGHT", "assofight@silvaplana.cloud"),
)

BRANDS = (CONTRETEMPS, ASSOFIGHT)
NATURES = {b.nature: b for b in BRANDS}


def of_nature(nature: str | None) -> Brand:
    return NATURES.get(nature or "", CONTRETEMPS)


def of_host(host: str | None) -> Brand | None:
    """The brand whose domain this host is or ends with; None otherwise
    (localhost, the server's own address)."""
    hote = (host or "").split(":")[0].strip().lower().rstrip(".")
    for brand in BRANDS:
        if hote == brand.domain or hote.endswith(f".{brand.domain}"):
            return brand
    return None
