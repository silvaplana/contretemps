"""Outils de l'assistant pour lire les données de l'école (Seb, 16 octobre) :
élèves, cours, professeurs, présences, heures des profs, chorégraphies,
inscriptions en ligne, saisons. En LECTURE seule.

Chaque outil respecte les droits de la personne, comme l'appli :
- admin (ou Super User) : toute l'école ;
- professeur : ses cours et leurs élèves, sans les paiements ;
- élève : lui-même et sa famille.
La saison est celle affichée dans l'appli (filtre de saison automatique,
voir saisons/portee.py).

Jamais transmis à l'assistant (Seb) : la santé (allergies, traitement,
informations importantes). Le commentaire de l'administration et le
surlignage rouge d'Admin > Élèves : aux admins et au Super User seulement
(Seb, 16 octobre)."""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from dataclasses import dataclass

from choregraphies.models import Choregraphie, choregraphies_eleves, choregraphies_videos
from comptes import roles
from comptes.models import Compte
from cours.models import Cours, cours_professeurs, eleves_cours
from ecoles.models import Ecole
from eleves.eleves import calculer_age
from eleves.models import ContactEleve, ProfilEleve
from inscriptions.models import Inscription
from messagerie.models import Conversation, ConversationMembre
from presence.models import PresenceEleve, PresenceProf, SeancePresence
from saisons.models import Saison
from saisons.portee import toutes_saisons
from saisons.saisons import saison_courante_id
from sqlalchemy import func, select
from sqlalchemy.orm import Session

LIGNES_MAX = 300


def _prop(type_, description, **autres):
    return {"type": type_, "description": description, **autres}


def _outil(nom: str, description: str, proprietes: dict) -> dict:
    return {
        "name": nom,
        "description": description,
        "strict": True,
        "eager_input_streaming": True,
        "input_schema": {
            "type": "object",
            "properties": proprietes,
            "required": list(proprietes),
            "additionalProperties": False,
        },
    }


COURS = _prop(["integer", "null"], "Numéro du cours, ou null pour tous.")
OUTILS_DONNEES = [
    _outil("resume_ecole", "Vue d'ensemble de l'école sur la saison : nombre d'élèves, de profs, de cours, paiements.", {}),
    _outil("lister_cours", "Les cours : discipline, niveau, jour et horaires, salle, professeurs, nombre d'élèves.", {}),
    _outil("lister_eleves",
           "Les élèves (prénom nom, âge, cours, paiement, contact). Filtres facultatifs : un cours, un bout de nom, "
           "un statut de paiement (en_cours ou paye).",
           {"cours_id": COURS, "nom": _prop(["string", "null"], "Bout de nom ou prénom, ou null."),
            "statut_paiement": _prop(["string", "null"], "en_cours, paye, ou null.")}),
    _outil("fiche_eleve", "Tout sur un élève : date de naissance, adresse, cours, contacts, paiement, présences, chorégraphies.",
           {"eleve_id": _prop("integer", "Numéro de l'élève.")}),
    _outil("lister_professeurs", "Les professeurs : contact et cours donnés.", {}),
    _outil("presences",
           "Présences d'un cours (ou de tous) entre deux dates : séances, présents, absents, retards, et taux par élève.",
           {"cours_id": COURS,
            "date_debut": _prop(["string", "null"], "AAAA-MM-JJ, ou null pour le début de la saison."),
            "date_fin": _prop(["string", "null"], "AAAA-MM-JJ, ou null pour aujourd'hui.")}),
    _outil("heures_professeurs",
           "Heures réellement faites par les professeurs (séances, horaires réels, dépassements), par mois.",
           {"professeur_id": _prop(["integer", "null"], "Numéro du professeur, ou null pour tous."),
            "mois": _prop(["string", "null"], "AAAA-MM, ou null pour toute la saison.")}),
    _outil("lister_choregraphies", "Les chorégraphies : cours, élèves, costume, horaire de répétition, nombre de vidéos.",
           {"cours_id": COURS}),
    _outil("lister_inscriptions_en_ligne",
           "Les fiches d'inscription reçues par la page publique : élève, date, moyen et statut de paiement, montants.", {}),
    _outil("lister_saisons", "Les saisons de l'école (nom, dates, laquelle est en cours).", {}),
    _outil("lister_personnes",
           "Toutes les personnes de l'école avec leurs rôles (élève, professeur, administrateur, trésorier, "
           "administrateur principal), plus les Super Users, qu'on peut ajouter aux groupes. Filtre facultatif : un rôle.",
           {"role": _prop(["string", "null"], "eleve, professeur, admin, tresorier, owner (administrateur principal), "
                          "superuser, ou null pour tous.")}),
    _outil("infos_ecole", "Les coordonnées de l'école (Admin > École) : nom, adresse, SIRET, IBAN, emails, adresse de l'appli.", {}),
    _outil("lister_groupes", "Les groupes de la messagerie (Admin > Messages) et leurs membres (personnes et cours).", {}),
]
NOMS = {o["name"] for o in OUTILS_DONNEES}
# Hors admins (un professeur) : seulement ce que ses écrans montrent (Seb,
# 16 octobre : « pas plus qu'en cliquant ») : ses cours, leurs élèves (nom et
# cours), leurs présences, ses propres heures, leurs chorégraphies. Pas de
# fiche élève, de contacts, d'âge, de paiements, ni des autres profs.
POUR_TOUS = {"resume_ecole", "lister_cours", "lister_eleves", "presences", "heures_professeurs", "lister_choregraphies"}


@dataclass
class Perimetre:
    ecole_id: int
    tout: bool  # admin ou Super User
    cours_ids: set[int] | None  # None : tous
    eleve_ids: set[int] | None  # None : tous
    paiements: bool
    compte_id: int | None = None  # la personne (un prof ne voit que ses heures)


# Colonnes d'Admin > Élèves qu'on peut mettre en rouge (AdminEleves.jsx).
COLONNES_ROUGES = {
    "nom": "élève", "cours": "cours suivis", "paiement": "paiement", "commentaire": "commentaire",
    "naissance": "date de naissance", "age": "âge", "contacts": "contacts", "telephone": "téléphone",
    "email": "email", "adresse": "adresse", "sante": "santé", "certificat": "certificat médical",
}


def _nom(c: Compte) -> str:
    return f"{c.prenom} {c.nom}".strip()


# Noms des rôles à l'écran (spec/core.md §4).
NOMS_ROLES = {
    roles.ELEVE: "élève", roles.PROFESSEUR: "professeur", roles.ADMIN: "administrateur",
    roles.TRESORIER: "trésorier", roles.OWNER: "administrateur principal", roles.SUPERUSER: "Super User",
}


class DonneesEcole:
    def perimetre(self, db: Session, compte: Compte, ecole_id: int) -> Perimetre:
        if roles.is_superuser(compte) or roles.is_admin(compte) or roles.is_owner(compte):
            return Perimetre(ecole_id, True, None, None, True)
        if roles.is_prof(compte):
            cours = set(db.scalars(select(cours_professeurs.c.cours_id).where(cours_professeurs.c.professeur_id == compte.id)))
            eleves = set(db.scalars(select(eleves_cours.c.eleve_id).where(eleves_cours.c.cours_id.in_(cours)))) if cours else set()
            return Perimetre(ecole_id, False, cours, eleves, False, compte.id)
        famille = {compte.id}
        if compte.famille_id:
            famille |= set(db.scalars(select(Compte.id).where(Compte.famille_id == compte.famille_id)))
        cours = set(db.scalars(select(eleves_cours.c.cours_id).where(eleves_cours.c.eleve_id.in_(famille))))
        return Perimetre(ecole_id, False, cours, famille, True)

    def executer(self, db: Session, compte: Compte, ecole_id: int, nom: str, args: dict) -> str:
        p = self.perimetre(db, compte, ecole_id)
        if not p.tout and nom not in POUR_TOUS:
            return "Réservé aux administrateurs."
        return getattr(self, f"_{nom}")(db, p, **args)

    # --- Aides ---------------------------------------------------------

    def _eleves(self, db: Session, p: Perimetre) -> list[Compte]:
        requete = (
            select(Compte)
            .where(Compte.ecole_id == p.ecole_id, Compte.roles.any(role=roles.ELEVE))
            .order_by(Compte.nom, Compte.prenom)
        )
        if p.eleve_ids is not None:
            requete = requete.where(Compte.id.in_(p.eleve_ids or {-1}))
        return list(db.scalars(requete))

    def _cours(self, db: Session, p: Perimetre) -> list[Cours]:
        requete = select(Cours).where(Cours.ecole_id == p.ecole_id).order_by(Cours.ordre, Cours.id)
        if p.cours_ids is not None:
            requete = requete.where(Cours.id.in_(p.cours_ids or {-1}))
        return list(db.scalars(requete))

    def _cours_par_eleve(self, db: Session, eleve_ids: list[int]) -> dict[int, list[str]]:
        resultat: dict[int, list[str]] = defaultdict(list)
        if eleve_ids:
            for eleve_id, nom in db.execute(
                select(eleves_cours.c.eleve_id, Cours.nom)
                .join(Cours, Cours.id == eleves_cours.c.cours_id)
                .where(eleves_cours.c.eleve_id.in_(eleve_ids))
            ):
                resultat[eleve_id].append(nom)
        return resultat

    def _profils(self, db: Session, eleve_ids: list[int]) -> dict[int, ProfilEleve]:
        if not eleve_ids:
            return {}
        return {pr.compte_id: pr for pr in db.scalars(select(ProfilEleve).where(ProfilEleve.compte_id.in_(eleve_ids)))}

    @staticmethod
    def _date(texte: str | None, defaut: dt.date) -> dt.date:
        try:
            return dt.date.fromisoformat(texte) if texte else defaut
        except ValueError:
            return defaut

    # --- Outils --------------------------------------------------------

    def _resume_ecole(self, db: Session, p: Perimetre) -> str:
        eleves = self._eleves(db, p)
        cours = self._cours(db, p)
        lignes = [f"{len(eleves)} élèves, {len(cours)} cours."]
        if p.tout:
            profs = db.scalar(
                select(func.count()).select_from(Compte).where(Compte.ecole_id == p.ecole_id, Compte.roles.any(role=roles.PROFESSEUR))
            )
            lignes.append(f"{profs} professeurs.")
        if p.paiements and eleves:
            profils = self._profils(db, [e.id for e in eleves]).values()
            attendu = sum(pr.montant_total_annee or 0 for pr in profils)
            paye = sum(pr.montant_paye or 0 for pr in profils)
            soldes = sum(1 for pr in profils if pr.statut_paiement == "paye")
            lignes.append(f"Paiements : {paye:.2f} € payés sur {attendu:.2f} € attendus ; {soldes} élèves ont tout payé.")
        return "\n".join(lignes)

    def _lister_cours(self, db: Session, p: Perimetre) -> str:
        lignes = []
        for c in self._cours(db, p):
            profs = [
                _nom(x) for x in db.scalars(
                    select(Compte).join(cours_professeurs, cours_professeurs.c.professeur_id == Compte.id).where(cours_professeurs.c.cours_id == c.id)
                )
            ]
            nb = db.scalar(select(func.count()).select_from(eleves_cours).where(eleves_cours.c.cours_id == c.id))
            horaires = [f"{c.jour or '?'} {c.heure_debut or ''}-{c.heure_fin or ''}"] + [
                f"{h.jour} {h.heure_debut}-{h.heure_fin}" for h in c.horaires_supplementaires
            ]
            lignes.append(
                f"- {c.nom} (id {c.id}) : {c.discipline or ''} {c.niveau or ''} ; {' + '.join(horaires)} ; salle {c.salle or '?'} ; "
                f"prof : {', '.join(profs) or '?'} ; {nb} élèves"
            )
        return "\n".join(lignes) or "Aucun cours."

    def _lister_eleves(self, db: Session, p: Perimetre, cours_id=None, nom=None, statut_paiement=None) -> str:
        eleves = self._eleves(db, p)
        if cours_id is not None:
            inscrits = set(db.scalars(select(eleves_cours.c.eleve_id).where(eleves_cours.c.cours_id == cours_id)))
            eleves = [e for e in eleves if e.id in inscrits]
        if nom:
            bout = nom.lower()
            eleves = [e for e in eleves if bout in _nom(e).lower()]
        ids = [e.id for e in eleves]
        profils = self._profils(db, ids)
        if statut_paiement and p.paiements:
            eleves = [e for e in eleves if profils.get(e.id) and profils[e.id].statut_paiement == statut_paiement]
        cours = self._cours_par_eleve(db, ids)
        lignes = []
        for e in eleves[:LIGNES_MAX]:
            pr = profils.get(e.id)
            morceaux = [f"- {_nom(e)} (id {e.id})"]
            if p.tout:
                age = calculer_age(pr.date_naissance) if pr else None
                morceaux.append(f"{age} ans" if age is not None else "âge ?")
            morceaux.append(", ".join(cours[e.id]) or "aucun cours")
            if p.paiements and pr:
                morceaux.append(f"paiement {pr.statut_paiement} {pr.montant_paye or 0:.0f}/{pr.montant_total_annee or 0:.0f} €")
            if p.tout and pr and pr.ligne_rouge:
                morceaux.append("en rouge")
            if p.tout:
                morceaux.append(" ".join(x for x in (e.email, e.telephone) if x) or "sans contact")
            lignes.append(" ; ".join(morceaux))
        reste = len(eleves) - LIGNES_MAX
        return f"{len(eleves)} élèves.\n" + "\n".join(lignes) + (f"\n… et {reste} de plus." if reste > 0 else "")

    def _fiche_eleve(self, db: Session, p: Perimetre, eleve_id: int) -> str:
        if p.eleve_ids is not None and eleve_id not in p.eleve_ids:
            return "Élève introuvable ou hors de vos droits."
        e = db.get(Compte, eleve_id)
        if e is None or e.ecole_id != p.ecole_id:
            return "Élève introuvable."
        pr = self._profils(db, [e.id]).get(e.id)
        lignes = [f"{_nom(e)} (id {e.id})"]
        if pr:
            age = calculer_age(pr.date_naissance)
            lignes.append(f"Né(e) le {pr.date_naissance or '?'} ({age if age is not None else '?'} ans) ; adresse : {pr.adresse or '?'}")
            if p.paiements:
                lignes.append(f"Paiement : {pr.statut_paiement}, {pr.montant_paye or 0:.2f} € payés sur {pr.montant_total_annee or 0:.2f} €")
            if p.tout:
                lignes.append(f"Commentaire de l'administration : {pr.commentaire_admin or 'aucun'}")
                rouge = ["toute la ligne"] if pr.ligne_rouge else []
                rouge += [COLONNES_ROUGES.get(c, c) for c in pr.cellules_rouges or []]
                lignes.append("En rouge dans Admin > Élèves : " + (", ".join(rouge) or "non"))
        lignes.append(f"Contact : {e.email or '?'} {e.telephone or ''}")
        for ct in db.scalars(select(ContactEleve).where(ContactEleve.eleve_id == e.id)):
            lignes.append(f"Contact {ct.lien or ''} : {ct.prenom or ''} {ct.nom or ''} {ct.telephone or ''} {ct.email or ''}".strip())
        lignes.append("Cours : " + (", ".join(self._cours_par_eleve(db, [e.id])[e.id]) or "aucun"))
        stats = dict(db.execute(
            select(PresenceEleve.statut, func.count()).where(PresenceEleve.eleve_id == e.id).group_by(PresenceEleve.statut)
        ).all())
        lignes.append(f"Présences : {stats.get('present', 0)} présent, {stats.get('retard', 0)} retard, {stats.get('absent', 0)} absent")
        chores = list(db.scalars(
            select(Choregraphie.nom).join(choregraphies_eleves, choregraphies_eleves.c.choregraphie_id == Choregraphie.id)
            .where(choregraphies_eleves.c.eleve_id == e.id)
        ))
        lignes.append("Chorégraphies : " + (", ".join(chores) or "aucune"))
        return "\n".join(lignes)

    def _lister_professeurs(self, db: Session, p: Perimetre) -> str:
        if not p.tout:
            return "Réservé aux administrateurs."
        lignes = []
        for prof in db.scalars(
            select(Compte).where(Compte.ecole_id == p.ecole_id, Compte.roles.any(role=roles.PROFESSEUR)).order_by(Compte.nom)
        ):
            cours = list(db.scalars(
                select(Cours.nom).join(cours_professeurs, cours_professeurs.c.cours_id == Cours.id)
                .where(cours_professeurs.c.professeur_id == prof.id)
            ))
            lignes.append(f"- {_nom(prof)} (id {prof.id}) ; {prof.email or ''} {prof.telephone or ''} ; cours : {', '.join(cours) or 'aucun'}")
        return "\n".join(lignes) or "Aucun professeur."

    def _presences(self, db: Session, p: Perimetre, cours_id=None, date_debut=None, date_fin=None) -> str:
        cours = {c.id: c for c in self._cours(db, p)}
        if cours_id is not None:
            cours = {k: v for k, v in cours.items() if k == cours_id}
        debut = self._date(date_debut, dt.date(1900, 1, 1))
        fin = self._date(date_fin, dt.date.today())
        seances = list(db.scalars(
            select(SeancePresence).where(SeancePresence.cours_id.in_(cours or {-1}), SeancePresence.date >= debut, SeancePresence.date <= fin)
            .order_by(SeancePresence.date)
        ))
        if not seances:
            return "Aucune séance enregistrée sur cette période."
        noms = {e.id: _nom(e) for e in self._eleves(db, p)}
        lignes, taux = [], defaultdict(lambda: [0, 0])
        for s in seances:
            parstatut = defaultdict(list)
            for pe in db.scalars(select(PresenceEleve).where(PresenceEleve.seance_id == s.id)):
                if pe.eleve_id in noms:
                    parstatut[pe.statut].append(noms[pe.eleve_id])
                    taux[pe.eleve_id][0] += pe.statut != "absent"
                    taux[pe.eleve_id][1] += 1
            lignes.append(
                f"- {s.date} {cours[s.cours_id].nom} : {len(parstatut['present'])} présents, {len(parstatut['retard'])} retards, "
                f"absents : {', '.join(parstatut['absent']) or 'aucun'}"
            )
        lignes.append("Taux de présence par élève :")
        for eleve_id, (venus, total) in sorted(taux.items(), key=lambda x: x[1][0] / max(x[1][1], 1)):
            lignes.append(f"  {noms[eleve_id]} : {venus}/{total}")
        return "\n".join(lignes[: LIGNES_MAX + 50])

    def _heures_professeurs(self, db: Session, p: Perimetre, professeur_id=None, mois=None) -> str:
        if not p.tout:
            # Un professeur : ses propres heures (Profil > Mes heures).
            if p.compte_id is None or professeur_id not in (None, p.compte_id):
                return "Réservé aux administrateurs : vous ne voyez que vos propres heures."
            professeur_id = p.compte_id
        requete = (
            select(PresenceProf, SeancePresence, Cours)
            .join(SeancePresence, SeancePresence.id == PresenceProf.seance_id)
            .join(Cours, Cours.id == SeancePresence.cours_id)
            .where(Cours.ecole_id == p.ecole_id)
            .order_by(SeancePresence.date)
        )
        if professeur_id is not None:
            requete = requete.where(PresenceProf.professeur_id == professeur_id)
        lignes, cumul = [], defaultdict(int)
        noms = {}
        for pp, s, c in db.execute(requete):
            if mois and not str(s.date).startswith(mois):
                continue
            if pp.professeur_id not in noms:
                prof = db.get(Compte, pp.professeur_id)
                noms[pp.professeur_id] = _nom(prof) if prof else str(pp.professeur_id)
            cumul[pp.professeur_id] += pp.depassement_minutes or 0
            lignes.append(
                f"- {s.date} {c.nom} : {noms[pp.professeur_id]} {pp.heure_debut_reelle or c.heure_debut}-"
                f"{pp.heure_fin_reelle or c.heure_fin}, dépassement {pp.depassement_minutes or 0} min"
            )
        if not lignes:
            return "Aucune séance enregistrée."
        lignes.append("Dépassements cumulés : " + ", ".join(f"{noms[k]} {v} min" for k, v in cumul.items()))
        return "\n".join(lignes[: LIGNES_MAX + 20])

    def _lister_choregraphies(self, db: Session, p: Perimetre, cours_id=None) -> str:
        cours = {c.id: c for c in self._cours(db, p)}
        requete = select(Choregraphie).where(Choregraphie.cours_id.in_(cours or {-1}))
        if cours_id is not None:
            requete = requete.where(Choregraphie.cours_id == cours_id)
        lignes = []
        for ch in db.scalars(requete):
            eleves = list(db.scalars(
                select(Compte).join(choregraphies_eleves, choregraphies_eleves.c.eleve_id == Compte.id)
                .where(choregraphies_eleves.c.choregraphie_id == ch.id)
            ))
            videos = db.scalar(select(func.count()).select_from(choregraphies_videos).where(choregraphies_videos.c.choregraphie_id == ch.id))
            lignes.append(
                f"- {ch.nom} ({cours[ch.cours_id].nom}) : {len(eleves)} élèves ({', '.join(_nom(e) for e in eleves)}) ; "
                f"costume : {ch.costume or '?'} ; répétition : {ch.horaire_repetition or '?'} ; {videos} vidéos"
            )
        return "\n".join(lignes) or "Aucune chorégraphie."

    def _lister_inscriptions_en_ligne(self, db: Session, p: Perimetre) -> str:
        if not p.tout:
            return "Réservé aux administrateurs."
        lignes = []
        for i in db.scalars(select(Inscription).where(Inscription.ecole_id == p.ecole_id).order_by(Inscription.created_at.desc())):
            lignes.append(
                f"- {i.eleve_prenom} {i.eleve_nom}, reçue le {i.created_at:%Y-%m-%d} ; {i.nb_cours_semaine} cours/semaine ; "
                f"paiement {i.moyen_paiement} ({i.statut_paiement}) ; adhésion {i.montant_adhesion:.2f} €, "
                f"trimestre {i.montant_trimestriel:.2f} €"
            )
        return "\n".join(lignes[:LIGNES_MAX]) or "Aucune inscription en ligne."

    def _lister_saisons(self, db: Session, p: Perimetre) -> str:
        with toutes_saisons(db):
            saisons = list(db.scalars(select(Saison).where(Saison.ecole_id == p.ecole_id).order_by(Saison.id)))
            courante = saison_courante_id(db, p.ecole_id)
        return "\n".join(
            f"- {s.nom} : du {s.date_debut} au {s.date_fin}{' (en cours)' if s.id == courante else ''}" for s in saisons
        ) or "Aucune saison."

    def _lister_personnes(self, db: Session, p: Perimetre, role=None) -> str:
        if role is not None and role not in NOMS_ROLES:
            return f"Rôle inconnu « {role} » : {', '.join(NOMS_ROLES)}."
        # Le Super User n'a pas de fiche d'école (spec/core.md §6.1) : listé à part.
        super_user = Compte.ecole_id.is_(None) & Compte.roles.any(role=roles.SUPERUSER)
        requete = select(Compte).where((Compte.ecole_id == p.ecole_id) | super_user).order_by(Compte.nom, Compte.prenom)
        if role is not None:
            requete = requete.where(Compte.roles.any(role=role))
        personnes = list(db.scalars(requete))
        lignes = []
        for c in personnes[:LIGNES_MAX]:
            noms = [NOMS_ROLES[r] for r in NOMS_ROLES if roles.a_le_role(c, r)]
            contact = "" if roles.is_superuser(c) else " ; " + (" ".join(x for x in (c.email, c.telephone) if x) or "sans contact")
            lignes.append(f"- {_nom(c)} (id {c.id}) : {', '.join(noms)}{contact}")
        reste = len(personnes) - LIGNES_MAX
        return f"{len(personnes)} personnes.\n" + "\n".join(lignes) + (f"\n… et {reste} de plus." if reste > 0 else "")

    def _infos_ecole(self, db: Session, p: Perimetre) -> str:
        e = db.get(Ecole, p.ecole_id)
        if e is None:
            return "École introuvable."
        # L'IBAN entier reste dans Admin > École : l'assistant n'en voit que la fin.
        iban = f"se termine par {e.iban[-4:]}" if e.iban else "?"
        return "\n".join([
            f"{e.nom} (id {e.id})",
            f"Adresse : {e.adresse or '?'}, {e.code_postal} {e.ville or ''}".rstrip(),
            f"SIRET : {e.siret or '?'} ; IBAN : {iban}",
            f"Email de contact : {e.email_contact or '?'} ; email du trésorier : {e.email_tresorier or '?'}",
            f"Adresse de l'appli : {e.sous_domaine} ; nom de l'appli : {e.nom_appli or e.nom} ; slogan : {e.slogan or 'aucun'}",
        ])

    def _lister_groupes(self, db: Session, p: Perimetre) -> str:
        groupes = list(db.scalars(
            select(Conversation).where(Conversation.ecole_id == p.ecole_id, Conversation.type == "groupe").order_by(Conversation.nom)
        ))
        lignes = []
        for g in groupes:
            membres = list(db.scalars(select(ConversationMembre).where(ConversationMembre.conversation_id == g.id)))
            noms = []
            for m in membres:
                x = db.get(Compte if m.membre_type == "compte" else Cours, m.membre_id)
                if x is not None:
                    noms.append(_nom(x) if m.membre_type == "compte" else f"le cours {x.nom}")
            lignes.append(f"- « {g.nom or 'sans nom'} » (id {g.id}) : {', '.join(noms) or 'aucun membre'}")
        return "\n".join(lignes) or "Aucun groupe."
