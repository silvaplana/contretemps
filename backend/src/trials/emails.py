"""Le mail de confirmation d'une inscription à l'essai (spec/modules/essai.md
§3) : un QR code par personne, modalités, horaires, informations
renseignées, signatures. Les images sont dans le mail (cid:qr-0,
cid:signature-0…) ; les certificats médicaux en pièces jointes."""

from __future__ import annotations

from html import escape

from . import content


def _person(student) -> str:
    return f"{student.first_name} {student.last_name}"


def confirmation_email(club: str, settings, terms, students, statuses, signatures) -> tuple[str, str, str]:
    """(objet, texte, html)."""
    subject = f"Cours d'essai : {_person(students[0])}"
    lines = [
        "Votre cours d'essai gratuit",
        "",
        "Présentez le QR code de chaque personne au prof au début du cours.",
        "",
    ]
    qr_html = []
    for i, (s, status) in enumerate(zip(students, statuses)):
        already = " (déjà inscrit·e : même QR code)" if status == "existing" else ""
        lines.append(f"- {_person(s)}{already}")
        qr_html.append(
            f'<figure style="display:inline-block;margin:0 12px 12px 0;text-align:center">'
            f'<img src="cid:qr-{i}" width="200" height="200" alt="QR code de {escape(_person(s))}">'
            f'<figcaption style="font-weight:bold">{escape(_person(s))}{escape(already)}</figcaption></figure>'
        )
    rules = settings.rules or []
    schedule = [" ".join(v for v in (x.get("day"), x.get("time"), x.get("course"), x.get("place")) if v) for x in settings.schedule]
    places = [f"{p.get('name')} : {p.get('address')}" for p in settings.places]
    if rules:
        lines += ["", "Modalités", *[f"- {r}" for r in rules]]
    if schedule:
        lines += ["", "Horaires d'entraînement", *[f"- {s}" for s in schedule]]
    if places:
        lines += ["", "Salles", *[f"- {p}" for p in places]]

    infos = []
    for s in students:
        age = f"{s.age} ans" if s.age is not None else "majeur·e"
        parent = f", parent : {s.parent_name}" if s.parent_name else ""
        infos.append(f"{_person(s)} : {age}{parent} ; décharge acceptée (version {terms.number})")
    lines += ["", "Informations renseignées", *[f"- {x}" for x in infos]]
    signed = [f"Signé par {sig.signer_name}" + (f" (autorisation parentale pour {', '.join(sig.children)})" if sig.children else "") for sig in signatures]
    lines += ["", *signed, "", "Les certificats médicaux sont joints à ce mail. Le club ne les garde pas dans son application."]
    text = "\n".join(lines)

    def ul(items):
        return "<ul>" + "".join(f"<li>{escape(x)}</li>" for x in items) + "</ul>"

    sig_html = "".join(
        f'<p style="margin:12px 0 4px">{escape(label)}</p>'
        f'<img src="cid:signature-{i}" width="280" alt="Signature" style="border:1px solid #ccc;max-width:100%;height:auto">'
        for i, label in enumerate(signed)
    )
    waiver = content.fill(terms.waiver, ", ".join(_person(s) for s in students), club=club)
    html = f"""<!doctype html>
<html lang="fr"><body style="font-family:Arial,sans-serif;font-size:16px;color:#111;max-width:620px">
<h1 style="font-size:22px">Votre cours d'essai gratuit</h1>
<p>Présentez le QR code de chaque personne au prof au début du cours.</p>
{''.join(qr_html)}
{f'<h2 style="font-size:17px">Modalités</h2>{ul(rules)}' if rules else ''}
{f'<h2 style="font-size:17px">Horaires d’entraînement</h2>{ul(schedule)}' if schedule else ''}
{f'<h2 style="font-size:17px">Salles</h2>{ul(places)}' if places else ''}
<h2 style="font-size:17px">Informations renseignées</h2>{ul(infos)}
<p style="font-size:14px;color:#444"><strong>Décharge de responsabilité :</strong> {escape(waiver)}</p>
{sig_html}
<p style="font-size:14px;color:#666;margin-top:20px">Les certificats médicaux sont joints à ce mail. {escape(club)} ne les garde pas dans son application.</p>
</body></html>"""
    return subject, text, html
