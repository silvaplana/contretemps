"""Reprend les élèves à l'essai de Sambo Admin dans une école (module Essai,
spec/modules/essai.md §8 et §9 étape 3) : chaque inscrit garde son QR code
(même jeton), ses deux cours, son commentaire et ses signatures. Le
certificat médical n'est pas repris (il n'est jamais gardé ici, §6) :
seulement la date à laquelle il avait été fourni.

Sambo Admin n'est jamais touché : la commande lit une COPIE de sa base
(fichier `sambo.db`), ouverte en lecture seule. Relançable : un inscrit déjà
repris (même QR code, ou mêmes prénom, nom et date d'inscription) est sauté.

Si la page d'essai de l'école n'a pas encore été remplie (pas d'horaires, de
salles ni de contacts), elle reçoit aussi les textes de la page d'essai de
Sambo Admin (titre, modalités, horaires, salles, contacts, décharge).

À lancer sur le serveur. 1) Copier la base de Sambo Admin, en lecture
seule (la sauvegarde de SQLite prend aussi ce qui est encore dans son
journal) puis la poser dans le conteneur backend de l'appli :

    cd ~/test-python && docker compose exec backend python -c "import sqlite3; sqlite3.connect('file:/app/data/sambo.db?mode=ro', uri=True).backup(sqlite3.connect('/tmp/sambo.db'))"
    docker compose cp backend:/tmp/sambo.db /tmp/sambo.db
    cd ~/contretemps && docker compose cp /tmp/sambo.db backend:/tmp/sambo.db

2) Lancer la reprise (d'abord avec `--essai`) :

    docker compose exec backend python -m app.reprise_essais --ecole 3 --base /tmp/sambo.db

`--essai` affiche ce qui serait fait, sans rien changer.
"""

from __future__ import annotations

import argparse
import secrets
import sqlite3
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db import SessionLocal
from ecoles.models import Ecole
from trials import TrialSettings, TrialSignature, TrialStudent, TrialTerms
from trials.trials import ADULT_AGE, Trials

# La page d'essai de Sambo Admin (backend/src/trials/content.py, version
# « 2026-09-29c »), écrite pour ASC La Ciotat. {eleve}, {parent} et {club}
# deviennent [élève], [parent] et [club]. Les deux règles sur les mineurs
# sont retirées : la page les écrit elle-même depuis l'âge minimum.
PAGE_SAMBO_ADMIN = {
    "title": "S'inscrire à un cours d'essai gratuit",
    "subtitle": "Sport de combat MMA Sambo – La Ciotat, La Bédoule",
    "intro": (
        "Venez découvrir le sambo et le MMA ! Inscrivez-vous ci-dessous : vous recevrez par e-mail "
        "un QR code à présenter à l'entraîneur au début de votre cours d'essai."
    ),
    "rules": [
        "Le cours d'essai est gratuit et sans engagement.",
        "Un seul cours d'essai par personne.",
        "Vous pouvez inscrire jusqu'à 3 personnes d'une même famille (même adresse e-mail) dans la même demande.",
        "Présentez votre QR code à l'entraîneur au début du cours (sur votre téléphone ou imprimé).",
        "Tenue : short ou jogging, t-shirt, bouteille d'eau. Pas de bijoux. Protège-dents conseillé.",
        "Un certificat médical d'aptitude au sambo est requis (à joindre à l'inscription).",
        "Arrivez 10 minutes avant le début du cours.",
    ],
    "min_age": 9,
    "schedule": [
        {"day": "Lundi", "time": "19h – 21h", "course": "Sambo MMA", "place": "La Bédoule"},
        {"day": "Jeudi", "time": "19h15 – 21h15", "course": "Sambo MMA", "place": "La Ciotat"},
        {"day": "Samedi", "time": "9h – 10h", "course": "Cross training", "place": "La Ciotat"},
        {"day": "Samedi", "time": "10h15 – 12h15", "course": "Sambo MMA", "place": "La Ciotat"},
    ],
    "places": [
        {"name": "La Bédoule", "address": "Salle Marius Aimonetto, allée Hippolyte Gondrexon, 13830 Roquefort-la-Bédoule"},
        {"name": "La Ciotat", "address": "Complexe Étienne Masse, avenue de la Pétanque, 13600 La Ciotat"},
    ],
    "contacts": [{"name": "Roland", "phone": "06 86 13 84 54"}, {"name": "Karima", "phone": "07 66 09 63 68"}],
    "certificate_hint": "Certificat médical d'aptitude au sambo / MMA, obligatoire (photo ou PDF).",
    "parental_consent": (
        "En signant, je soussigné(e), [parent], représentant légal de [élève], donne mon autorisation "
        "pour le cours d'essai de MMA / sambo organisé par [club], et autorise les encadrants à prendre "
        "toute mesure d'urgence nécessaire (appel des secours) en cas d'accident."
    ),
    "waiver": (
        "Je reconnais que le MMA et le sambo sont des sports de combat comportant des risques de "
        "blessure, et que le cours d'essai se fait dans le respect des consignes des encadrants. "
        "Je renonce à tout recours contre [club] et ses encadrants en cas d'accident survenu à [élève] "
        "pendant le cours d'essai, sauf faute de leur part. Je déclare être couvert(e) par une assurance "
        "responsabilité civile."
    ),
}


def _instant(texte: str | None) -> datetime | None:
    """Horodatage ISO de Sambo Admin (UTC) -> datetime sans fuseau, comme nos tables."""
    if not texte:
        return None
    moment = datetime.fromisoformat(texte.replace("Z", "+00:00"))
    return moment.astimezone(timezone.utc).replace(tzinfo=None) if moment.tzinfo else moment


def _jour(texte: str | None) -> date | None:
    return date.fromisoformat(texte[:10]) if texte else None


def _age(ligne: sqlite3.Row) -> int | None:
    """Âge d'un mineur, None pour un majeur (les premiers inscrits de Sambo
    Admin avaient une date de naissance au lieu de l'âge)."""
    age = ligne["age"]
    if age is None and ligne["birth_date"]:
        naissance, inscription = _jour(ligne["birth_date"]), _jour(ligne["created_at"])
        age = inscription.year - naissance.year - ((inscription.month, inscription.day) < (naissance.month, naissance.day))
    return age if age is not None and age < ADULT_AGE else None


def _page_vide(reglages: TrialSettings) -> bool:
    return not (reglages.schedule or reglages.places or reglages.contacts)


def _textes_sambo_admin(db: Session, org_id: int, reglages: TrialSettings, essai: bool) -> TrialTerms | None:
    """La version des textes acceptés dans Sambo Admin (la page la reçoit
    si elle est encore vide)."""
    if _page_vide(reglages) and not essai:
        Trials(send=None, school_address=None).save_settings(db, org_id, PAGE_SAMBO_ADMIN)
    trouve = db.scalar(
        select(TrialTerms).where(
            TrialTerms.org_id == org_id,
            TrialTerms.waiver == PAGE_SAMBO_ADMIN["waiver"],
            TrialTerms.parental_consent == PAGE_SAMBO_ADMIN["parental_consent"],
        )
    )
    if trouve or essai:
        return trouve
    numero = db.scalar(select(func.max(TrialTerms.number)).where(TrialTerms.org_id == org_id)) or 0
    terms = TrialTerms(
        org_id=org_id, number=numero + 1, waiver=PAGE_SAMBO_ADMIN["waiver"], parental_consent=PAGE_SAMBO_ADMIN["parental_consent"]
    )
    db.add(terms)
    db.flush()
    return terms


def reprendre(db: Session, org_id: int, sambo: sqlite3.Connection, essai: bool = False) -> list[str]:
    """Reprend les inscrits ; rend le compte rendu, ligne par ligne."""
    if db.get(Ecole, org_id) is None:
        raise SystemExit(f"Pas d'école n° {org_id}")
    lignes = []
    reglages = Trials(send=None, school_address=None).settings(db, org_id)
    if _page_vide(reglages):
        lignes.append("Page d'essai : textes de Sambo Admin (horaires, salles, contacts, décharge).")
    else:
        lignes.append("Page d'essai déjà remplie : elle ne change pas.")
    terms = _textes_sambo_admin(db, org_id, reglages, essai)

    eleves = sambo.execute("SELECT * FROM trial_students ORDER BY id").fetchall()
    signatures = sambo.execute("SELECT * FROM trial_signatures ORDER BY id").fetchall()
    deja = {(r.first_name, r.last_name, r.created_at) for r in db.scalars(select(TrialStudent).where(TrialStudent.org_id == org_id))}
    jetons = set(db.scalars(select(TrialStudent.token)))
    repris, sautes, familles = 0, 0, {}
    for e in eleves:
        cree = _instant(e["created_at"])
        if e["qr_token"] in jetons or (e["first_name"], e["last_name"], cree) in deja:
            sautes += 1
            continue
        # Les premiers inscrits n'avaient pas de famille : chacun la sienne.
        famille = (e["family_id"] or f"sambo-{e['id']}")[:32]
        familles.setdefault(famille, []).append(e)
        repris += 1
        lignes.append(f"+ {e['first_name']} {e['last_name']}")
        if essai:
            continue
        db.add(
            TrialStudent(
                org_id=org_id,
                first_name=e["first_name"],
                last_name=e["last_name"],
                age=_age(e),
                email=e["email"] or "",
                phone=e["phone"] or None,
                parent_name=e["parent_name"] or None,
                comment=e["comment"] or "",
                family=famille,
                # Pas de QR code (ajouté à la main) : un jeton neuf, jamais envoyé.
                token=e["qr_token"] or secrets.token_urlsafe(16),
                terms_id=terms.id,
                waiver_accepted=bool(e["waiver_accepted"]),
                certificate_at=cree if e["medical_certificate_file"] else None,
                ip=e["signed_ip"],
                created_at=cree,
                course1_date=_jour(e["course1_date"]),
                course1_mode=e["course1_mode"],
                course2_date=_jour(e["course2_date"]),
                course2_mode=e["course2_mode"],
            )
        )

    # Signatures des familles reprises : la table de Sambo Admin, ou, pour les
    # premiers inscrits, celle gardée sur la ligne de l'élève.
    nb_signatures = 0
    for famille, membres in familles.items():
        mineurs = [f"{m['first_name']} {m['last_name']}" for m in membres if _age(m) is not None]
        a_reprendre = [
            (s["signer_name"], s["png"], s["signed_at"], s["signed_ip"], s["role"] == "parent")
            for s in signatures
            if s["family_id"] == famille
        ] or [
            (m["parent_name"] if _age(m) is not None and m["parent_name"] else f"{m['first_name']} {m['last_name']}",
             m["signature_png"], m["signed_at"] or m["created_at"], m["signed_ip"], _age(m) is not None and bool(m["parent_name"]))
            for m in membres
            if m["signature_png"]
        ]
        for nom, png, signe, ip, parent in a_reprendre:
            nb_signatures += 1
            if essai:
                continue
            db.add(
                TrialSignature(
                    org_id=org_id,
                    family=famille,
                    signer_name=nom,
                    # Une signature de parent vaut autorisation pour les mineurs de la demande.
                    children=mineurs if parent else [],
                    png=png,
                    terms_id=terms.id,
                    ip=ip,
                    created_at=_instant(signe),
                )
            )
    if not essai:
        db.commit()
    lignes.append(f"{repris} inscrit(s) repris, {sautes} déjà là, {nb_signatures} signature(s).")
    return lignes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--ecole", type=int, required=True, help="id de l'école")
    parser.add_argument("--base", required=True, help="copie de la base de Sambo Admin (sambo.db)")
    parser.add_argument("--essai", action="store_true", help="n'écrit rien, affiche seulement")
    args = parser.parse_args()
    sambo = sqlite3.connect(f"file:{args.base}?mode=ro", uri=True)
    sambo.row_factory = sqlite3.Row
    with SessionLocal() as db:
        for ligne in reprendre(db, args.ecole, sambo, args.essai):
            print(ligne)
    print("(essai : rien n'a été écrit)" if args.essai else "Reprise terminée.")


if __name__ == "__main__":
    main()
