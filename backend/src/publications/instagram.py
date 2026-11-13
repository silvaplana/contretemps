"""Relaying an Instagram account into a blog (spec/modules/actualites.md
§6 bis, §12.5): one account per organization, its posts arrive in the blog
where it was linked. The account must be professional (creator or business): Instagram
lets no app read a personal account. The publisher links it with « Se
connecter avec Instagram » when the server has the Meta app (INSTAGRAM_APP_ID,
INSTAGRAM_APP_SECRET, INSTAGRAM_REDIRECT_URL, INSTAGRAM_CONFIG_ID in
backend/.env), or else pastes an access key made in Meta's developer site. Every 5 minutes the worker
(app/relance_worker.py) turns each new post into a Normal post: its
text, then its photos and videos. Only posts published after the link come in.

The button goes through Meta's « Instagram API with Unified Login » (Seb,
11 November 2026: new Meta apps no longer offer Instagram Login): Facebook's
login window with the app's configuration, where one can choose Instagram;
the key never expires and the account is read on graph.facebook.com. A pasted
key goes through « Instagram API with Instagram Login » (graph.instagram.com)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import io
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import requests
from comptes import Compte
from registry import activation
from securite.chiffrement import chiffrer, dechiffrer
from securite.jetons import signatures_egales, signer
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import NORMAL, Blog, InstagramLink, InstagramSettings, Post, PostMedia
from .publications import InvalidMedia, Publications

logger = logging.getLogger(__name__)

GRAPH = "https://graph.instagram.com"
FACEBOOK_GRAPH = "https://graph.facebook.com"
VERSION = "v23.0"
TIMEOUT = 30
VIDEO_MAX_BYTES = 100 * 1024 * 1024
# A key lasts 60 days; renewed well before.
REFRESH_AFTER = timedelta(days=7)
# « Se connecter avec Instagram » (Unified Login: Facebook Login for Business).
AUTHORIZE_URL = "https://www.facebook.com/dialog/oauth"
STATE_SECONDS = 30 * 60
MEDIA_FIELDS = "id,caption,media_type,media_url,timestamp,children{media_type,media_url}"


class InstagramError(Exception):
    """Instagram refused (bad or expired key, account not professional…)."""


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# --- Calls to Instagram (replaced by fakes in the tests) ---


def _get(path: str, host: str = GRAPH, **params) -> dict:
    try:
        reponse = requests.get(f"{host}/{path}", params=params, timeout=TIMEOUT)
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


def _facebook(app: InstagramApp, path: str, token: str, **params) -> dict:
    # appsecret_proof: accepted always, required when the app asks for it.
    proof = hmac.new(app.secret.encode(), token.encode(), hashlib.sha256).hexdigest()
    return _get(f"{VERSION}/{path}", host=FACEBOOK_GRAPH, access_token=token, appsecret_proof=proof, **params)


def fetch_unified_account(app: InstagramApp, token: str) -> dict:
    """The Instagram account the person gave access to: {id, username}."""
    found = _facebook(app, "me/assigned_instagram_accounts", token, fields="id,username").get("data") or []
    if not found:
        # An account reached through a Facebook Page.
        for page in _facebook(app, "me/accounts", token, fields="instagram_business_account{id,username}").get("data") or []:
            if page.get("instagram_business_account"):
                found.append(page["instagram_business_account"])
    if not found:
        raise InstagramError("Aucun compte Instagram professionnel n'a été autorisé")
    return found[0]


def fetch_account_media(app: InstagramApp, token: str, ig_user_id: str) -> list[dict]:
    return _facebook(app, f"{ig_user_id}/media", token, fields=MEDIA_FIELDS, limit=20).get("data", [])


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


@dataclass(frozen=True)
class InstagramApp:
    """The Meta app that « Se connecter avec Instagram » goes through, made
    once by Seb on developers.facebook.com (spec §6 bis)."""

    app_id: str  # the Meta app's ID (Paramètres › Général)
    secret: str
    redirect_url: str  # …/api/news/instagram/return, declared in the Meta app
    config_id: str  # the Unified Login configuration (Cas d'utilisation › API setup with Unified login)

    @classmethod
    def from_env(cls) -> InstagramApp | None:
        keys = ("INSTAGRAM_APP_ID", "INSTAGRAM_APP_SECRET", "INSTAGRAM_REDIRECT_URL", "INSTAGRAM_CONFIG_ID")
        values = [os.environ.get(k, "").strip() for k in keys]
        return cls(*values) if all(values) else None


def exchange_code(app: InstagramApp, code: str) -> str:
    """The code Meta sends back becomes a key (system user: no end date)."""
    data = _get(f"{VERSION}/oauth/access_token", host=FACEBOOK_GRAPH, client_id=app.app_id,
                client_secret=app.secret, redirect_uri=app.redirect_url, code=code)
    if not data.get("access_token"):
        raise InstagramError("Instagram n'a pas donné de clé")
    return data["access_token"]


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _make_state(org_id: int, author_id: int | None, blog_id: int | None = None) -> str:
    """Says who comes back from Instagram, and to which blog: signed by the
    server, 30 minutes."""
    charge = _b64(json.dumps({"o": org_id, "a": author_id, "b": blog_id, "e": int(time.time()) + STATE_SECONDS}).encode())
    return f"{charge}.{signer(charge)}"


def _read_state(state: str) -> tuple[int, int | None, int | None] | None:
    charge, _, signature = state.partition(".")
    if not charge or not signatures_egales(signer(charge), signature):
        return None
    try:
        data = json.loads(base64.urlsafe_b64decode(charge + "=" * (-len(charge) % 4)))
    except ValueError:
        return None
    if data.get("e", 0) < time.time():
        return None
    return data["o"], data.get("a"), data.get("b")


def _has_hashtag(caption: str, hashtag: str) -> bool:
    """#contretemps, but not #contretempsdanse; any case."""
    return re.search(rf"#{re.escape(hashtag)}(?!\w)", caption, re.IGNORECASE) is not None


def _posted_at(post: dict) -> datetime | None:
    try:
        return datetime.strptime(post["timestamp"], "%Y-%m-%dT%H:%M:%S%z").astimezone(timezone.utc).replace(tzinfo=None)
    except (KeyError, ValueError):
        return None


class InstagramRelay:
    def __init__(self, publications: Publications, app: InstagramApp | None = None) -> None:
        self.publications = publications
        self.app = app

    # --- Which posts come in (Seb, 11 November) ---

    def hashtag(self, db: Session, org_id: int) -> str:
        settings = db.get(InstagramSettings, org_id)
        return "" if settings is None else settings.hashtag

    def publishes(self, db: Session, org_id: int) -> bool:
        settings = db.get(InstagramSettings, org_id)
        return True if settings is None else settings.publish

    def change_settings(self, db: Session, org_id: int, hashtag: str | None = None, publish: bool | None = None) -> None:
        settings = db.get(InstagramSettings, org_id)
        if settings is None:
            settings = InstagramSettings(org_id=org_id, hashtag="", publish=True)
            db.add(settings)
        if hashtag is not None:
            settings.hashtag = hashtag.strip().lstrip("#").strip()
        if publish is not None:
            settings.publish = publish
        db.commit()

    def blog_of(self, db: Session, link: InstagramLink) -> Blog:
        """Where its posts arrive: the blog where it was linked, else the
        first blog."""
        blog = db.get(Blog, link.blog_id) if link.blog_id else None
        return blog or self.publications.blogs(db, link.org_id)[0]

    # --- Linking ---

    def login_url(self, org_id: int, author: Compte | None, blog_id: int | None = None) -> str:
        """Where « Se connecter avec Instagram » leads. Raises InstagramError
        if the server has no Meta app."""
        if self.app is None:
            raise InstagramError("La connexion à Instagram n'est pas installée sur le serveur")
        query = urlencode({
            "client_id": self.app.app_id, "config_id": self.app.config_id, "redirect_uri": self.app.redirect_url,
            "response_type": "code", "override_default_response_type": "true", "prompt": "login",
            "state": _make_state(org_id, author.id if author else None, blog_id),
        })
        return f"{AUTHORIZE_URL}?{query}"

    def origin_of(self, state: str) -> tuple[int | None, int | None]:
        """The organization and the blog that asked to link."""
        read = _read_state(state)
        return (read[0], read[2]) if read else (None, None)

    def complete(self, db: Session, code: str, state: str) -> InstagramLink:
        """Back from Instagram: the code becomes a key, and the account is
        linked as if the key had been pasted. Raises InstagramError."""
        read = _read_state(state)
        if read is None or self.app is None:
            raise InstagramError("Connexion expirée : recommencez")
        org_id, author_id, blog_id = read
        token = exchange_code(self.app, code)
        account = fetch_unified_account(self.app, token)
        author = db.get(Compte, author_id) if author_id else None
        return self._keep(db, org_id, blog_id, author, token, account.get("username", ""), ig_user_id=str(account["id"]))

    def get(self, db: Session, org_id: int) -> InstagramLink | None:
        return db.get(InstagramLink, org_id)

    def link(self, db: Session, org_id: int, author: Compte | None, token: str, blog_id: int | None = None) -> InstagramLink:
        """Checks the key with Instagram, then keeps it. Raises InstagramError."""
        token = token.strip()
        return self._keep(db, org_id, blog_id, author, token, fetch_account(token).get("username", ""))

    def _keep(self, db: Session, org_id: int, blog_id: int | None, author: Compte | None, token: str, username: str,
              ig_user_id: str | None = None) -> InstagramLink:
        link = db.get(InstagramLink, org_id) or InstagramLink(org_id=org_id)
        link.blog_id = blog_id
        link.token_encrypted = chiffrer(token)
        link.username = username
        # Unified Login: read by the account's id, the key never expires.
        link.ig_user_id, link.refreshes = ig_user_id, ig_user_id is None
        link.linked_by = author.id if author else None
        link.linked_by_name = author.prenom if author else ""
        link.linked_at = link.token_refreshed_at = _now()
        link.last_sync_at, link.last_error = None, None
        db.add(link)
        db.commit()
        db.refresh(link)
        return link

    def unlink(self, db: Session, org_id: int) -> None:
        link = db.get(InstagramLink, org_id)
        if link is not None:
            db.delete(link)
            db.commit()

    def sync(self, db: Session, link: InstagramLink) -> int:
        """Brings in the new posts; returns how many. Never raises: the
        error is kept on the link and shown in Paramètres d'édition."""
        try:
            token = dechiffrer(link.token_encrypted)
            if token is None:
                raise InstagramError("Clé illisible : à recoller")
            if link.refreshes and _now() - link.token_refreshed_at > REFRESH_AFTER:
                token = refresh_token(token)
                link.token_encrypted, link.token_refreshed_at = chiffrer(token), _now()
            if link.ig_user_id:
                if self.app is None:
                    raise InstagramError("La connexion à Instagram n'est plus installée sur le serveur")
                posts = fetch_account_media(self.app, token, link.ig_user_id)
            else:
                posts = fetch_recent_media(token)
            count = 0
            hashtag = self.hashtag(db, link.org_id)
            # Oldest first, so the newest ends on top of the blog.
            for post in reversed(posts):
                posted_at = _posted_at(post)
                if posted_at is None or posted_at <= link.linked_at or self._known(db, link.org_id, post["id"]):
                    continue
                if hashtag and not _has_hashtag(post.get("caption") or "", hashtag):
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
        """Every linked organization whose Publications module is on (the worker)."""
        result = {}
        for link in list(db.scalars(select(InstagramLink))):
            if "publications" not in activation.disabled(db, link.org_id):
                result[link.org_id] = self.sync(db, link)
        return result

    def _known(self, db: Session, org_id: int, post_id: str) -> bool:
        return db.scalar(select(Post.id).where(Post.org_id == org_id, Post.instagram_id == post_id)) is not None

    def _bring_in(self, db: Session, link: InstagramLink, post: dict) -> None:
        # An album (carousel) brings all its photos and videos, in order.
        elements = (post.get("children", {}).get("data") or []) if post.get("media_type") == "CAROUSEL_ALBUM" else [post]
        media = []
        for element in elements:
            url = element.get("media_url")
            if element.get("media_type") == "IMAGE" and url:
                photo = self.publications.store_photo(link.org_id, io.BytesIO(download(url, 25 * 1024 * 1024)))
                media.append(PostMedia(position=len(media), photo_sha=photo))
            elif element.get("media_type") == "VIDEO" and url:
                video_id = self._store_video(db, link, download(url, VIDEO_MAX_BYTES))
                media.append(PostMedia(position=len(media), video_id=video_id))
        db.add(Post(
            org_id=link.org_id, blog_id=self.blog_of(db, link).id, level=NORMAL, body=(post.get("caption") or "").strip(), notify=False,
            author_id=link.linked_by, author_name=link.signed_by_name or link.linked_by_name,
            published_at=_now() if self.publishes(db, link.org_id) else None,
            media=media, instagram_id=post["id"],
        ))
        db.commit()

    def _store_video(self, db: Session, link: InstagramLink, content: bytes) -> int:
        """Through the Videos module, as if sent from a phone in one block;
        Instagram has already compressed it."""
        videos = self.publications.videos
        upload = videos.creer_televersement(db, link.org_id, ".mp4", len(content))
        videos.ecrire_bloc(db, upload.id, 0, content)
        video = videos.finaliser(db, upload.id, nom="Actualité", uploaded_by=link.linked_by or 0, deja_compresse=True)
        if video is None:
            raise InstagramError("Vidéo non enregistrée")
        return video.id
