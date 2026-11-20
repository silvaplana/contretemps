"""HelloAsso actions opened to the assistant (Seb, 20 November 2026): what
the screens already do, behind a card Faire / Annuler, through the screens'
routes (same rights). Choose how a season uses HelloAsso and its campaign,
copy the members now, mail members (the unpaid ones at once), validate a
member's file or check them all, and the « Nouveaux adhérents » settings.

Left to the screens: the connection (keys), cancelling a membership at
HelloAsso (final, money), and the text message, which leaves from the
person's phone.
"""

from __future__ import annotations

from typing import Literal

from assistant.actions import Action
from assistant.modifications import Ligne, Refus
from comptes import Compte, rbac
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from . import contact
from . import members as imposed_members
from .api import HelloAssoError
from .campaign import Campaigns
from .lectures import MODES, SEASON, in_season, season
from .receiver import CampaignIn, HelloAssoReceiver, SeasonIn
from .verification import ChecksReceiver, SettingsIn

MAIL_MAX = 60


class SeasonMode(BaseModel):
    season: str | None = SEASON
    mode: Literal["master", "payment", "none"] = Field(
        description="master : « HelloAsso fait tout » (avec sa campagne) ; payment : « L'appli fait tout, HelloAsso "
        "encaisse » ; none : « Sans HelloAsso »."
    )
    campaign: str | None = Field(default=None, description="Avec master : nom (ou bout de nom) de la campagne HelloAsso (voir helloasso_campaign).")


class SeasonOnly(BaseModel):
    season: str | None = SEASON


class Mail(BaseModel):
    season: str | None = SEASON
    member_ids: list[int] = Field(default=[], max_length=MAIL_MAX, description="Numéros des fiches des adhérents (voir helloasso_members).")
    unpaid: bool = Field(default=False, description="true : à tous les adhérents qui ont un impayé (relance des impayés).")
    template_id: int | None = Field(default=None, description="Numéro d'un message préenregistré (mail), ou null pour subject et message.")
    subject: str = Field(default="", max_length=255, description="Objet.")
    message: str = Field(default="", max_length=20000, description="Message ; {prénom} et {nom} sont remplacés pour chacun.")


class Files(BaseModel):
    validate_ids: list[int] = Field(default=[], max_length=100, description="Fiches dont on valide le dossier (« Valider le dossier »).")
    unvalidate_ids: list[int] = Field(default=[], max_length=100, description="Fiches dont on annule la validation.")
    check_all: bool = Field(default=False, description="« Vérifier les adhérents » : relancer la vérification des dossiers pas OK (Accès au Financier).")


class NewMembers(BaseModel):
    notify_new: bool | None = Field(default=None, description="« Prévenir les administrateurs à chaque nouvel adhérent », ou null pour ne pas changer.")
    check_files: bool | None = Field(default=None, description="« Vérifier le dossier de chaque adhérent », ou null pour ne pas changer.")


def _yes(on: bool) -> str:
    return "oui" if on else "non"


def actions(receiver: HelloAssoReceiver, checks: ChecksReceiver) -> list[Action]:
    def prepare_mode(db: Session, compte, org_id: int, p: SeasonMode) -> Ligne:
        rbac.require_owner(compte, org_id)
        found = season(db, org_id, p.season)
        if receiver.client.current(db, org_id) is None:
            raise Refus("HelloAsso n’est pas connecté (Admin › École › Connexions)")
        if p.mode != "master":
            def faire_mode(db: Session) -> None:
                with in_season(db, org_id, found):
                    receiver.choisir_saison(org_id, SeasonIn(mode=p.mode), db=db, appelant=compte)

            return Ligne(f"Saison {found.nom} : « {MODES[p.mode]} » (la campagne éventuelle est retirée, "
                         "les réponses restent)", faire_mode)
        if not p.campaign:
            raise Refus("dites quelle campagne (voir helloasso_campaign)")
        try:
            forms = receiver.campaigns.list_forms(db, org_id)
        except HelloAssoError as erreur:
            raise Refus(str(erreur)) from None
        wanted = " ".join(p.campaign.split()).casefold()
        chosen = [f for f in forms if wanted in (f.name.casefold(), f.form_slug.casefold())] or [
            f for f in forms if wanted in f.name.casefold()
        ]
        if len(chosen) != 1:
            raise Refus(f"campagne « {p.campaign} » " + ("introuvable" if not chosen else "ambiguë")
                        + ". Campagnes : " + ", ".join(f.name for f in forms))
        form = chosen[0]

        def faire_campaign(db: Session) -> None:
            with in_season(db, org_id, found):
                receiver.choisir(org_id, CampaignIn(form_type=form.form_type, form_slug=form.form_slug), db=db,
                                 appelant=compte)

        return Ligne(f"Saison {found.nom} : « HelloAsso fait tout », campagne « {form.name} » (ses questions "
                     "passent sur la fiche des membres)", faire_campaign)

    def prepare_sync(db: Session, compte, org_id: int, p: SeasonOnly) -> Ligne:
        rbac.require_admin(compte, org_id)
        found = season(db, org_id, p.season)
        if Campaigns.current(db, found.id) is None:
            raise Refus(f"pas de campagne HelloAsso pour la saison {found.nom}")

        def faire(db: Session) -> None:
            with in_season(db, org_id, found):
                receiver.synchroniser(org_id, db=db, appelant=compte)

        return Ligne(f"Recopier maintenant les adhérents HelloAsso de la saison {found.nom}", faire)

    def prepare_mail(db: Session, compte, org_id: int, p: Mail) -> Ligne:
        rbac.require_admin(compte, org_id)
        if receiver.send_mail is None:
            raise Refus("l’envoi de mails n’est pas configuré sur ce serveur")
        found = season(db, org_id, p.season)
        subject, body = p.subject, p.message
        if p.template_id is not None:
            template = next((t for t in contact.templates(db, org_id, "mail") if t["id"] == p.template_id), None)
            if template is None:
                raise Refus("message préenregistré introuvable (voir helloasso_members, presetMessages)")
            subject, body = subject or template["subject"], body or template["body"]
        subject, body = " ".join(subject.split()), body.strip()
        if not subject or not body:
            raise Refus("l’objet et le message sont obligatoires")
        with in_season(db, org_id, found):
            ids = list(dict.fromkeys(p.member_ids))
            if p.unpaid:
                ids += [m["member_id"] for m in imposed_members.unpaid(db, org_id, found.id)
                        if m["member_id"] is not None and m["member_id"] not in ids]
            if not ids:
                raise Refus("aucun adhérent à qui écrire")
            if len(ids) > MAIL_MAX:
                raise Refus(f"{len(ids)} adhérents : {MAIL_MAX} au plus par envoi")
            recipients = []
            for member_id in ids:
                r = receiver._registration(db, org_id, member_id, compte)
                if not (r.payer_email or "").strip():
                    raise Refus(f"{r.first_name} {r.last_name} n’a pas d’adresse email chez HelloAsso")
                fiche = db.get(Compte, member_id)
                first, last = (fiche.prenom, fiche.nom) if fiche else (r.first_name, r.last_name)
                recipients.append((member_id, f"{first} {last}", r.payer_email,
                                   body.replace("{prénom}", first).replace("{nom}", last)))

        def faire(db: Session) -> None:
            failed = []
            with in_season(db, org_id, found):
                for member_id, name, _, text in recipients:
                    r = receiver._registration(db, org_id, member_id, compte)
                    if contact.send_mail(db, receiver.send_mail, r, subject, text).error:
                        failed.append(name)
            # Mails gone are noted even when another one failed.
            db.commit()
            if failed:
                raise ValueError("le mail n’est pas parti pour " + ", ".join(failed))

        to = ", ".join(f"{name} ({email})" for _, name, email, _ in recipients[:10])
        more = f" et {len(recipients) - 10} autres" if len(recipients) > 10 else ""
        excerpt = body if len(body) <= 300 else body[:300] + "…"
        n = len(recipients)
        return Ligne(
            f"Envoyer un mail à {n} adhérent{'s' if n > 1 else ''} (au payeur, l’école en copie) : {to}{more}. "
            f"Objet « {subject} ». Message : « {excerpt} »",
            faire,
        )

    def prepare_files(db: Session, compte, org_id: int, p: Files) -> Ligne:
        rbac.require_admin(compte, org_id)
        if not (p.validate_ids or p.unvalidate_ids or p.check_all):
            raise Refus("rien à faire : validate_ids, unvalidate_ids ou check_all")
        names, parts = {}, []
        for member_id in [*p.validate_ids, *p.unvalidate_ids]:
            r = receiver._registration(db, org_id, member_id, compte)
            names[member_id] = f"{r.first_name} {r.last_name}"
        if p.validate_ids:
            parts.append("Valider le dossier de " + ", ".join(names[i] for i in p.validate_ids))
        if p.unvalidate_ids:
            parts.append("Annuler la validation du dossier de " + ", ".join(names[i] for i in p.unvalidate_ids))
        if p.check_all:
            state = checks.etat(org_id, db=db, appelant=compte)
            if not state.on:
                raise Refus("la vérification des dossiers n’est pas allumée")
            if not state.can_run:
                raise Refus("vérifier les adhérents demande l’accès au Financier")
            parts.append(f"Vérifier les {state.to_check} dossiers pas encore OK de la saison en cours "
                         "(facturé ; rapport par mail à l’école)")

        def faire(db: Session) -> None:
            for member_id in p.validate_ids:
                checks.valider(org_id, member_id, db=db, appelant=compte)
            for member_id in p.unvalidate_ids:
                checks.devalider(org_id, member_id, db=db, appelant=compte)
            if p.check_all:
                checks.verifier(org_id, db=db, appelant=compte)

        return Ligne(" ; ".join(parts), faire)

    def prepare_new_members(db: Session, compte, org_id: int, p: NewMembers) -> Ligne:
        current = checks.reglages(org_id, db=db, appelant=compte)  # administrateur principal
        wanted = SettingsIn(
            notify_new=current.notify_new if p.notify_new is None else p.notify_new,
            check_files=current.check_files if p.check_files is None else p.check_files,
        )

        def faire(db: Session) -> None:
            checks.regler(org_id, wanted, db=db, appelant=compte)

        return Ligne(
            f"Nouveaux adhérents : prévenir les administrateurs : {_yes(wanted.notify_new)} ; vérifier le dossier "
            f"de chaque adhérent : {_yes(wanted.check_files)}" + (" (chaque vérification est facturée)" if wanted.check_files else ""),
            faire,
        )

    return [
        Action(
            name="set_helloasso_season",
            module="HelloAsso",
            description="Choisir comment une saison utilise HelloAsso, et sa campagne (Admin › École › Saisons › "
            "Éditer la saison ; Admin › Élèves › ⋮ › Champs). Administrateur principal.",
            params=SeasonMode,
            prepare=prepare_mode,
        ),
        Action(
            name="sync_helloasso",
            module="HelloAsso",
            description="« Synchroniser maintenant » / « Rafraîchir » : recopier tout de suite les adhérents "
            "HelloAsso d'une saison qui a sa campagne.",
            params=SeasonOnly,
            prepare=prepare_sync,
        ),
        Action(
            name="mail_helloasso_members",
            module="HelloAsso",
            description="Envoyer un mail à un ou plusieurs adhérents HelloAsso (Admin › Élèves, colonne Contact, "
            "« ✉ Mail ») : au payeur, l'école en copie. unpaid=true : relancer tous les impayés. Le SMS part du "
            "téléphone de la personne, depuis l'écran.",
            params=Mail,
            prepare=prepare_mail,
        ),
        Action(
            name="review_helloasso_files",
            module="HelloAsso",
            description="Vérification des dossiers (Admin › Élèves, colonne Vérification) : « Valider le dossier » "
            "ou l'annuler, et « Vérifier les adhérents » (⋮, Accès au Financier).",
            params=Files,
            prepare=prepare_files,
        ),
        Action(
            name="set_helloasso_new_members",
            module="HelloAsso",
            description="Bloc « Nouveaux adhérents » de la ligne HelloAsso (Admin › École › Connexions › Voir) : "
            "prévenir les administrateurs à chaque nouvel adhérent, vérifier le dossier de chaque adhérent. "
            "Administrateur principal.",
            params=NewMembers,
            prepare=prepare_new_members,
        ),
    ]
