"""Routes REST du module notes de frais (/notes-frais/...). Qui appelle est
fourni par l'appli hôte (`membre_courant`, une dépendance FastAPI qui
renvoie un `Membre`) ; les droits sont vérifiés par le service.
"""

from __future__ import annotations

import io
from urllib.parse import quote
from collections.abc import Callable
import datetime as dt

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse
from openpyxl import Workbook
from openpyxl.styles import Font
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db import get_db

from .ports import LectureImpossible, Membre
from .service import NotesDeFrais

TAILLE_MAX_LECTURE = 10 * 1024 * 1024
TAILLE_MAX_PIECE = 20 * 1024 * 1024


class DepenseEntree(BaseModel):
    date: dt.date
    montant_centimes: int = Field(gt=0)
    categorie_id: int | None = None
    description: str = ""
    lue_par_ia: bool = False


class DepenseModification(BaseModel):
    date: dt.date | None = None
    montant_centimes: int | None = Field(default=None, gt=0)
    categorie_id: int | None = None
    description: str | None = None


class RibEntree(BaseModel):
    titulaire: str | None = None
    iban: str | None = None
    bic: str | None = None


class EnvoiEntree(BaseModel):
    depense_ids: list[int]
    titre: str = ""
    don: bool = False
    rib: RibEntree | None = None


class RefusEntree(BaseModel):
    motif: str


class RemboursementEntree(BaseModel):
    note_ids: list[int]


class CorrectionEntree(BaseModel):
    person_id: int | None = None
    fournisseur: str | None = None
    date: dt.date | None = None
    montant_centimes: int | None = Field(default=None, gt=0)
    description: str | None = None
    titre: str | None = None
    categorie_id: int | None = None


class PreparationEntree(BaseModel):
    payeur_id: int


class PaiementEntree(BaseModel):
    operation_id: int


class PayeursEntree(BaseModel):
    person_ids: list[int]


class CategoriesEntree(BaseModel):
    libelles: list[str]


def _http(erreur: Exception) -> HTTPException:
    if isinstance(erreur, LookupError):
        return HTTPException(status_code=404, detail=str(erreur))
    if isinstance(erreur, PermissionError):
        return HTTPException(status_code=403, detail=str(erreur))
    return HTTPException(status_code=400, detail=str(erreur))


# Un trésorier qui saisit pour quelqu'un (Financier › ⋯) envoie l'id de la
# personne dans cet en-tête : il agit alors en son nom (service.agir_pour).
ENTETE_POUR = "X-Pour-Personne"


class NotesDeFraisReceiver:
    def __init__(self, client: NotesDeFrais, app: FastAPI, membre_courant: Callable[..., Membre]) -> None:
        self.client = client
        self.app = app
        self.membre_courant = membre_courant
        self._routes()

    def _routes(self) -> None:  # noqa: C901 - une fonction par route, comme documents/receiver.py
        app, nf = self.app, self.client
        db_dep = Depends(get_db)

        def appeler(fonction, *args, **kwargs):
            try:
                return fonction(*args, **kwargs)
            except (LookupError, PermissionError, ValueError) as erreur:
                raise _http(erreur) from erreur

        def membre_ou_personne(request: Request, db: Session = db_dep, m: Membre = Depends(self.membre_courant)) -> Membre:
            pour = request.headers.get(ENTETE_POUR, "")
            return appeler(nf.agir_pour, db, m, int(pour)) if pour.isdigit() else m

        membre = Depends(membre_ou_personne)

        # --- Membre ---

        @app.get("/notes-frais/moi")
        def espace(db: Session = db_dep, m: Membre = membre):
            return nf.espace(db, m)

        @app.get("/notes-frais/compteurs")
        def compteurs(db: Session = db_dep, m: Membre = membre):
            return nf.compteurs(db, m)

        @app.put("/notes-frais/rib")
        def definir_rib(corps: RibEntree, db: Session = db_dep, m: Membre = membre):
            rib = appeler(nf.definir_rib, db, m, titulaire=corps.titulaire, iban=corps.iban, bic=corps.bic)
            return {"rib": nf.rib_dict(rib)}

        @app.post("/notes-frais/lecture")
        async def lire_ticket(fichier: UploadFile = File(...), db: Session = db_dep, m: Membre = membre):
            contenu = await fichier.read(TAILLE_MAX_LECTURE + 1)
            if len(contenu) > TAILLE_MAX_LECTURE:
                raise HTTPException(status_code=400, detail="Photo trop lourde pour être lue : remplissez à la main.")
            try:
                return nf.lire_ticket(db, m, contenu, fichier.content_type or "")
            except LectureImpossible as erreur:
                raise HTTPException(status_code=422, detail=str(erreur)) from erreur

        @app.post("/notes-frais/depenses", status_code=201)
        def creer_depense(corps: DepenseEntree, db: Session = db_dep, m: Membre = membre):
            depense = appeler(
                nf.creer_depense, db, m, jour=corps.date, montant_centimes=corps.montant_centimes,
                categorie_id=corps.categorie_id, description=corps.description, lue_par_ia=corps.lue_par_ia,
            )
            return nf.depense_dict(depense)

        @app.put("/notes-frais/depenses/{depense_id}")
        def modifier_depense(depense_id: int, corps: DepenseModification, db: Session = db_dep, m: Membre = membre):
            champs = corps.model_dump(exclude_unset=True)
            if "date" in champs:
                champs["jour"] = champs.pop("date")
            return nf.depense_dict(appeler(nf.modifier_depense, db, m, depense_id, **champs))

        @app.delete("/notes-frais/depenses/{depense_id}", status_code=204)
        def supprimer_depense(depense_id: int, db: Session = db_dep, m: Membre = membre):
            appeler(nf.supprimer_depense, db, m, depense_id)
            return Response(status_code=204)

        @app.post("/notes-frais/depenses/{depense_id}/pieces", status_code=201)
        def ajouter_piece(depense_id: int, fichier: UploadFile = File(...), db: Session = db_dep, m: Membre = membre):
            piece = appeler(
                nf.ajouter_piece, db, m, depense_id, fichier.file, fichier.filename or "", fichier.content_type or ""
            )
            return {"id": piece.id, "type_mime": piece.type_mime, "nom": piece.nom}

        @app.delete("/notes-frais/pieces/{piece_id}", status_code=204)
        def supprimer_piece(piece_id: int, db: Session = db_dep, m: Membre = membre):
            appeler(nf.supprimer_piece, db, m, piece_id)
            return Response(status_code=204)

        @app.get("/notes-frais/pieces/{piece_id}")
        def fichier_piece(piece_id: int, db: Session = db_dep, m: Membre = membre):
            chemin, type_mime, nom = appeler(nf.fichier_piece, db, m, piece_id)
            return FileResponse(chemin, media_type=type_mime, filename=nom or None,
                                content_disposition_type="inline", headers={"Cache-Control": "private, max-age=3600"})

        @app.post("/notes-frais/notes", status_code=201)
        def envoyer(corps: EnvoiEntree, db: Session = db_dep, m: Membre = membre):
            note = appeler(
                nf.envoyer, db, m, depense_ids=corps.depense_ids, titre=corps.titre, don=corps.don,
                rib=corps.rib.model_dump() if corps.rib else None,
            )
            return nf.note_dict(note)

        @app.get("/notes-frais/notes/{note_id}/justificatifs.zip")
        def justificatifs(note_id: int, db: Session = db_dep, m: Membre = membre):
            contenu, nom = appeler(nf.archive_justificatifs, db, m, note_id)
            return Response(
                content=contenu,
                media_type="application/zip",
                headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(nom)}"},
            )

        @app.post("/notes-frais/notes/{note_id}/reprendre", status_code=204)
        def reprendre(note_id: int, db: Session = db_dep, m: Membre = membre):
            appeler(nf.reprendre, db, m, note_id)
            return Response(status_code=204)

        # --- Trésoriers ---

        @app.get("/notes-frais/personnes")
        def personnes(db: Session = db_dep, m: Membre = membre):
            return [{"person_id": p.person_id, "nom": p.nom, "role": p.role} for p in appeler(nf.personnes, db, m)]

        @app.get("/notes-frais/tresorerie")
        def tresorerie(filtre: str = "a_valider", db: Session = db_dep, m: Membre = membre):
            notes = appeler(nf.tresorerie, db, m, filtre)
            return {"notes": notes, "compteurs": nf.compteurs_tresorerie(db, m)}

        @app.get("/notes-frais/tresorerie/compteurs")
        def compteurs_tresorerie(db: Session = db_dep, m: Membre = membre):
            return appeler(nf.compteurs_tresorerie, db, m)

        @app.post("/notes-frais/notes/{note_id}/valider")
        def valider(note_id: int, db: Session = db_dep, m: Membre = membre):
            return nf.notes_dicts(db, m, [appeler(nf.valider, db, m, note_id)])[0]

        @app.post("/notes-frais/notes/{note_id}/refuser")
        def refuser(note_id: int, corps: RefusEntree, db: Session = db_dep, m: Membre = membre):
            return nf.note_dict(appeler(nf.refuser, db, m, note_id, corps.motif))

        # --- Financier › Pièces : établir et vérifier (financier.md §8.3 bis) ---

        @app.post("/notes-frais/etablir", status_code=201)
        async def etablir(
            nature: str = Form(...),
            fichier: UploadFile | None = File(None),
            person_id: int | None = Form(None),
            fournisseur: str | None = Form(None),
            date: dt.date | None = Form(None),
            montant_centimes: int | None = Form(None),
            description: str = Form(""),
            valider: bool = Form(False),
            categorie_id: int | None = Form(None),
            db: Session = db_dep,
            m: Membre = membre,
        ):
            contenu = None
            if fichier is not None:
                donnees = await fichier.read(TAILLE_MAX_PIECE + 1)
                if len(donnees) > TAILLE_MAX_PIECE:
                    raise HTTPException(status_code=400, detail="Fichier trop lourd (plus de 20 Mo).")
                contenu = (donnees, fichier.filename or "", fichier.content_type or "")
            note = appeler(
                nf.etablir, db, m, nature=nature, fichier=contenu, person_id=person_id, fournisseur=fournisseur,
                jour=date, montant_centimes=montant_centimes, description=description, valider=valider,
                categorie_id=categorie_id,
            )
            return nf.notes_dicts(db, m, [note])[0]

        @app.post("/notes-frais/notes/{note_id}/pages")
        def ajouter_page(note_id: int, fichier: UploadFile = File(...), db: Session = db_dep, m: Membre = membre):
            note = appeler(nf.ajouter_page, db, m, note_id, fichier.file, fichier.filename or "", fichier.content_type or "")
            return nf.notes_dicts(db, m, [note])[0]

        @app.patch("/notes-frais/notes/{note_id}")
        def corriger(note_id: int, corps: CorrectionEntree, db: Session = db_dep, m: Membre = membre):
            champs = corps.model_dump(exclude_unset=True)
            if "date" in champs:
                champs["jour"] = champs.pop("date")
            return nf.notes_dicts(db, m, [appeler(nf.corriger, db, m, note_id, **champs)])[0]

        @app.delete("/notes-frais/notes/{note_id}", status_code=204)
        def supprimer_note(note_id: int, db: Session = db_dep, m: Membre = membre):
            appeler(nf.supprimer_note, db, m, note_id)
            return Response(status_code=204)

        # --- Virements (financier.md §8.3 bis) ---

        def personnes_dicts(personnes):
            return [{"person_id": p.person_id, "nom": p.nom} for p in personnes]

        @app.get("/notes-frais/virements")
        def virements(db: Session = db_dep, m: Membre = membre):
            return {
                "virements": appeler(nf.virements, db, m),
                "payeurs": personnes_dicts(nf.payeurs(db, m)),
                "moi": m.person_id,
            }

        @app.get("/notes-frais/payeurs")
        def payeurs(db: Session = db_dep, m: Membre = membre):
            return personnes_dicts(appeler(nf.payeurs, db, m))

        @app.put("/notes-frais/payeurs")
        def definir_payeurs(corps: PayeursEntree, db: Session = db_dep, m: Membre = membre):
            return personnes_dicts(appeler(nf.definir_payeurs, db, m, corps.person_ids))

        @app.put("/notes-frais/notes/{note_id}/rib")
        def rib_note(note_id: int, corps: RibEntree, db: Session = db_dep, m: Membre = membre):
            note = appeler(nf.definir_rib_note, db, m, note_id, titulaire=corps.titulaire, iban=corps.iban, bic=corps.bic)
            return nf.notes_dicts(db, m, [note])[0]

        @app.post("/notes-frais/notes/{note_id}/preparer")
        def preparer(note_id: int, corps: PreparationEntree, db: Session = db_dep, m: Membre = membre):
            return nf.notes_dicts(db, m, [appeler(nf.preparer, db, m, note_id, corps.payeur_id)])[0]

        @app.post("/notes-frais/notes/{note_id}/virement")
        def virement_fait(note_id: int, db: Session = db_dep, m: Membre = membre):
            return nf.notes_dicts(db, m, [appeler(nf.virement_fait, db, m, note_id)])[0]

        @app.post("/notes-frais/notes/{note_id}/payee")
        def payee(note_id: int, corps: PaiementEntree, db: Session = db_dep, m: Membre = membre):
            return nf.notes_dicts(db, m, [appeler(nf.payer, db, m, note_id, corps.operation_id)])[0]

        @app.post("/notes-frais/remboursements")
        def rembourser(corps: RemboursementEntree, db: Session = db_dep, m: Membre = membre):
            return [nf.note_dict(n) for n in appeler(nf.rembourser, db, m, corps.note_ids)]

        @app.get("/notes-frais/categories")
        def categories(db: Session = db_dep, m: Membre = membre):
            return [{"id": c.id, "libelle": c.libelle, "code": c.code} for c in nf.categories(db, m.org_id)]

        @app.put("/notes-frais/categories")
        def definir_categories(corps: CategoriesEntree, db: Session = db_dep, m: Membre = membre):
            return [{"id": c.id, "libelle": c.libelle, "code": c.code} for c in appeler(nf.definir_categories, db, m, corps.libelles)]

        @app.get("/notes-frais/export.xlsx")
        def export(
            debut: dt.date | None = None, fin: dt.date | None = None, nature: str = "frais",
            db: Session = db_dep, m: Membre = membre,
        ):
            lignes = appeler(nf.lignes_export, db, m, debut, fin, nature)
            return Response(
                content=_classeur(lignes),
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": 'attachment; filename="notes-de-frais.xlsx"'},
            )


COLONNES = [
    ("date", "Date", 12), ("personne", "Personne", 24), ("categorie", "Catégorie", 18),
    ("description", "Description", 36), ("montant", "Montant (€)", 12), ("justificatif", "Justificatif", 12),
    ("note", "Note", 28), ("statut", "Statut", 14), ("envoyee_le", "Envoyée le", 12),
]


def _classeur(lignes: list[dict]) -> bytes:
    classeur = Workbook()
    feuille = classeur.active
    feuille.title = "Notes de frais"
    feuille.append([titre for _, titre, _ in COLONNES])
    for cellule in feuille[1]:
        cellule.font = Font(bold=True)
    for ligne in lignes:
        feuille.append([ligne[cle] for cle, _, _ in COLONNES])
    for index, (cle, _, largeur) in enumerate(COLONNES, start=1):
        lettre = feuille.cell(row=1, column=index).column_letter
        feuille.column_dimensions[lettre].width = largeur
        for cellule in feuille[lettre][1:]:
            if cle == "montant":
                cellule.number_format = "#,##0.00"
            elif cle in ("date", "envoyee_le"):
                cellule.number_format = "DD/MM/YYYY"
    feuille.freeze_panes = "A2"
    tampon = io.BytesIO()
    classeur.save(tampon)
    return tampon.getvalue()
