"""A post sent by mail to the members (Seb, 19 November 2026;
spec/modules/actualites.md §12.13), like the newsletters of Substack or Ghost:
one mail per address through the core's service (ecoles/mail_ecole.py:
envoyer_a_chacun, Brevo), replies to the club's address, a « Lire sur
l'appli » button, and « Ne plus recevoir les actus par mail »."""

from __future__ import annotations

import base64
from html import escape

from comptes import Compte
from comptes.models import separer_emails
from saisons.portee import toutes_saisons
from saisons.saisons import saison_courante_id
from securite import jetons
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Blog, MailOptOut, Post

SUBJECT_CHARS = 80


class InvalidMail(ValueError):
    """A mail that cannot leave (no club address, a wrong test address…)."""


def clean_addresses(addresses: str | None) -> list[str]:
    """One address or several (« , », « ; » or spaces), like in Gmail."""
    found = separer_emails(addresses or "")
    if not found or any("@" not in a for a in found):
        raise InvalidMail("Écrivez une adresse mail")
    return found


def recipients(db: Session, blog: Blog, can_read) -> list[str]:
    """One address per family, sorted: the members of the current season who
    read the blog, without those who asked for no more mails."""
    season = saison_courante_id(db, blog.org_id)
    with toutes_saisons(db):
        members = list(db.scalars(select(Compte).where(Compte.ecole_id == blog.org_id, Compte.saison_id == season)))
        addresses = {a for m in members if can_read(m, blog) for a in m.emails}
    out = set(db.scalars(select(MailOptOut.email).where(MailOptOut.org_id == blog.org_id)))
    return sorted(addresses - out)


def people(db: Session, org_id: int) -> list[tuple[str, str]]:
    """(name, address) of everyone in the school this season, administrators,
    teachers and pupils, to complete the address of a test (Seb, 19 November)."""
    season = saison_courante_id(db, org_id)
    with toutes_saisons(db):
        members = db.scalars(select(Compte).where(Compte.ecole_id == org_id, Compte.saison_id == season))
        found = {(f"{m.prenom} {m.nom}".strip(), a) for m in members for a in m.emails}
    return sorted(found)


# --- « Ne plus recevoir les actus par mail » ---

def optout_token(org_id: int, address: str) -> str:
    charge = f"{org_id}:{address}"
    code = base64.urlsafe_b64encode(charge.encode()).decode().rstrip("=")
    return f"{code}.{jetons.signer(f'pub-optout:{charge}')}"


def read_token(token: str) -> tuple[int, str] | None:
    code, _, signature = token.partition(".")
    try:
        charge = base64.urlsafe_b64decode(code + "=" * (-len(code) % 4)).decode()
        org, address = charge.split(":", 1)
        org_id = int(org)
    except ValueError:
        return None
    if not jetons.signatures_egales(jetons.signer(f"pub-optout:{charge}"), signature):
        return None
    return org_id, address


def opt_out(db: Session, org_id: int, address: str, out: bool) -> None:
    row = db.get(MailOptOut, (org_id, address))
    if out and row is None:
        db.add(MailOptOut(org_id=org_id, email=address))
    if not out and row is not None:
        db.delete(row)
    db.commit()


def optout_page(school: str, out: bool) -> str:
    """The page the link opens: gros et simple, « Annuler » to come back."""
    if out:
        title = "Vous ne recevrez plus les actus par mail"
        text = (f"Elles restent dans l’appli de {escape(school)}. Les autres mails du club "
                "(inscription, AG…) continuent d’arriver.")
        button = '<form method="post"><button type="submit">Annuler</button></form>'
    else:
        title = "Vous recevrez de nouveau les actus par mail"
        text, button = "", ""
    return (
        '<!doctype html><html lang="fr"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{escape(school)}</title><style>"
        "body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;"
        "font-family:Roboto,system-ui,sans-serif;background:#f4f4f2;color:#1f1f1f;text-align:center}"
        "main{max-width:420px;padding:32px;display:flex;flex-direction:column;gap:20px;align-items:center}"
        "h1{font-size:24px;margin:0}p{font-size:17px;line-height:1.5;margin:0}"
        "button{min-height:52px;padding:0 28px;border-radius:26px;border:1px solid #c9c9c9;background:#fff;"
        "font-size:17px;font-weight:700;cursor:pointer}</style></head><body><main>"
        f"<strong>{escape(school)}</strong><h1>{title}</h1><p>{text}</p>{button}</main></body></html>"
    )


# --- The mail itself ---

def subject(blog: Blog, post: Post) -> str:
    headline = post.title if blog.with_categories and post.title else (post.body.strip().splitlines() or [""])[0]
    if len(headline) > SUBJECT_CHARS:
        headline = headline[: SUBJECT_CHARS - 1].rstrip() + "…"
    return f"{blog.name} · {headline}" if headline else f"Nouveau dans {blog.name}"


def content(blog: Blog, post: Post, school: str, app_url: str, address: str, photo: bool):
    """(subject, text, html) for one address. « Lire sur l'appli » only for a
    published post; a mail alone (still a draft) has none."""
    optout = f"{app_url}/api/publications/desinscription/{optout_token(post.org_id, address)}"
    read = post.published_at is not None
    links = [(m.link_title or m.link_url, m.link_url) for m in post.media if m.link_url]
    title = post.title if blog.with_categories and post.title else ""

    lines = [title, post.body] if title else [post.body]
    lines += [f"{t} : {u}" for t, u in links]
    if read:
        lines.append(f"Lire sur l’appli : {app_url}")
    lines.append(f"Vous recevez ce mail parce que vous êtes adhérent de {school}. Pour répondre, répondez à ce mail.")
    lines.append(f"Ne plus recevoir les actus par mail : {optout}")
    text = "\n\n".join(x for x in lines if x)

    parts = []
    if title:
        parts.append(f'<h1 style="margin:0;font-size:21px">{escape(title)}</h1>')
    if post.body:
        body = escape(post.body).replace("\n", "<br>")
        parts.append(f'<p style="margin:0;font-size:17px;line-height:1.5">{body}</p>')
    if photo:
        parts.append('<img src="cid:photo" alt="" style="display:block;width:100%;max-width:560px;border-radius:10px">')
    for t, u in links:
        parts.append(f'<p style="margin:0;font-size:17px"><a href="{escape(u, True)}">{escape(t)}</a></p>')
    if read:
        parts.append(
            f'<p style="margin:0"><a href="{escape(app_url, True)}" style="display:inline-block;padding:14px 22px;'
            'border-radius:24px;background:#17181c;color:#ffffff;font-size:17px;font-weight:700;'
            'text-decoration:none">Lire sur l’appli</a></p>'
        )
    if post.author_name:
        parts.append(f'<p style="margin:0;font-size:15px;color:#5f6368">{escape(post.author_name)}</p>')
    html = (
        '<div style="background:#f4f4f2;padding:20px 12px;font-family:Roboto,Arial,sans-serif;color:#1f1f1f">'
        '<div style="max-width:600px;margin:0 auto;background:#ffffff;border:1px solid #e3e3e3;border-radius:12px;'
        'padding:20px;display:block">'
        f'<p style="margin:0 0 16px;font-size:17px;font-weight:700">{escape(school)} · {escape(blog.name)}</p>'
        + '<div style="height:16px"></div>'.join(parts)
        + "</div>"
        '<p style="max-width:600px;margin:16px auto 0;font-size:14px;line-height:1.5;color:#5f6368;text-align:center">'
        f"Vous recevez ce mail parce que vous êtes adhérent de {escape(school)}.<br>"
        "Pour répondre, répondez simplement à ce mail.<br>"
        f'<a href="{escape(optout, True)}" style="color:#1a5fb4">Ne plus recevoir les actus par mail</a></p></div>'
    )
    return subject(blog, post), text, html
