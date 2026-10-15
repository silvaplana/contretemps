"""Routes de la personnalisation par école (spec §2.7, §5.1.1).

Publiques (voir comptes/rbac.py : ROUTES_PUBLIQUES), car lues avant toute
connexion — par le téléphone qui installe l'appli, par Caddy qui décide de
créer un certificat, par la page de connexion :
- `GET /sous-domaines/existe?domain=…` (Caddy, `on_demand_tls`) ;
- `GET /par-host/…` : l'école de l'adresse visitée (en-tête Host) ;
- `GET /ecoles/{id}/personnalisation/{fichier}` : logo, nom en image,
  brouillons (noms tirés au hasard).
Les autres : un admin de l'école ; changer l'adresse : un Owner.
"""

from comptes import Compte, rbac
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db
from ecoles.models import Ecole

from .adresse import AdresseInvalide
from .images import ImageRefusee
from .personnalisation import TYPES_IMAGE, Personnalisation, PersonnalisationRefusee


class PersonnalisationModification(BaseModel):
    nom_appli: str | None = None
    nom_mode: str | None = None
    slogan: str | None = None
    couleur_fond: str | None = None
    couleur_texte: str | None = None
    couleur_accent: str | None = None
    police: str | None = None


class AdresseModification(BaseModel):
    sous_domaine: str


class DetourageChoix(BaseModel):
    detourage: str


def _host(request: Request) -> str | None:
    return request.headers.get("x-forwarded-host") or request.headers.get("host")


class PersonnalisationReceiver:
    def __init__(self, client: Personnalisation, app: FastAPI) -> None:
        self.client = client
        r = app
        r.get("/sous-domaines/existe")(self.existe)
        r.get("/sous-domaines/{adresse}/disponible")(self.disponible)
        r.get("/par-host/personnalisation")(self.par_host)
        r.get("/par-host/entete.html", response_class=HTMLResponse)(self.entete)
        r.get("/par-host/site.webmanifest")(self.manifest)
        r.get("/par-host/icons/{nom}")(self.icone_par_host)
        r.get("/par-host/{nom}")(self.icone_par_host)
        r.get("/ecoles/{ecole_id}/apparence")(self.apparence)
        r.get("/ecoles/{ecole_id}/personnalisation", dependencies=[Depends(self._admin)])(self.obtenir)
        r.patch("/ecoles/{ecole_id}/personnalisation", dependencies=[Depends(self._admin)])(self.modifier)
        r.post("/ecoles/{ecole_id}/personnalisation/defaut", dependencies=[Depends(self._admin)])(self.defaut)
        r.patch("/ecoles/{ecole_id}/sous-domaine", dependencies=[Depends(self._owner)])(self.changer_adresse)
        r.post("/ecoles/{ecole_id}/personnalisation/images/{type_image}", dependencies=[Depends(self._admin)])(
            self.envoyer_image
        )
        r.post(
            "/ecoles/{ecole_id}/personnalisation/images/{type_image}/detourage",
            dependencies=[Depends(self._admin)],
        )(self.detourage)
        r.post(
            "/ecoles/{ecole_id}/personnalisation/images/{type_image}/valider",
            dependencies=[Depends(self._admin)],
        )(self.valider)
        r.get(
            "/ecoles/{ecole_id}/personnalisation/images/{type_image}/historique",
            dependencies=[Depends(self._admin)],
        )(self.historique)
        r.post(
            "/ecoles/{ecole_id}/personnalisation/images/{type_image}/historique/{fichier}",
            dependencies=[Depends(self._admin)],
        )(self.reprendre)
        r.delete(
            "/ecoles/{ecole_id}/personnalisation/images/{type_image}/historique/{fichier}",
            status_code=204,
            dependencies=[Depends(self._admin)],
        )(self.supprimer_de_l_historique)
        r.delete(
            "/ecoles/{ecole_id}/personnalisation/images/{type_image}",
            status_code=204,
            dependencies=[Depends(self._admin)],
        )(self.annuler)
        r.get("/ecoles/{ecole_id}/personnalisation/{fichier}")(self.fichier)

    # --- Droits ---

    def _admin(self, ecole_id: int, appelant: Compte = Depends(rbac.compte_appelant)) -> None:
        rbac.require_admin(appelant, ecole_id)

    def _owner(self, ecole_id: int, appelant: Compte = Depends(rbac.compte_appelant)) -> None:
        rbac.require_owner(appelant, ecole_id)

    def _ecole(self, db: Session, ecole_id: int) -> Ecole:
        ecole = db.get(Ecole, ecole_id)
        if ecole is None:
            raise HTTPException(status_code=404, detail="École introuvable")
        return ecole

    @staticmethod
    def _type(type_image: str) -> str:
        if type_image not in TYPES_IMAGE:
            raise HTTPException(status_code=404, detail="Type d'image inconnu")
        return type_image

    # --- Publiques ---

    def existe(self, domain: str = "", db: Session = Depends(get_db)):
        """Appelée par Caddy avant de créer un certificat : réponse rapide,
        sans corps utile (spec §2.7)."""
        if not self.client.existe(db, domain):
            raise HTTPException(status_code=404)
        return Response(status_code=200)

    def disponible(
        self,
        adresse: str,
        ecole_id: int | None = None,
        db: Session = Depends(get_db),
    ):
        return self.client.ecoles.disponibilite(db, adresse, ecole_id)

    def par_host(self, request: Request, db: Session = Depends(get_db)):
        ecole, ancienne = self.client.ecole_du_host(db, _host(request))
        vue = self.client.vue(ecole)
        # Ancienne adresse encore valable : l'appli renvoie vers la nouvelle.
        vue["redirige_vers"] = vue["adresse"] if ancienne else None
        return vue

    def entete(self, request: Request, db: Session = Depends(get_db)):
        ecole, _ = self.client.ecole_du_host(db, _host(request))
        return HTMLResponse(self.client.entete_html(ecole), headers={"Cache-Control": "no-cache"})

    def manifest(self, request: Request, db: Session = Depends(get_db)):
        ecole, _ = self.client.ecole_du_host(db, _host(request))
        return JSONResponse(
            self.client.manifest(ecole),
            media_type="application/manifest+json",
            headers={"Cache-Control": "no-cache"},
        )

    def icone_par_host(self, nom: str, request: Request, db: Session = Depends(get_db)):
        ecole, _ = self.client.ecole_du_host(db, _host(request))
        contenu = self.client.icone(ecole, nom)
        if contenu is None:
            raise HTTPException(status_code=404)
        return Response(contenu, media_type="image/png", headers={"Cache-Control": "public, max-age=3600"})

    def apparence(self, ecole_id: int, db: Session = Depends(get_db)):
        """L'apparence d'une école (couleurs, police, logo, nom, slogan) :
        rien de secret, lue par l'appli une fois connectée, quelle que soit
        l'adresse (sur l'adresse générique, l'école est celle du compte)."""
        return self.client.vue(self._ecole(db, ecole_id))

    def fichier(self, ecole_id: int, fichier: str, db: Session = Depends(get_db)):
        chemin = self.client.fichier_image(self._ecole(db, ecole_id), fichier)
        if chemin is None or not chemin.exists():
            raise HTTPException(status_code=404)
        return FileResponse(chemin, media_type="image/png", headers={"Cache-Control": "public, max-age=300"})

    # --- Admin ---

    def obtenir(self, ecole_id: int, db: Session = Depends(get_db)):
        vue = self.client.vue(self._ecole(db, ecole_id))
        vue["detourages_disponibles"] = self.client.detourages_disponibles()
        return vue

    def modifier(self, ecole_id: int, donnees: PersonnalisationModification, db: Session = Depends(get_db)):
        try:
            ecole = self.client.modifier(db, self._ecole(db, ecole_id), donnees.model_dump(exclude_unset=True))
        except PersonnalisationRefusee as erreur:
            raise HTTPException(status_code=400, detail=str(erreur)) from erreur
        return self.client.vue(ecole)

    def defaut(self, ecole_id: int, db: Session = Depends(get_db)):
        return self.client.vue(self.client.revenir_au_defaut(db, self._ecole(db, ecole_id)))

    def changer_adresse(self, ecole_id: int, donnees: AdresseModification, db: Session = Depends(get_db)):
        try:
            ecole = self.client.ecoles.changer_adresse(db, self._ecole(db, ecole_id), donnees.sous_domaine)
        except AdresseInvalide as erreur:
            raise HTTPException(status_code=400, detail=str(erreur)) from erreur
        except ValueError as erreur:
            raise HTTPException(status_code=409, detail=str(erreur)) from erreur
        return self.client.vue(ecole)

    def envoyer_image(
        self,
        ecole_id: int,
        type_image: str,
        fichier: UploadFile = File(...),
        detourage: str | None = Form(None),
        db: Session = Depends(get_db),
    ):
        try:
            return self.client.envoyer_image(
                db, self._ecole(db, ecole_id), self._type(type_image), fichier.file.read(),
                (fichier.content_type or "").lower(), detourage,
            )
        except (ImageRefusee, PersonnalisationRefusee) as erreur:
            raise HTTPException(status_code=400, detail=str(erreur)) from erreur

    def detourage(self, ecole_id: int, type_image: str, donnees: DetourageChoix, db: Session = Depends(get_db)):
        try:
            return self.client.choisir_detourage(db, self._ecole(db, ecole_id), self._type(type_image), donnees.detourage)
        except PersonnalisationRefusee as erreur:
            raise HTTPException(status_code=400, detail=str(erreur)) from erreur

    def valider(self, ecole_id: int, type_image: str, db: Session = Depends(get_db)):
        try:
            ecole = self.client.valider_image(db, self._ecole(db, ecole_id), self._type(type_image))
        except PersonnalisationRefusee as erreur:
            raise HTTPException(status_code=400, detail=str(erreur)) from erreur
        return self.client.vue(ecole)

    def historique(self, ecole_id: int, type_image: str, db: Session = Depends(get_db)):
        return self.client.historique(self._ecole(db, ecole_id), self._type(type_image))

    def reprendre(self, ecole_id: int, type_image: str, fichier: str, db: Session = Depends(get_db)):
        try:
            ecole = self.client.reprendre_image(db, self._ecole(db, ecole_id), self._type(type_image), fichier)
        except PersonnalisationRefusee as erreur:
            raise HTTPException(status_code=400, detail=str(erreur)) from erreur
        return self.client.vue(ecole)

    def supprimer_de_l_historique(self, ecole_id: int, type_image: str, fichier: str, db: Session = Depends(get_db)):
        try:
            self.client.supprimer_image(self._ecole(db, ecole_id), self._type(type_image), fichier)
        except PersonnalisationRefusee as erreur:
            raise HTTPException(status_code=400, detail=str(erreur)) from erreur

    def annuler(self, ecole_id: int, type_image: str, db: Session = Depends(get_db)):
        self._ecole(db, ecole_id)
        self.client.annuler_image(ecole_id, self._type(type_image))
