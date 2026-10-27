import { useEffect, useState } from 'react'
import { consulterSaison, useSaisonConsultee } from '../../api/saison.js'
import * as saisonsApi from '../../api/saisons.js'
import Icon from '../../components/Icon.jsx'
import Modal from '../../components/Modal.jsx'
import CreerSaison from './CreerSaison.jsx'

// Panneau "Éditer saison courante" (spec §2.6 et §5.1.1) : nom et dates.
// La création est un écran à part (CreerSaison.jsx).
function PanneauSaison({ courante, onValider, onClose }) {
  const [champs, setChamps] = useState({ nom: courante.nom, dateDebut: courante.dateDebut, dateFin: courante.dateFin })
  const [erreur, setErreur] = useState(null)
  const [enCours, setEnCours] = useState(false)

  async function valider() {
    setErreur(null)
    setEnCours(true)
    try {
      await onValider(champs)
    } catch (err) {
      setErreur(err.message)
      setEnCours(false)
    }
  }

  return (
    <Modal
      title="Éditer saison courante"
      onClose={onClose}
      footer={
        <button
          type="button"
          className="btn btn--primary btn--block"
          disabled={enCours || !champs.nom.trim() || !champs.dateDebut || !champs.dateFin}
          onClick={valider}
        >
          Valider
        </button>
      }
    >
      <div className="form-fields">
        <label htmlFor="saison-nom">Nom</label>
        <input
          id="saison-nom"
          className="field-input"
          value={champs.nom}
          placeholder="ex. 2027-2028"
          onChange={(e) => setChamps((c) => ({ ...c, nom: e.target.value }))}
        />
        <label htmlFor="saison-debut">Date de début</label>
        <input
          id="saison-debut"
          type="date"
          className="field-input"
          value={champs.dateDebut}
          onChange={(e) => setChamps((c) => ({ ...c, dateDebut: e.target.value }))}
        />
        <label htmlFor="saison-fin">Date de fin</label>
        <input
          id="saison-fin"
          type="date"
          className="field-input"
          value={champs.dateFin}
          onChange={(e) => setChamps((c) => ({ ...c, dateFin: e.target.value }))}
        />
      </div>

      {erreur && <p className="login-screen__erreur">{erreur}</p>}
    </Modal>
  )
}

// Panneau "Supprimer une saison" : n'importe laquelle, sauf s'il n'en reste
// qu'une. Irréversible (hors sauvegarde) : il faut choisir la saison, lire
// ce qui disparaît, puis retaper son nom pour pouvoir confirmer (demande
// utilisateur du 2026-09-24 : confirmation avant de pouvoir le faire).
function PanneauSuppression({ saisons, onSupprimer, onClose }) {
  const [saisonId, setSaisonId] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [erreur, setErreur] = useState(null)
  const [enCours, setEnCours] = useState(false)
  const saison = saisons.find((s) => s.id === Number(saisonId)) ?? null
  const precedente = saison?.courante ? saisons.find((s) => !s.courante) : null

  async function supprimer() {
    setErreur(null)
    setEnCours(true)
    try {
      await onSupprimer(saison)
    } catch (err) {
      setErreur(err.message)
      setEnCours(false)
    }
  }

  return (
    <Modal
      title="Supprimer une saison"
      onClose={onClose}
      footer={
        <button
          type="button"
          className="btn btn--danger btn--block"
          disabled={enCours || !saison || confirmation.trim() !== saison.nom}
          onClick={supprimer}
        >
          Supprimer définitivement
        </button>
      }
    >
      <div className="form-fields">
        <label htmlFor="saison-a-supprimer">Saison à supprimer</label>
        <select
          id="saison-a-supprimer"
          className="field-input"
          value={saisonId}
          onChange={(e) => {
            setSaisonId(e.target.value)
            setConfirmation('')
          }}
        >
          <option value="">Choisir une saison…</option>
          {saisons.map((s) => (
            <option key={s.id} value={s.id}>
              {s.courante ? `${s.nom} (courante)` : s.nom}
            </option>
          ))}
        </select>
      </div>

      {saison && (
        <div className="saison-panneau__suppression">
          <p>
            Tout ce qui appartient à la saison <strong>{saison.nom}</strong> sera supprimé définitivement :
            élèves, professeurs et administrateurs de cette saison, cours, présences, chorégraphies, vidéos
            (fichiers compris), conversations et messages, inscriptions.
          </p>
          {precedente && (
            <p>
              C’est la saison courante : la saison <strong>{precedente.nom}</strong> redeviendra la saison
              courante, de nouveau modifiable, et seules ses fiches pourront se connecter.
            </p>
          )}
          <p className="muted">
            Une sauvegarde complète de l’école est enregistrée sur le serveur juste avant (menu ⋮ d’Admin &gt;
            École).
          </p>
          <div className="form-fields">
            <label htmlFor="saison-confirmation">
              Pour confirmer, tapez le nom de la saison : <strong>{saison.nom}</strong>
            </label>
            <input
              id="saison-confirmation"
              className="field-input"
              value={confirmation}
              autoComplete="off"
              onChange={(e) => setConfirmation(e.target.value)}
            />
          </div>
        </div>
      )}

      {erreur && <p className="login-screen__erreur">{erreur}</p>}
    </Modal>
  )
}

// Section "Saison <saison affichée>" d'Admin > École (spec §5.1.1,
// libellé demandé par l'utilisateur le 2026-09-24), repliable comme
// "Usage vidéo", entre les codes d'accès et les administrateurs. Chargée
// dès l'affichage : son titre donne le nom de la saison affichée.
export default function SaisonsSection({ ecoleId, documents, onSaisonCreee, onSaisonSupprimee }) {
  const [ouvert, setOuvert] = useState(false)
  const [saisons, setSaisons] = useState([])
  const [panneau, setPanneau] = useState(null) // 'creation' | 'edition' | 'suppression' | null
  const consultee = useSaisonConsultee()
  const courante = saisons.find((s) => s.courante) ?? null

  function recharger() {
    return saisonsApi
      .lister(ecoleId)
      .then(setSaisons)
      .catch((err) => console.error(err))
  }

  useEffect(() => {
    recharger()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ecoleId])

  function choisir(id) {
    const saison = saisons.find((s) => s.id === Number(id))
    consulterSaison(saison && !saison.courante ? saison : null)
  }

  // Pas de rechargement ici : la fiche de l'admin vient de passer dans
  // l'ancienne saison, le serveur refuserait. L'appli bascule sur sa
  // nouvelle fiche (voir App.jsx : surSaisonCreee), ce qui recrée cette
  // section (voir `key` dans AdminParametres.jsx) et la recharge.
  async function creer(donnees) {
    const resultat = await saisonsApi.creer(ecoleId, donnees)
    setPanneau(null)
    onSaisonCreee?.(resultat)
  }

  // Rechargement ici seulement si l'admin garde sa fiche (ancienne saison
  // supprimée) ; sinon l'appli bascule sur une autre fiche, ce qui recrée
  // cette section (même principe que `creer`).
  async function supprimer(saison) {
    const resultat = await saisonsApi.supprimer(ecoleId, saison.id)
    setPanneau(null)
    const garde = onSaisonSupprimee?.({ ...resultat, saisonId: saison.id })
    if (garde) await recharger()
  }

  async function editer(donnees) {
    await saisonsApi.modifierCourante(ecoleId, donnees)
    setPanneau(null)
    await recharger()
  }

  return (
    <section className="admin-saisons">
      <h3 className="section-label">
        <button
          type="button"
          className="section-label__depliant"
          aria-expanded={ouvert}
          onClick={() => setOuvert((o) => !o)}
        >
          <Icon name={ouvert ? 'chevronDown' : 'chevronRight'} size={14} />
          Saisons ({consultee?.nom ?? courante?.nom ?? ''} Sélectionnée)
        </button>
      </h3>
      {ouvert && courante && (
        <div className="admin-saisons__contenu">
          <div className="form-fields">
            <label htmlFor="saison-affichee">Saison affichée</label>
            <select
              id="saison-affichee"
              className="field-input"
              value={consultee?.id ?? courante.id}
              onChange={(e) => choisir(e.target.value)}
            >
              {saisons.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.courante ? `${s.nom} (courante)` : `${s.nom} (lecture seule)`}
                </option>
              ))}
            </select>
          </div>
          <div className="admin-saisons__actions">
            <button type="button" className="btn btn--secondary" onClick={() => setPanneau('creation')}>
              Créer une saison
            </button>
            <button type="button" className="btn btn--secondary" onClick={() => setPanneau('edition')}>
              Éditer saison courante
            </button>
            {saisons.length > 1 && (
              <button type="button" className="btn btn--secondary" onClick={() => setPanneau('suppression')}>
                Supprimer une saison
              </button>
            )}
          </div>
        </div>
      )}
      {panneau === 'suppression' && (
        <PanneauSuppression saisons={saisons} onSupprimer={supprimer} onClose={() => setPanneau(null)} />
      )}
      {panneau === 'creation' && courante && (
        <CreerSaison
          ecoleId={ecoleId}
          courante={courante}
          documents={documents}
          onCreer={creer}
          onClose={() => setPanneau(null)}
        />
      )}
      {panneau === 'edition' && courante && (
        <PanneauSaison courante={courante} onValider={editer} onClose={() => setPanneau(null)} />
      )}
    </section>
  )
}
