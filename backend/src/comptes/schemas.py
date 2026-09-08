from pydantic import BaseModel


class CompteSortie(BaseModel):
    id: int
    ecole_id: int
    famille_id: int
    role: str
    nom: str
    prenom: str
    email: str | None
    telephone: str | None

    model_config = {"from_attributes": True}
