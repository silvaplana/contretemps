// Liste des cours proposés sur le formulaire public d'inscription — les
// libellés que voit la famille diffèrent des noms internes de l'appli
// (voir cours/models.py:Cours.nom, source de vérité pour le tarif et
// l'export Excel/PDF).
//
// `coursNom` : nom EXACT du cours interne que ce choix représente
// (résolu en id via le `cours` renvoyé par GET /cours, voir
// FormulaireInscription.jsx — jour/horaire affichés viennent TOUJOURS
// du cours réel, jamais tapés en dur ici, pour rester synchronisés si
// l'horaire est corrigé plus tard côté Admin). Une entrée dont le nom
// ne résout à aucun cours réel (ex. cours renommé/supprimé côté admin)
// est simplement ignorée à l'affichage — jamais une case cassée.
//
// "Éveil + Classique Initiation" est volontairement un ALIAS de
// "Classique Initiation" (même coursNom, "Class Ini") — décision
// utilisateur : compte comme 1 seul cours pour le tarif ET
// l'inscription réelle, l'Éveil n'apparaît nulle part à part. Les 2
// entrées existent juste pour que la famille retrouve le cours qu'elle
// cherche, qu'elle pense "Éveil" ou "Classique Initiation".
export const COURS_PUBLICS = [
  { libelle: 'Éveil', coursNom: 'Éveil' },
  { libelle: 'Éveil + Classique Initiation', coursNom: 'Class Ini' },
  { libelle: 'Classique Initiation', coursNom: 'Class Ini' },
  { libelle: 'Classique Moyen', coursNom: 'Class Moy' },
  { libelle: 'Classique Inter', coursNom: 'Class Inter' },
  { libelle: 'Classique Avancé', coursNom: 'Class AV' },
  { libelle: 'Pointes Inter', coursNom: 'Pointes inter' },
  { libelle: 'Pointes Avancé', coursNom: 'Pointes AV' },
  { libelle: 'Jazz Initiation', coursNom: 'Jazz Ini' },
  { libelle: 'Jazz Moyen', coursNom: 'Jazz Moy' },
  { libelle: 'Jazz Junior', coursNom: 'Jazz Junior' },
  { libelle: 'Jazz Inter', coursNom: 'Jazz Inter' },
  { libelle: 'Jazz Avancé', coursNom: 'Jazz AV' },
  { libelle: 'Street Moyen', coursNom: 'Street Moyen' },
  { libelle: 'Street Junior Inter', coursNom: 'Street Junior Inter' },
  { libelle: 'Contemporain Junior', coursNom: 'Contempo Junior' },
  { libelle: 'Contemporain Inter Avancé', coursNom: 'Contempo Inter avance' },
  { libelle: 'Contemporain Adulte', coursNom: 'Contempo Adulte' },
]
