// Les colonnes du tableau des élèves (Admin > Élèves) et leur affichage
// (spec/core.md §4.3, niveau 2 : « Affichage dans Admin »). Le serveur garde
// pour chaque saison l'ordre et la case Afficher ; ici, ce qu'est chaque
// colonne. « field:<id> » : un champ de la fiche (ChampsMembres.jsx).

export const COLONNES = [
  { key: 'nom', label: 'Élève', nature: 'Saisi', verrouillee: true },
  { key: 'cours', label: 'Cours suivis', nature: 'Saisi' },
  { key: 'paiement', label: 'Paiement', nature: 'Calculé', detail: 'statut et montants' },
  { key: 'commentaire', label: 'Commentaire', nature: 'Saisi' },
  { key: 'naissance', label: 'Date de naissance', nature: 'Saisi' },
  { key: 'age', label: 'Âge', nature: 'Calculé', detail: 'date de naissance' },
  { key: 'contacts', label: 'Contacts', nature: 'Saisi' },
  { key: 'telephone', label: 'Téléphone', nature: 'Saisi' },
  { key: 'email', label: 'Email', nature: 'Saisi' },
  { key: 'adresse', label: 'Adresse', nature: 'Saisi' },
  { key: 'sante', label: 'Santé', nature: 'Saisi' },
  { key: 'certificat', label: 'Certificat médical', nature: 'Saisi' },
  { key: 'inviter', label: 'Inviter', nature: 'Bouton', detail: 'accès à l’appli' },
  { key: 'statut', label: 'Statut de connexion', nature: 'Calculé', detail: 'invité · mot de passe · appli' },
]

// Toutes les colonnes, dans l'ordre choisi : celles enregistrées d'abord,
// puis celles qui manquent (nouveau champ, saison jamais réglée), affichées.
export function ordonner(enregistrees, champs) {
  const connues = [
    ...COLONNES,
    ...champs.map((c) => ({ key: `field:${c.id}`, label: c.label, nature: 'Saisi', champ: c })),
  ]
  const parCle = new Map(connues.map((c) => [c.key, c]))
  const resultat = []
  for (const { key, shown } of enregistrees) {
    const colonne = parCle.get(key)
    if (!colonne) continue
    resultat.push({ ...colonne, shown: colonne.verrouillee ? true : shown })
    parCle.delete(key)
  }
  for (const colonne of parCle.values()) resultat.push({ ...colonne, shown: true })
  return resultat
}
