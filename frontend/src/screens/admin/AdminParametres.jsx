import { useState } from 'react'
import {
  definirAffichageMigration,
  DOMAINES_MIGRES,
  estAffichageMigrationActif,
  INFOS_DOMAINES,
} from '../../api/etatMigration.js'
import Badge from '../../components/Badge.jsx'
import Modal from '../../components/Modal.jsx'

// Onglet Admin > École (voir spec/SPEC.md §5.1.1 et §6.1) : nom de l'école,
// code postal et ses 3 codes d'accès, modifiables par tout admin (pas
// seulement le créateur de l'école). Premier sous-onglet, le plus à gauche.
// Le code postal distingue deux écoles qui porteraient le même nom (le
// couple nom + code postal doit être unique, pas le nom seul).
//
// Section "Développement" en bas : outils de suivi de la migration vers
// le vrai backend (voir api/etatMigration.js) — utiles uniquement pendant
// cette période de transition, à retirer une fois tous les domaines
// branchés.
export default function AdminParametres({ ecole, setEcole }) {
  const [afficherMigration, setAfficherMigration] = useState(estAffichageMigrationActif())
  const [showEtatModules, setShowEtatModules] = useState(false)

  function update(patch) {
    setEcole((e) => ({ ...e, ...patch }))
  }

  function toggleAffichageMigration(actif) {
    setAfficherMigration(actif)
    definirAffichageMigration(actif)
    // Simplification volontaire : le liseré bleu (ZoneMigration.jsx) est
    // lu au rendu de chaque écran, pas suivi en état React partagé — un
    // rechargement garantit que tous les écrans déjà montés le reflètent.
    window.location.reload()
  }

  return (
    <div className="admin-panel">
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
          value={ecole.codeAccesAdmin}
          onChange={(e) => update({ codeAccesAdmin: e.target.value })}
        />

        <label htmlFor="ecole-param-prof">Code d’accès Professeur</label>
        <input
          id="ecole-param-prof"
          className="field-input"
          value={ecole.codeAccesProf}
          onChange={(e) => update({ codeAccesProf: e.target.value })}
        />

        <label htmlFor="ecole-param-eleve">Code d’accès Élève</label>
        <input
          id="ecole-param-eleve"
          className="field-input"
          value={ecole.codeAccesEleve}
          onChange={(e) => update({ codeAccesEleve: e.target.value })}
        />
      </div>

      <p className="section-label">Développement</p>
      <div className="form-fields">
        <label className="checkbox-list__item">
          <input
            type="checkbox"
            checked={afficherMigration}
            onChange={(e) => toggleAffichageMigration(e.target.checked)}
          />
          Repérer en bleu les écrans pas encore branchés au vrai backend
        </label>
        <button
          type="button"
          className="btn btn--secondary"
          onClick={() => setShowEtatModules(true)}
        >
          État des modules
        </button>
      </div>

      {showEtatModules && (
        <Modal title="État des modules" onClose={() => setShowEtatModules(false)}>
          <p className="muted">
            Le backend expose déjà tous ces modules (testés côté serveur) — "Branché" veut dire
            que l'écran correspondant les utilise vraiment ; "En dur" veut dire qu'il affiche
            encore les données fictives du frontend, pas encore le vrai backend.
          </p>
          <div className="checkbox-list">
            {Object.entries(INFOS_DOMAINES).map(([cle, { label, ecran }]) => (
              <div key={cle} className="checkbox-list__item checkbox-list__item--etat">
                <span>
                  <strong>{label}</strong> — {ecran}
                </span>
                {DOMAINES_MIGRES[cle] ? (
                  <Badge tone="success">Branché</Badge>
                ) : (
                  <Badge tone="info">En dur</Badge>
                )}
              </div>
            ))}
          </div>
        </Modal>
      )}
    </div>
  )
}
