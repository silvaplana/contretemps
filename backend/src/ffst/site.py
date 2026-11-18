"""Reading the FFST licence site, ffst-licences.com (spec/modules/ffst.md §3).

Ported from Sambo Admin (`silvaplana/test-python`, backend/src/ffst/ffst.py),
same requests. The site has no API: it is a WEBDEV application behind a
plain login form, the club login being typed in three boxes. Each page
carries its table as an escaped XML block inside a <script>, which we parse.
Licensees: the page shown right after logging in. Validated requests and
drafts (the basket): one more simulated click on the WEBDEV buttons « M32 »
and « M39 » of that page, on the same session (same cookies).

The site copes badly with two simultaneous logins on the same account: one
lock serialises every call, and each list gets its own login, as in Sambo
Admin."""

from __future__ import annotations

import html
import os
import re
import shutil
import threading
import unicodedata
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass, replace

import httpx

BASE_URL = "https://ffst-licences.com"
LOGIN_PATH = "/GESTION_LICENCES_FFST"

LICENSEES, VALIDATED, DRAFTS = "licensees", "validated", "drafts"
LISTS = (LICENSEES, VALIDATED, DRAFTS)

_lock = threading.Lock()


class FfstError(RuntimeError):
    """The site refused or did not answer: the message is shown as is."""


class FfstAuthError(FfstError):
    pass


CHANGED = "Le site de la FFST a changé : l’appli ne sait plus le lire."


@dataclass(frozen=True)
class Login:
    part1: str
    part2: str
    part3: str
    password: str


def _form(page_html: str, form_name: str) -> tuple[str, dict[str, str]]:
    """Absolute action URL and hidden fields of the WEBDEV form `form_name`."""
    action = re.search(rf'<form name="{form_name}" action="([^"]+)"', page_html)
    if not action:
        raise FfstError(CHANGED)
    hidden = {
        key: html.unescape(value)
        for key, value in re.findall(r'<input type="hidden" name="([^"]+)" value="([^"]*)"', page_html)
    }
    return f"{BASE_URL}{action.group(1)}", hidden


def _login(client: httpx.Client, login: Login) -> str:
    """Logs in and returns the « Licences de la saison » page."""
    page = client.get(f"{BASE_URL}{LOGIN_PATH}")
    url, hidden = _form(page.text, "ACCUEIL")
    data = {
        **hidden,
        "A5": login.part1,
        "A9": login.part2,
        "A10": login.part3,
        "A3": login.password,
        "WD_BUTTON_CLICK_": "A7",
    }
    response = client.post(url, data=data)
    if "Visu_Licences_Club" not in response.text:
        raise FfstAuthError("Le site de la FFST refuse cet identifiant ou ce mot de passe.")
    return response.text


def _click(client: httpx.Client, page_html: str, form_name: str, button: str) -> str:
    url, hidden = _form(page_html, form_name)
    return client.post(url, data={**hidden, "WD_BUTTON_CLICK_": button}).text


def parse_table(page_html: str) -> list[dict]:
    """The WEBDEV table (field « A1 ») of a page: one dict per row, keyed by
    the column titles of the site (« Nom et Prénom », « Né(e) le »...)."""
    match = re.search(r'DeclareChamp\("A1".*?WDTable,\["(.*?)",0,\d+,\d+,\d+,\d+,\[', page_html, re.DOTALL)
    if not match:
        raise FfstError(CHANGED)
    xml = match.group(1).replace("\\x3C", "<").replace("\\x3E", ">").replace('\\"', '"')
    try:
        root = ET.fromstring(xml)
        columns = [col.get("TITRE") for col in root.find("COLONNES")]
        return [dict(zip(columns, [col.text for col in row])) for row in root.find("LIGNES")]
    except (ET.ParseError, TypeError) as error:
        raise FfstError(CHANGED) from error


# The page after the click, and a text it must contain (Sambo Admin).
_PAGES = {VALIDATED: ("M32", "Renouvellement de licences"), DRAFTS: ("M39", "Panier")}


def _session(login: Login, do: Callable[[httpx.Client], object]):
    with _lock:
        try:
            with httpx.Client(follow_redirects=True, timeout=20) as client:
                return do(client)
        except httpx.HTTPError as error:
            raise FfstError("Le site de la FFST ne répond pas, réessayez plus tard.") from error


def check(login: Login) -> int:
    """« Tester la connexion »: logs in; returns the number of licensees."""
    return len(parse_table(_session(login, lambda client: _login(client, login))))


def read_list(login: Login, name: str) -> list[dict]:
    def do(client: httpx.Client) -> str:
        page = _login(client, login)
        if name == LICENSEES:
            return page
        button, marker = _PAGES[name]
        target = _click(client, page, "VISU_LICENCES_CLUB", button)
        if marker not in target:
            raise FfstError(CHANGED)
        return target

    return parse_table(_session(login, do))


def read_all(login: Login) -> dict[str, list[dict]]:
    """The three lists, read one after the other."""
    return {name: read_list(login, name) for name in LISTS}


# --- Writing: a request in the basket, or out of it (spec §5) ---
# Ported from Sambo Admin with the same clicks: these pages are forms run by
# client-side JS (WEBDEV editable tables, a form rebuilt after some fields),
# too fragile to replay as raw HTTP. A real browser (Playwright, the
# server's Chromium) does what a volunteer would do, one at a time.

# The options of the « Fonction* » field (A39) of the request form, as read
# on the site by Sambo Admin. To keep up to date if the site changes them.
FONCTIONS = [
    "001-PRESIDENT", "002-SECRETAIRE", "003-TRESORIER", "004-ENTRAINEUR", "005-PRATIQUANT",
    "006-JUGE", "007-ARBITRE", "008-ADMINISTRATIF", "010-VICE PRESIDENT", "011-TRESORIER PRATIQUANT",
    "012-SECRETAIRE PRATIQUANT", "013-ADMINISTRATIF PRATIQUANT", "014-DIRIGEANT PRATIQUANT",
    "015-DIRIGEANT", "016-PRESIDENT ENTRAINEUR", "017-SECRETAIRE ENTRAINEUR", "018-TRESORIER ENTRAINEUR",
    "019-PRESIDENT PRATIQUANT", "021-ADMINISTRATIF JUGE", "022-ADMINISTRATIF/JUGE/ENT",
    "024-SECRETAIRE ADJOINT", "025-TRESORIER ADJOINT", "026-ENT/ADM/PRATIQUANT", "028-PRESIDENT D'HONNEUR",
    "029-ENTRAINEUR - JUGE", "030-ADMINISTRATIF ENTRAINEUR", "032-PRESIDENT ADJOINT",
    "034-ENTRAINEUR - PRATIQUANT", "036-Vice Président/Entraîneur", "038-JUGE - PRATIQUANT",
    "042-RESPONSABLE SECTION", "043-MEDECIN", "053-INSTRUCTEUR", "056-PRESIDENT NATIONAL",
    "057-TRESORIERE NATIONALE", "059-TRESORIER - JUGE", "060-MEMBRE D HONNEUR", "061-ARBITRE - PRATIQUANT",
    "062-PRESIDENT - ARBITRE", "063-TRESORIER - ARBITRE", "064-SECRETAIRE - ARBITRE",
    "065-ENTRAINEUR - ARBITRE", "066-SECRETAIRE - JUGE",
]
PRATIQUANT = "005-PRATIQUANT"

_APOSTROPHES = "'’‘ʼ`´"


def site_name(name: str | None) -> str:
    """A name as the site accepts it: an apostrophe makes the site crash
    (« M'Hadjou » refused on 31/10/2026 in Sambo Admin), a space instead."""
    name = name or ""
    for apostrophe in _APOSTROPHES:
        name = name.replace(apostrophe, " ")
    return " ".join(name.split())


def site_city(city: str | None) -> str:
    """The site refuses a town whose first character is not a capital letter
    (« laciotat »): first letter in capitals, without accent."""
    city = (city or "").strip()
    if not city:
        return city
    first = "".join(c for c in unicodedata.normalize("NFD", city[0]) if not unicodedata.combining(c)).upper()
    return first + city[1:]


@dataclass(frozen=True)
class Person:
    """What a request needs, from the HelloAsso form (Sambo Admin)."""

    last_name: str
    first_name: str
    gender: str | None = None  # « H » or « F »
    birth_date: str | None = None  # JJ/MM/AAAA
    address: str | None = None
    postal_code: str | None = None
    city: str | None = None
    phone: str | None = None
    email: str | None = None


@dataclass(frozen=True)
class Settings:
    """The school's settings (spec §2), hard-coded for ASC in Sambo Admin."""

    discipline: str  # e.g. « 0470-SAMBO »
    default_birth_town: str  # e.g. « La Ciotat »
    image_rights: bool = True


class NotFound(FfstError):
    """No former licensee to renew: a new request is made instead."""


def _chromium() -> str | None:
    """The server's Chromium (Dockerfile, already there for the PDFs), or
    None: Playwright's own browser (tests, a developer's computer)."""
    explicit = os.environ.get("FFST_CHROMIUM")
    if explicit:
        return explicit
    return next((p for p in map(shutil.which, ("chromium", "chromium-browser")) if p), None)


def _browser(do: Callable):
    """Runs `do(page, warnings)` in a fresh browser, logged out at the end.
    The site's JS pop-ups are accepted, their text kept (`page.dialogs`):
    the confirmation of a request comes as one."""
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright

    with _lock:
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(executable_path=_chromium())
                try:
                    page = browser.new_page()
                    page.dialogs = []
                    page.on("dialog", lambda dialog: (page.dialogs.append(dialog.message), dialog.accept()))
                    warnings: list[str] = []
                    do(page, warnings)
                    return warnings
                finally:
                    browser.close()
        except PlaywrightError as error:
            raise FfstError(f"Le site de la FFST n’a pas répondu comme prévu : {error.message.splitlines()[0]}") from error


def _browser_login(page, login: Login) -> None:
    page.goto(f"{BASE_URL}{LOGIN_PATH}")
    page.fill('[name="A5"]', login.part1)
    page.fill('[name="A9"]', login.part2)
    page.fill('[name="A10"]', login.part3)
    page.fill('[name="A3"]', login.password)
    page.get_by_role("button", name="Valider").click()
    page.wait_for_load_state("networkidle")
    if "Visu_Licences_Club" not in page.content():
        raise FfstAuthError("Le site de la FFST refuse cet identifiant ou ce mot de passe.")


def create_request(login: Login, person: Person, fonction: str, settings: Settings) -> list[str]:
    """Puts a licence request in the basket: a renewal when one former
    licensee of the club has this name, otherwise a new request. Returns the
    warnings (birth town by default). The request is billed by the FFST once
    the basket is validated on the site: only ever on an explicit click."""
    if fonction not in FONCTIONS:
        raise FfstError(f"Fonction FFST inconnue : {fonction}")
    person = replace(
        person, last_name=site_name(person.last_name), first_name=site_name(person.first_name), city=site_city(person.city)
    )

    def do(page, warnings):
        _browser_login(page, login)
        try:
            _renew(page, person, fonction, settings, warnings)
        except NotFound:
            missing = [
                label
                for label, value in (
                    ("genre", person.gender), ("date de naissance", person.birth_date), ("adresse", person.address),
                    ("code postal", person.postal_code), ("ville", person.city),
                )
                if not value
            ]
            if missing:
                raise FfstError(
                    f"Jamais licencié au club, rien à reprendre d’une ancienne licence : il manque "
                    f"{', '.join(missing)}. À compléter dans sa fiche HelloAsso."
                ) from None
            if not settings.discipline:
                raise FfstError("Discipline manquante : à choisir dans les réglages FFST (Fonctionnalités).") from None
            _new_request(page, person, fonction, settings, warnings)

    return _browser(do)


def _settle(page) -> None:
    # Several fields reload the form on blur: wait for the network, a short
    # delay, and a field of the final form (Sambo Admin, seen in debug).
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(300)
    page.wait_for_selector('[name="A33"]', state="attached", timeout=15000)


def _renew(page, person: Person, fonction: str, settings: Settings, warnings: list[str]) -> None:
    # « Renouveler les licences » (WEBDEV button M31, in a drop-down menu).
    page.evaluate("_JSL(_PAGE_, 'M31', '_self', '', '')")
    page.wait_for_load_state("networkidle")
    page.get_by_label("Nom :", exact=True).fill(person.last_name)
    page.get_by_label("Prénom :", exact=True).fill(person.first_name)
    page.get_by_role("button", name="Rechercher").click()
    page.wait_for_load_state("networkidle")
    boxes = page.get_by_role("checkbox")
    if boxes.count() == 0:
        raise NotFound(person.last_name)
    if boxes.count() > 1:
        raise FfstError(
            f"Plusieurs anciens licenciés s’appellent {person.last_name} {person.first_name} : "
            "demande à faire à la main sur le site de la FFST."
        )
    boxes.first.check()
    page.get_by_role("button", name="Renouveler les licences sélectionnées").click()
    page.wait_for_selector('[name="A33"]', state="attached", timeout=15000)
    page.wait_for_load_state("networkidle")
    # Prefilled with the former licence's details, maybe out of date:
    # replaced by HelloAsso's (an empty one keeps the former value).
    _fill(page, person, fonction, settings, warnings)
    page.get_by_role(
        "checkbox", name="Vous êtes en possession de l'attestation d'assurance signée par l'adhérent"
    ).check()
    _save(page, person)


def _new_request(page, person: Person, fonction: str, settings: Settings, warnings: list[str]) -> None:
    # « Saisir une nouvelle demande » (WEBDEV button M30). The form is built
    # in two steps: wait for a field of the final form first.
    page.evaluate("_JSL(_PAGE_, 'M30', '_self', '', '')")
    page.wait_for_selector('[name="A33"]', state="attached", timeout=15000)
    page.wait_for_load_state("networkidle")
    page.select_option('[name="A33"]', label=settings.discipline)
    _settle(page)
    _fill(page, person, fonction, settings, warnings)
    if settings.image_rights:
        page.check("#A78_1")  # Droit à l'image
    page.check("#A35_1")  # Attestation d'assurance
    _save(page, person)


def _save(page, person: Person) -> None:
    """« Enregistrer votre demande », then check the site's confirmation
    (« bien enregistrée »): a missing field only shows a JS alert, which
    would otherwise look like a success."""
    page.dialogs.clear()
    page.get_by_role("button", name="Enregistrer votre demande").click()
    page.wait_for_load_state("networkidle")
    if any("bien" in m.lower() and "enregistr" in m.lower() for m in page.dialogs):
        return
    detail = page.dialogs[-1] if page.dialogs else "aucune confirmation du site (site modifié ?)"
    raise FfstError(f"Le site de la FFST n’a pas enregistré la demande de {person.last_name} {person.first_name} : {detail}")


def _fill(page, person: Person, fonction: str, settings: Settings, warnings: list[str]) -> None:
    """The fields shared by both forms (WEBDEV names read by Sambo Admin):
    A10 last name, A12 first name, A15 gender (1 man, 2 woman), A18 birth
    date, A39 function, A24/A27/A28 address, A29/A30 phones, A31 email."""

    def put(selector: str, value: str) -> None:
        page.fill(selector, value)
        page.press(selector, "Tab")  # the blur reloads the form
        _settle(page)

    put('[name="A10"]', person.last_name)
    put('[name="A12"]', person.first_name)
    if person.gender:
        page.check(f'[name="A15"][value="{"1" if person.gender == "H" else "2"}"]')
        _settle(page)
    if person.birth_date:
        put('[name="A18"]', person.birth_date)
    page.select_option('[name="A39"]', label=fonction)
    _settle(page)

    # « Commune de naissance »: required for any function but Pratiquant,
    # absent from HelloAsso. Hidden (renewal) or absent (new request)
    # otherwise: is_visible() covers both.
    if page.locator('[name="A61"]').is_visible():

        def search(town: str) -> list[dict]:
            page.fill('[name="A61"]', town)
            page.click("#A76")
            _settle(page)
            options = page.eval_on_selector(
                '[name="A54"]', "el => Array.from(el.options).map(o => ({value: o.value, text: o.text}))"
            )
            return [o for o in options if o["text"] != "Sélectionnez"]

        found = search(person.city) if person.city else []
        if len(found) != 1:
            found = search(settings.default_birth_town) if settings.default_birth_town else []
            if len(found) != 1:
                raise FfstError(
                    f"Commune de naissance introuvable pour « {person.city} » comme pour « "
                    f"{settings.default_birth_town} » : demande à faire à la main sur le site de la FFST."
                )
            warnings.append(
                f"Commune de naissance de {person.first_name} {person.last_name} introuvable pour « {person.city} » : "
                f"« {settings.default_birth_town} » mise par défaut, à corriger sur le site de la FFST si besoin."
            )
        page.select_option('[name="A54"]', value=found[0]["value"])
        _settle(page)

    # The address only when complete: otherwise the former one stays whole.
    if person.address and person.postal_code and person.city:
        put('[name="A27"]', person.postal_code)  # first: it suggests a town
        put('[name="A24"]', person.address)
        put('[name="A28"]', person.city)
    if person.phone:
        # HelloAsso has one number: in both boxes, the site may require either.
        put('[name="A29"]', person.phone)
        put('[name="A30"]', person.phone)
    if person.email:
        put('[name="A31"]', person.email)


def delete_draft(login: Login, last_name: str, first_name: str) -> None:
    """Takes a request out of the basket, then checks that its line is gone
    (two tries: the confirmation once did nothing, silently)."""
    target = " ".join(f"{site_name(last_name)} {site_name(first_name)}".split()).upper()

    def index(page) -> int:
        rows = parse_table(page.content())
        found = [i for i, r in enumerate(rows) if " ".join((r.get("Nom et Prénom") or "").split()).upper() == target]
        if len(found) > 1:
            raise FfstError(f"Plusieurs demandes en brouillon pour {last_name} {first_name} : à faire sur le site de la FFST.")
        return found[0] if found else -1

    def do(page, warnings):
        _browser_login(page, login)
        page.evaluate("_JSL(_PAGE_, 'M39', '_self', '', '')")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(500)
        if "Panier" not in page.content():
            raise FfstError(CHANGED)
        i = index(page)
        if i == -1:
            raise FfstError(f"Aucune demande en brouillon pour {last_name} {first_name}.")
        for _ in range(2):
            page.check(f'[name="_{i}_A1_0"]')
            page.wait_for_timeout(300)
            page.get_by_role("button", name="Supprimer la demande").click()
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(300)
            # The confirmation is a link styled as a button, label doubled.
            page.get_by_role("link", name="Oui").first.click()
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(500)
            i = index(page)
            if i == -1:
                return
        raise FfstError(
            f"La demande de {last_name} {first_name} est toujours dans le panier après deux essais : "
            "à retirer sur le site de la FFST."
        )

    _browser(do)
