"""A link in the carousel (Seb, 9 November): its title and its picture,
read once when the link is added (spec/modules/actualites.md §3.3).

YouTube answers through oEmbed; any other site through its og: tags.
Only public addresses are fetched: a publisher must not be able to make
the server read the inside of the VPS."""

from __future__ import annotations

import ipaddress
import re
import socket
from dataclasses import dataclass
from html import unescape
from urllib.parse import urljoin, urlparse

import requests

TIMEOUT = 8
PAGE_MAX_BYTES = 2 * 1024 * 1024
IMAGE_MAX_BYTES = 10 * 1024 * 1024
_YOUTUBE = re.compile(
    r"^https?://(?:www\.|m\.)?(?:youtube\.com/(?:watch\?(?:.*&)?v=|shorts/|embed/|live/)|youtu\.be/)([\w-]{11})"
)


class LinkError(ValueError):
    """A link that cannot be read."""


@dataclass(frozen=True)
class Preview:
    title: str
    image: bytes | None


def youtube_id(url: str) -> str | None:
    match = _YOUTUBE.match(url.strip())
    return match.group(1) if match else None


def _check_public(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise LinkError("Ce n'est pas un lien web")
    try:
        addresses = {info[4][0] for info in socket.getaddrinfo(parsed.hostname, None)}
    except OSError as erreur:
        raise LinkError("Site introuvable") from erreur
    for address in addresses:
        if not ipaddress.ip_address(address.split("%")[0]).is_global:
            raise LinkError("Site introuvable")


def _fetch(url: str, max_bytes: int) -> tuple[bytes, str]:
    """The body (cut at max_bytes) and the final address. Each redirect is
    checked again."""
    session = requests.Session()
    for _ in range(5):
        _check_public(url)
        response = session.get(url, stream=True, timeout=TIMEOUT, allow_redirects=False,
                               headers={"User-Agent": "Mozilla/5.0 (compatible; Actus)"})
        if response.is_redirect and response.headers.get("location"):
            url = urljoin(url, response.headers["location"])
            response.close()
            continue
        with response:
            response.raise_for_status()
            body = bytearray()
            for block in response.iter_content(64 * 1024):
                body += block
                if len(body) >= max_bytes:
                    break
            return bytes(body[:max_bytes]), url
    raise LinkError("Trop de redirections")


def _meta(html: str, name: str) -> str | None:
    for tag in re.findall(r"<meta\b[^>]*>", html, re.I):
        if re.search(rf"""(?:property|name)\s*=\s*["']{re.escape(name)}["']""", tag, re.I):
            content = re.search(r"""content\s*=\s*(["'])(.*?)\1""", tag, re.I | re.S)
            if content:
                return unescape(content.group(2)).strip()
    return None


def _image(url: str | None) -> bytes | None:
    if not url:
        return None
    try:
        return _fetch(url, IMAGE_MAX_BYTES)[0]
    except (requests.RequestException, LinkError):
        return None


def read(url: str) -> Preview:
    """Raises LinkError."""
    url = url.strip()
    try:
        if youtube_id(url):
            _check_public("https://www.youtube.com/")
            data = requests.get("https://www.youtube.com/oembed", params={"url": url, "format": "json"},
                                timeout=TIMEOUT).json()
            return Preview(title=str(data.get("title", ""))[:300], image=_image(data.get("thumbnail_url")))
        body, final = _fetch(url, PAGE_MAX_BYTES)
    except requests.RequestException as erreur:
        raise LinkError("Ce lien ne répond pas") from erreur
    except ValueError as erreur:  # JSON
        raise LinkError("Ce lien ne répond pas") from erreur
    html = body.decode("utf-8", errors="replace")
    title = _meta(html, "og:title")
    if not title:
        found = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
        title = unescape(found.group(1)).strip() if found else ""
    image = _meta(html, "og:image") or _meta(html, "twitter:image")
    return Preview(title=" ".join(title.split())[:300], image=_image(urljoin(final, image) if image else None))
