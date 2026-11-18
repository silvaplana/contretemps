"""Déclaration du module Essai (spec/core.md §11, spec/modules/essai.md).
Éteint dans les écoles existantes (migration du 18 novembre 2026)."""

from personnalisation import brands
from personnalisation.personnalisation import adresse_de_l_ecole
from registry import Module, guide_file

from .receiver import TrialsReceiver
from .trials import Trials, normalize


def mount(app, core) -> None:
    envoi = core.email_envoi

    def send(to, subject, text, html, attachments, images, copy, reply_to, school):
        # Au nom de l'école, depuis l'adresse de son enseigne ; réponses et
        # copie à l'email de contact de l'école.
        brand = brands.of_nature(school.nature)
        envoi.envoyer_confirmation(
            to,
            subject,
            text,
            attachments,
            corps_html=html,
            copie=copy,
            expediteur=(school.nom, brand.sender_email),
            images=images,
            repondre_a=reply_to,
        )

    def member_names(db, org_id):
        return {normalize(f"{c.prenom} {c.nom}") for c in core.eleves_client.list(db, org_id)}

    core.trials_client = Trials(send=send, school_address=adresse_de_l_ecole, member_names=member_names)
    core.trials_receiver = TrialsReceiver(client=core.trials_client, app=app)


MODULE = Module(key="trials", label="Essais", mount=mount, guide=guide_file(__file__))
