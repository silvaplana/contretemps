import { useEffect, useState } from 'react'
import { consulterSaison, useSaisonConsultee } from '../../api/saison.js'
import * as saisonsApi from '../../api/saisons.js'
import Icon from '../../components/Icon.jsx'
import Modal from '../../components/Modal.jsx'

// Proposition pour la saison suivante : "2026-2027" -> "2027-2028", dates
// décalées d'un an. Juste un point de départ, tout reste modifiable.
function saisonSuivante(courante) {
  const decaler = (iso) => (iso ? `${Number(iso.slice(0, 4)) + 1}${iso.slice(4)}` : '')
  const annees = courante?.nom.match(/^(\d{4})-(\d{4})$/)
  return {
    nom: annees ? `${Number(annees[1]) + 1}-${Number(annees[2]) + 1}` : '',
    dateDebut: decaler(courante?.dateDebut),
    dateFin: decaler(courante?.dateFin),
  }
}

// Panneau "Créer nouvelle saison" / "Éditer saison courante" (spec §2.6 et
// §5.1.1) : nom et dates, plus — en création seulement — les cases de
// duplication, dans l'ordre profs → cours → élèves : chacune n'est
// possible que si la précédente est cochée (on ne recopie pas des cours
// sans leurs profs, ni des élèves sans leurs cours).
function PanneauSaison({ mode, courante, onValider, onClose }) {
  const [champs, setChamps] = useState(() =>
    mode === 'creation'
      ? saisonSuivante(courante)
      : { nom: courante.nom, dateDebut: courante.dateDebut, dateFin: courante.dateFin },
  )
  const [cases, setCases] = useState({ profs: false, cours: false, eleves: false })
  const [erreur, setErreur] = useState(null)
  const [enCours, setEnCours] = useState(false)

  function cocher(nom, coche) {
    setCases((c) => {
      if (nom === 'profs') return coche ? { ...c, profs: true } : { profs: false, cours: false, eleves: false }
      if (nom === 'cours') return coche ? { ...c, cours: true } : { ...c, cours: false, eleves: false }
      return { ...c, eleves: coche }
    })
  }

  async function valider() {
    setErreur(null)
    setEnCours(true)
    try {
      await onValider({ ...champs, cases })
    } catch (err) {
      setErreur(err.message)
      setEnCours(false)
    }
  }

  return (
    <Modal
      title={mode === 'creation' ? 'Créer nouvelle saison' : 'Éditer saison courante'}
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

      {mode === 'creation' && (
        <div className="saison-panneau__duplication">
          <p className="muted">Recopier depuis la saison {courante.nom} :</p>
          <label className="checkbox-inline">
            <input type="checkbox" checked={cases.profs} onChange={(e) => cocher('profs', e.target.checked)} />
            Professeurs
          </label>
          <label className="checkbox-inline">
            <input
              type="checkbox"
              checked={cases.cours}
              disabled={!cases.profs}
              onChange={(e) => cocher('cours', e.target.checked)}
            />
            Cours
          </label>
          <label className="checkbox-inline">
            <input
              type="checkbox"
              checked={cases.eleves}
              disabled={!cases.cours}
              onChange={(e) => cocher('eleves', e.target.checked)}
            />
            Élèves (avec les mêmes cours)
          </label>
          <p className="muted saison-panneau__note">
            Les administrateurs sont toujours recopiés. Dès la validation, la nouvelle saison devient la
            saison courante et la saison {courante.nom} passe en lecture seule.
          </p>
        </div>
      )}

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
export default function SaisonsSection({ ecoleId, onSaisonCreee, onSaisonSupprimee }) {
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
          Saison {consultee?.nom ?? courante?.nom ?? ''}
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
              Créer nouvelle saison
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
      {(panneau === 'creation' || panneau === 'edition') && courante && (
        <PanneauSaison
          mode={panneau}
          courante={courante}
          onValider={panneau === 'creation' ? creer : editer}
          onClose={() => setPanneau(null)}
        />
      )}
    </section>
  )
}
