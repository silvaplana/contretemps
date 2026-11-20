"""Un mail à chacun, au nom de l'école (ecoles/mail_ecole.py : envoyer_a_chacun) :
le service du core pour écrire aux adhérents (Seb, 19 novembre 2026)."""

from ecoles import Ecoles, mail_ecole


class FauxEnvoi:
    actif = True
    repondre_a = None

    def __init__(self):
        self.envoyes = []

    def envoyer_confirmation(self, destinataire, sujet, corps, pieces, corps_html=None, copie=None,
                             expediteur=None, images=None, repondre_a=None):
        if destinataire == "panne@exemple.fr":
            raise OSError("refusé")
        self.envoyes.append(dict(a=destinataire, sujet=sujet, texte=corps, html=corps_html, copie=copie,
                                 expediteur=expediteur, images=images, repondre_a=repondre_a))


def test_un_mail_a_chacun_reponses_au_club(db_session, monkeypatch):
    ecole = Ecoles().create(db_session, nom="ASC La Ciotat", code_postal="13600")
    ecole.email_contact = "contact@asc.fr"
    db_session.commit()
    faux = FauxEnvoi()
    monkeypatch.setattr(mail_ecole, "_envoi", faux)

    envoyes = mail_ecole.envoyer_a_chacun(
        db_session, ecole.id, ["a@exemple.fr", "panne@exemple.fr", "b@exemple.fr"],
        lambda adresse: ("Sujet", f"Bonjour {adresse}", f"<p>{adresse}</p>"),
        images=[("photo", b"\xff\xd8\xffjpeg")],
    )

    # Un mail par adresse, personne ne voit les autres ; une panne n'arrête pas l'envoi.
    assert envoyes == ["a@exemple.fr", "b@exemple.fr"]
    assert [m["a"] for m in faux.envoyes] == ["a@exemple.fr", "b@exemple.fr"]
    premier = faux.envoyes[0]
    assert premier["texte"] == "Bonjour a@exemple.fr" and premier["html"] == "<p>a@exemple.fr</p>"
    # Au nom de l'école, réponses vers son adresse de contact, sans copie.
    assert premier["expediteur"][0] == "ASC La Ciotat"
    assert premier["repondre_a"] == "contact@asc.fr" and premier["copie"] is None
    assert premier["images"] == [("photo", b"\xff\xd8\xffjpeg")]

    # Un autre module peut choisir l'adresse de réponse (Mail : la boîte de « De »).
    faux.envoyes.clear()
    mail_ecole.envoyer_a_chacun(db_session, ecole.id, ["a@exemple.fr"], lambda a: ("S", "T", "<p>T</p>"),
                                repondre_a="bureau@asc.fr")
    assert faux.envoyes[0]["repondre_a"] == "bureau@asc.fr"


def test_aucun_mail_parti_le_dit(db_session, monkeypatch):
    """Seb, 20 novembre : « Essai envoyé » s'affichait alors que rien n'était
    parti. Si aucune adresse n'est servie, l'erreur remonte avec sa raison."""
    import pytest

    ecole = Ecoles().create(db_session, nom="ASC La Ciotat", code_postal="13600")
    db_session.commit()
    monkeypatch.setattr(mail_ecole, "_envoi", FauxEnvoi())
    with pytest.raises(RuntimeError, match="refusé"):
        mail_ecole.envoyer_a_chacun(db_session, ecole.id, ["panne@exemple.fr"], lambda a: ("S", "T", "<p>T</p>"))
