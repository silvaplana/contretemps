"""Relaying an Instagram account into the news (spec/modules/actualites.md
§6 bis). The account must be professional (creator or business): Instagram
lets no app read a personal account. The publisher pastes an access key
made in Meta's developer site; every 5 minutes the worker
(app/relance_worker.py) turns each new post into a Normal news item: its
text, then its photo or video. Only posts published after the link come in.

Calls the « Instagram API with Instagram Login » (graph.instagram.com)."""

from __future__ import annotations

import io
import logging
from datetime import datetime, timedelta, timezone

import requests
from comptes import Compte
from registry import activation
from securite.chiffrement import chiffrer, dechiffrer
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import NORMAL, NewsInstagram, NewsItem
from .news import InvalidMedia, News

logger = logging.getLogger(__name__)

GRAPH = "https://graph.instagram.com"
VERSION = "v23.0"
TIMEOUT = 30
VIDEO_MAX_BYTES = 100 * 1024 * 1024
# A key lasts 60 days; renewed well before.
REFRESH_AFTER = timedelta(days=7)
MEDIA_FIELDS = "id,caption,media_type,media_url,timestamp,children{media_type,media_url}"


class InstagramError(Exception):
    """Instagram refused (bad or expired key, account not professional…)."""


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# --- Calls to Instagram (replaced by fakes in the tests) ---


def _get(path: str, **params) -> dict:
    try:
        reponse = requests.get(f"{GRAPH}/{path}", params=params, timeout=TIMEOUT)
    except requests.RequestException as erreur:
        raise InstagramError("Instagram ne répond pas") from erreur
    if reponse.status_code != 200:
        try:
            message = reponse.json()["error"]["message"]
        except (ValueError, KeyError, TypeError):
            message = f"erreur {reponse.status_code}"
        raise InstagramError(f"Instagram a refusé : {message}")
    return reponse.json()


def fetch_account(token: str) -> dict:
    return _get(f"{VERSION}/me", fields="user_id,username", access_token=token)


def fetch_recent_media(token: str) -> list[dict]:
    return _get(f"{VERSION}/me/media", fields=MEDIA_FIELDS, limit=20, access_token=token).get("data", [])


def refresh_token(token: str) -> str:
    return _get("refresh_access_token", grant_type="ig_refresh_token", access_token=token)["access_token"]


def download(url: str, max_bytes: int) -> bytes:
    try:
        with requests.get(url, stream=True, timeout=TIMEOUT) as reponse:
            reponse.raise_for_status()
            contenu = io.BytesIO()
            for bloc in reponse.iter_content(1024 * 1024):
                contenu.write(bloc)
                if contenu.tell() > max_bytes:
                    raise InstagramError("Fichier trop lourd")
            return contenu.getvalue()
    except requests.RequestException as erreur:
        raise InstagramError("Téléchargement impossible") from erreur


def _posted_at(post: dict) -> datetime | None:
    try:
        return datetime.strptime(post["timestamp"], "%Y-%m-%dT%H:%M:%S%z").astimezone(timezone.utc).replace(tzinfo=None)
    except (KeyError, ValueError):
        return None


class InstagramRelay:
    def __init__(self, news: News) -> None:
        self.news = news

    def get(self, db: Session, org_id: int) -> NewsInstagram | None:
        return db.get(NewsInstagram, org_id)

    def link(self, db: Session, org_id: int, author: Compte | None, token: str) -> NewsInstagram:
        """Checks the key with Instagram, then keeps it. Raises InstagramError."""
        token = token.strip()
        account = fetch_account(token)
        link = db.get(NewsInstagram, org_id) or NewsInstagram(org_id=org_id)
        link.token_encrypted = chiffrer(token)
        link.username = account.get("username", "")
        link.linked_by = author.id if author else None
        link.linked_by_name = author.prenom if author else ""
        link.linked_at = link.token_refreshed_at = _now()
        link.last_sync_at, link.last_error = None, None
        db.add(link)
        db.commit()
        db.refresh(link)
        return link

    def unlink(self, db: Session, org_id: int) -> None:
        link = db.get(NewsInstagram, org_id)
        if link is not None:
            db.delete(link)
            db.commit()

    def sync(self, db: Session, link: NewsInstagram) -> int:
        """Brings in the new posts; returns how many. Never raises: the
        error is kept on the link and shown in Paramètres d'édition."""
        try:
            token = dechiffrer(link.token_encrypted)
            if token is None:
                raise InstagramError("Clé illisible : à recoller")
            if _now() - link.token_refreshed_at > REFRESH_AFTER:
                token = refresh_token(token)
                link.token_encrypted, link.token_refreshed_at = chiffrer(token), _now()
            count = 0
            # Oldest first, so the newest ends on top of the news.
            for post in reversed(fetch_recent_media(token)):
                posted_at = _posted_at(post)
                if posted_at is None or posted_at <= link.linked_at or self._known(db, link.org_id, post["id"]):
                    continue
                self._bring_in(db, link, post)
                count += 1
            link.last_sync_at, link.last_error = _now(), None
            db.commit()
            return count
        except (InstagramError, InvalidMedia) as erreur:
            db.rollback()
            link.last_error = str(erreur)
            db.commit()
            logger.warning("Instagram relay, organization %s: %s", link.org_id, erreur)
            return 0

    def sync_all(self, db: Session) -> dict[int, int]:
        """Every linked organization whose news module is on (the worker)."""
        result = {}
        for link in list(db.scalars(select(NewsInstagram))):
            if "news" not in activation.disabled(db, link.org_id):
                result[link.org_id] = self.sync(db, link)
        return result

    def _known(self, db: Session, org_id: int, post_id: str) -> bool:
        return db.scalar(select(NewsItem.id).where(NewsItem.org_id == org_id, NewsItem.instagram_id == post_id)) is not None

    def _bring_in(self, db: Session, link: NewsInstagram, post: dict) -> None:
        media = post
        if post.get("media_type") == "CAROUSEL_ALBUM":
            # An album: its first photo or video.
            media = (post.get("children", {}).get("data") or [{}])[0]
        photo = video_id = None
        if media.get("media_type") == "IMAGE" and media.get("media_url"):
            photo = self.news.store_photo(link.org_id, io.BytesIO(download(media["media_url"], 25 * 1024 * 1024)))
        elif media.get("media_type") == "VIDEO" and media.get("media_url"):
            video_id = self._store_video(db, link, download(media["media_url"], VIDEO_MAX_BYTES))
        now = _now()
        db.add(NewsItem(
            org_id=link.org_id, level=NORMAL, body=(post.get("caption") or "").strip(), notify=False,
            author_id=link.linked_by, author_name=link.linked_by_name, published_at=now,
            photo_sha=photo, video_id=video_id, instagram_id=post["id"],
        ))
        db.commit()

    def _store_video(self, db: Session, link: NewsInstagram, content: bytes) -> int:
        """Through the Videos module, as if sent from a phone in one block;
        Instagram has already compressed it."""
        videos = self.news.videos
        upload = videos.creer_televersement(db, link.org_id, ".mp4", len(content))
        videos.ecrire_bloc(db, upload.id, 0, content)
        video = videos.finaliser(db, upload.id, nom="Actualité", uploaded_by=link.linked_by or 0, deja_compresse=True)
        if video is None:
            raise InstagramError("Vidéo non enregistrée")
        return video.id
