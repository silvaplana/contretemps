"""A post sent by mail to the members (Seb, 19 November 2026;
spec/modules/actualites.md §12.13): one mail per address through the core's
service (ecoles/mail_ecole.py: envoyer_a_chacun, Brevo), replies to the
club's address, written like an ordinary mail (Seb, 20 November). The
« Ne plus recevoir les actus par mail » page stays for the links of the
mails already sent."""

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

from . import formatting
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


def first_names(db: Session, org_id: int) -> dict[str, str]:
    """Address → « Lou et Léo », for « Bonjour … » at the top of the mail
    (Seb, 20 November: a personal mail, not a newsletter, stays out of
    Gmail's Promotions tab)."""
    season = saison_courante_id(db, org_id)
    names: dict[str, list[str]] = {}
    with toutes_saisons(db):
        members = db.scalars(select(Compte).where(Compte.ecole_id == org_id, Compte.saison_id == season))
        for m in members:
            first = (m.prenom or "").strip()
            for a in m.emails:
                if first and first not in names.setdefault(a, []):
                    names[a].append(first)
    return {a: " et ".join([", ".join(sorted(n)[:-1]), sorted(n)[-1]] if len(n) > 1 else n) for a, n in names.items() if n}


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


# --- The post's document, attached ---

def document_attachment(docs, db: Session, node) -> tuple[str, bytes] | None:
    """(name, bytes) of a post's document: the file as stored in Docs, or
    for a convocation to the AG (a file the app fills), its PDF."""
    from documents import assembly
    from documents.models import DocVersion, StoredFile

    if node.kind == "folder":
        return None
    version = db.get(DocVersion, node.current_version_id or 0)
    stored = db.get(StoredFile, version.stored_file_id) if version is not None else None
    if stored is not None:
        path = docs.storage.path(node.org_id, stored.sha256)
        return (node.name, path.read_bytes()) if path.exists() else None
    app_version = docs.apps.current_version(db, node)
    if app_version is not None and assembly.block_of(app_version.content) is not None:
        school = docs.mailer.org(db, node.org_id)[0] if docs.mailer is not None else ""
        return f"{node.name}.pdf", assembly.convocation_pdf(app_version.content, node.name, school)
    return None


# --- The mail itself ---

def subject(blog: Blog, post: Post, typed: str | None = None) -> str:
    """The « Objet du mail » typed (Seb, 20 November), else the title or the
    first line."""
    if typed:
        return typed
    headline = post.title if blog.with_categories and post.title else (formatting.plain(post.body).strip().splitlines() or [""])[0]
    if len(headline) > SUBJECT_CHARS:
        headline = headline[: SUBJECT_CHARS - 1].rstrip() + "…"
    # No « Actus · » before it: a personal mail (Seb, 20 November).
    return headline or f"Nouveau dans {blog.name}"


def content(blog: Blog, post: Post, school: str, photo: bool, name: str = "", typed_subject: str | None = None):
    """(subject, text, html) for one address, written like an ordinary mail
    (Seb, 20 November: the newsletter look sent it to Gmail's Promotions):
    « Bonjour Prénom, », the post, « Cordialement, », the author and the
    school. Nothing else: no « Lire sur l'appli », no unsubscribe link (the
    addresses already opted out stay out). The post's own links stay, they
    are part of the message."""
    links = [(m.link_title or m.link_url, m.link_url) for m in post.media if m.link_url]
    title = post.title if blog.with_categories and post.title else ""
    hello = f"Bonjour {name}," if name else "Bonjour,"
    signature = ["Cordialement,", post.author_name, school] if post.author_name else ["Cordialement,", school]

    lines = [hello, title, formatting.plain(post.body)]
    lines += [f"{t} : {u}" for t, u in links]
    lines.append("\n".join(signature))
    text = "\n\n".join(x for x in lines if x)

    p = '<p style="margin:0 0 16px;font-size:17px;line-height:1.5">'
    parts = [f"{p}{escape(hello)}</p>"]
    if title:
        parts.append(f"{p}<strong>{escape(title)}</strong></p>")
    if post.body:
        parts.append(f"{p}{formatting.to_html(post.body)}</p>")
    if photo:
        parts.append('<p style="margin:0 0 16px"><img src="cid:photo" alt="" style="display:block;width:100%;max-width:560px"></p>')
    for t, u in links:
        parts.append(f'{p}<a href="{escape(u, True)}">{escape(t)}</a></p>')
    parts.append(f"{p}{'<br>'.join(escape(x) for x in signature)}</p>")
    html = '<div style="font-family:Arial,sans-serif;color:#1f1f1f;max-width:600px">' + "".join(parts) + "</div>"
    return subject(blog, post, typed_subject), text, html
