import { useEffect, useState } from 'react'
import * as ecolesApi from '../../api/ecoles.js'
import { useSaisonConsultee } from '../../api/saison.js'
import AdministrateursTableau from './AdministrateursTableau.jsx'
import { isOwner } from '../../data/roles.js'
import SaisonsSection from './SaisonsSection.jsx'
import SauvegardeEcoleMenu from './SauvegardeEcoleMenu.jsx'
import UsageVideoSection from './UsageVideoSection.jsx'

// Onglet Admin > École (voir spec/SPEC.md §5.1.1 et §6.1) : nom de l'école,
// code postal et ses 3 codes d'accès, modifiables par tout admin (pas
// seulement le créateur de l'école). Premier sous-onglet, le plus à gauche.
// Le code postal distingue deux écoles qui porteraient le même nom (le
// couple nom + code postal doit être unique, pas le nom seul).
//
// Persisté via api/ecoles.js (voir api/README.md) — avant, `update` ne
// touchait qu'à l'état React local (setEcole), jamais sauvegardé : toute
// modif disparaissait à la fermeture de l'appli (bug signalé, ex. code
// postal). Chaque champ appelle l'API à chaque frappe, comme les autres
// écrans Admin (voir AdminEleves.jsx : EditableText/update) — mais MAJ
// locale immédiate (optimiste), sans attendre la réponse réseau pour
// mettre à jour l'affichage : sur ces champs texte, attendre la réponse
// avant de raffraîchir `ecole` peut faire résoudre les requêtes dans le
// désordre (une frappe rapide envoie plusieurs PUT qui ne reviennent pas
// forcément dans l'ordre d'envoi) et faire revenir l'affichage en
// arrière au milieu de la frappe. La persistance reste garantie : chaque
// requête envoie la valeur complète du champ à cet instant, la dernière
// envoyée finit par gagner côté serveur.
//
// Menu ⋮ dans l'en-tête, à droite du badge de l'utilisateur (demande du
// 2026-09-21, voir SauvegardeEcoleMenu.jsx) : sauvegarder/programmer/
// importer/supprimer les données de l'école, le téléchargement des
// nouvelles inscriptions et, pour un administrateur principal, "Ajouter un
// administrateur" (un seul ⋮ pour tout l'écran).
export default function AdminParametres({
  ecole,
  setEcole,
  setVideos,
  cours,
  eleves,
  setEleves,
  activeUser,
  professeurs,
  onSaisonCreee,
  onSaisonSupprimee,
}) {
  const [creationAdminOuverte, setCreationAdminOuverte] = useState(false)
  const saisonConsultee = useSaisonConsultee()

  // Codes d'accès et réglages de sauvegarde : chargés ici, par la route
  // réservée aux admins (voir api/ecoles.js : obtenir). L'école reçue à la
  // connexion n'a que son nom et son code postal.
  useEffect(() => {
    let annule = false
    ecolesApi
      .obtenir(ecole.id)
      .then((complete) => {
        if (!annule) setEcole((e) => ({ ...e, ...complete }))
      })
      .catch((err) => console.error(err))
    return () => {
      annule = true
    }
  }, [ecole.id, setEcole])

  function update(patch) {
    setEcole((e) => ({ ...e, ...patch }))
    ecolesApi.modifier(ecole.id, patch).catch((err) => console.error(err))
  }

  return (
    <div className="admin-panel">
      <SauvegardeEcoleMenu
        ecole={ecole}
        cours={cours}
        setEleves={setEleves}
        onAjouterAdministrateur={isOwner(activeUser) ? () => setCreationAdminOuverte(true) : null}
      />

      <div className="form-fields">
        <label htmlFor="ecole-param-nom">Nom de l’école</label>
        <input
          id="ecole-param-nom"
          className="field-input"
          value={ecole.nom}
          onChange={(e) => update({ nom: e.target.value })}
        />

        <label htmlFor="ecole-param-cp">Code postal</label>
        <input
          id="ecole-param-cp"
          className="field-input"
          value={ecole.codePostal}
          onChange={(e) => update({ codePostal: e.target.value })}
        />

        <label htmlFor="ecole-param-admin">Code d’accès Admin</label>
        <input
          id="ecole-param-admin"
          className="field-input"
          value={ecole.codeAccesAdmin ?? ''}
          onChange={(e) => update({ codeAccesAdmin: e.target.value })}
        />

        <label htmlFor="ecole-param-prof">Code d’accès Professeur</label>
        <input
          id="ecole-param-prof"
          className="field-input"
          value={ecole.codeAccesProf ?? ''}
          onChange={(e) => update({ codeAccesProf: e.target.value })}
        />

        <label htmlFor="ecole-param-eleve">Code d’accès Élève</label>
        <input
          id="ecole-param-eleve"
          className="field-input"
          value={ecole.codeAccesEleve ?? ''}
          onChange={(e) => update({ codeAccesEleve: e.target.value })}
        />
      </div>

      {/* Sections au même niveau, même format de titre (demande du
          2026-09-21) : Saisons (spec §2.6, entre les codes d'accès et les
          administrateurs), Administrateurs (spec §2.4), puis Usage vidéo. */}
      <SaisonsSection
        key={activeUser.id}
        ecoleId={ecole.id}
        onSaisonCreee={onSaisonCreee}
        onSaisonSupprimee={onSaisonSupprimee}
      />

      <AdministrateursTableau
        ecoleId={ecole.id}
        activeUser={activeUser}
        professeurs={professeurs}
        eleves={eleves}
        creationOuverte={creationAdminOuverte}
        onFermerCreation={() => setCreationAdminOuverte(false)}
      />

      {/* `key` : recalculé quand la saison affichée change (spec §2.6). */}
      <UsageVideoSection key={saisonConsultee?.id ?? 'courante'} ecoleId={ecole.id} setVideos={setVideos} />
    </div>
  )
}
