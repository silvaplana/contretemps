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
import re
import threading
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass

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
