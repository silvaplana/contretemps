// Les colonnes du tableau des élèves (Admin > Élèves) et leur affichage
// (spec/core.md §4.3, niveau 2 : « Affichage dans Admin »). Le serveur garde
// pour chaque saison l'ordre et la case Afficher ; ici, ce qu'est chaque
// colonne. « field:<id> » : un champ de la fiche (ChampsMembres.jsx).

import { mots } from '../api/mots.js'
export const COLONNES = [
  {
    key: 'nom',
    get label() {
      return mots().Eleve
    },
    nature: 'Saisi',
    verrouillee: true,
  },
  { key: 'cours', label: 'Cours suivis', nature: 'Saisi' },
  { key: 'paiement', label: 'Paiement', nature: 'Calculé', detail: 'statut et montants' },
  { key: 'commentaire', label: 'Commentaire', nature: 'Saisi' },
  // Les champs de la fiche que l'appli sait lire (members/fields.py, KNOWN)
  // prennent ici la place des anciennes colonnes.
  { champ: 'birth_date' },
  { key: 'age', label: 'Âge', nature: 'Calculé', detail: 'date de naissance' },
  { key: 'contacts', label: 'Contacts', nature: 'Saisi' },
  { key: 'telephone', label: 'Téléphone', nature: 'Saisi' },
  { key: 'email', label: 'Email', nature: 'Saisi' },
  { champ: 'address' },
  { champ: 'allergies' },
  { champ: 'medical_treatment' },
  { champ: 'important_info' },
  { key: 'certificat', label: 'Certificat médical', nature: 'Saisi' },
  { key: 'inviter', label: 'Inviter', nature: 'Bouton', detail: 'accès à l’appli' },
  { key: 'statut', label: 'Statut de connexion', nature: 'Calculé', detail: 'invité · mot de passe · appli' },
]

// Toutes les colonnes, dans l'ordre choisi : celles enregistrées d'abord,
// puis celles qui manquent (nouveau champ, saison jamais réglée), affichées.
// `modules` (colonnesModules de app/modules.js) : les colonnes et boutons
// des modules. `imposee` (listeImposee) : le module qui apporte les
// membres ; saison jamais réglée, ses colonnes et celles du core sont
// celles de son `ordreParDefaut`, dans cet ordre, puis celles des autres
// modules (Statut FFST…), affichées.
export function ordonner(enregistrees, champs, imposee = null, modules = []) {
  const colonneDe = (c) => ({ key: `field:${c.id}`, label: c.label, nature: 'Saisi', champ: c })
  const connues = [
    ...COLONNES.flatMap((c) => (c.champ ? champs.filter((f) => f.key === c.champ).map(colonneDe) : [c])),
    ...modules,
    ...champs.filter((f) => !f.key).map(colonneDe),
  ]
  const parCle = new Map(connues.map((c) => [c.key, c]))
  const defaut = imposee?.liste.ordreParDefaut ?? []
  const reglees =
    imposee && enregistrees.length === 0
      ? [
          ...defaut.map((key) => ({ key, shown: true })),
          ...connues
            .filter((c) => !defaut.includes(c.key) && (!c.module || c.module === imposee.module))
            .map((c) => ({ key: c.key, shown: false })),
        ]
      : enregistrees
  const resultat = []
  for (const { key, shown } of reglees) {
    const colonne = parCle.get(key)
    if (!colonne) continue
    resultat.push({ ...colonne, shown: colonne.verrouillee ? true : shown })
    parCle.delete(key)
  }
  for (const colonne of parCle.values()) resultat.push({ ...colonne, shown: true })
  return resultat
}
