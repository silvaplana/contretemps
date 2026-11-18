import { useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import Modal from '../../components/Modal.jsx'
import { enEuros } from '../../utils/euros.js'
import * as api from './api.js'
import { MailModal, dehors, useToast } from './Contact.jsx'

// Vérification des dossiers (spec/modules/helloasso.md §7.5, maquette
// « Adhérents ASC ») : colonne « Vérification » (OK ou « À vérifier »),
// l'écran du dossier, la rubrique de la fiche et ⋮ > Vérifier les adhérents.

// Ouvert tout de suite (sinon le navigateur bloque la fenêtre), rempli ensuite.
async function ouvrirFichier(ecoleId, ficheId, index) {
  const fenetre = window.open('', '_blank')
  try {
    const url = await api.urlFichier(ecoleId, ficheId, index)
    if (fenetre) fenetre.location.replace(url)
  } catch (e) {
    fenetre?.close()
    throw e
  }
}

// « Valider le dossier », avec Annuler 10 s (rien n'est perdu : les raisons restent).
function useValider(ecoleId, eleve, apres) {
  const [toast, montrer] = useToast()
  async function valider() {
    await api.validerDossier(ecoleId, eleve.id)
    apres()
    montrer('Dossier validé', async () => {
      await api.devaliderDossier(ecoleId, eleve.id)
      apres()
    })
  }
  return [toast, valider]
}

function DossierModal({ ecoleId, eleve, check, onClose, onEcrire, onValider }) {
  const [fichiers, setFichiers] = useState([])
  const [erreur, setErreur] = useState('')
  useEffect(() => {
    api
      .adherent(ecoleId, eleve.id)
      .then((f) => setFichiers(f.files))
      .catch(() => setFichiers([]))
  }, [ecoleId, eleve.id])
  return (
    <Modal
      title={`Dossier de ${eleve.prenom} ${eleve.nom}`}
      onClose={onClose}
      footer={
        <div className="contact__pied">
          <button type="button" className="btn btn--secondary" onClick={onEcrire}>
            Écrire à l’adhérent
          </button>
          <button type="button" className="btn btn--primary" onClick={onValider}>
            Valider le dossier
          </button>
        </div>
      }
    >
      <ul>
        {check.issues.map((raison, i) => (
          <li key={i}>{raison}</li>
        ))}
      </ul>
      {fichiers.length > 0 && (
        <div className="adherents__documents">
          {fichiers.map((f) => (
            <button
              key={f.index}
              type="button"
              className="btn btn--secondary"
              onClick={() => ouvrirFichier(ecoleId, eleve.id, f.index).catch((e) => setErreur(e.message))}
            >
              {f.name}
            </button>
          ))}
        </div>
      )}
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
    </Modal>
  )
}

// Colonne « Vérification » : vide tant que le dossier n'a pas été vérifié.
export function CelluleVerification({ ecoleId, eleve, ligne, relire }) {
  const [ouvert, setOuvert] = useState(null) // null | 'dossier' | 'mail'
  const [toast, valider] = useValider(ecoleId, eleve, () => relire?.())
  const [toastMail, montrerMail] = useToast()
  const check = ligne?.check
  if (!check) return null
  return (
    <div onClick={(e) => e.stopPropagation()}>
      {check.ok ? (
        <span className="dossier__ok">OK</span>
      ) : (
        <button type="button" className="btn btn--link dossier__a-verifier" onClick={() => setOuvert('dossier')}>
          À vérifier
        </button>
      )}
      {ouvert === 'dossier' &&
        dehors(
          <DossierModal
            ecoleId={ecoleId}
            eleve={eleve}
            check={check}
            onClose={() => setOuvert(null)}
            onEcrire={() => setOuvert('mail')}
            onValider={() => {
              setOuvert(null)
              valider()
            }}
          />,
        )}
      {ouvert === 'mail' &&
        dehors(
          <MailModal
            ecoleId={ecoleId}
            eleve={eleve}
            ligne={ligne}
            onClose={() => setOuvert(null)}
            onEnvoye={(texte) => {
              setOuvert(null)
              montrerMail(texte)
              relire?.()
            }}
          />,
        )}
      {toast}
      {toastMail}
    </div>
  )
}

// La rubrique de la fiche (spec §7.3) ; rien tant que le dossier n'a pas été vérifié.
export function RubriqueVerification({ ecoleId, eleve, check, onChange, Rubrique }) {
  const [toast, valider] = useValider(ecoleId, eleve, onChange)
  if (!check) return null
  return (
    <Rubrique titre="Vérification du dossier">
      {check.ok ? (
        <p className="dossier__ok">OK</p>
      ) : (
        <>
          <ul>
            {check.issues.map((raison, i) => (
              <li key={i}>{raison}</li>
            ))}
          </ul>
          <button type="button" className="btn btn--secondary" onClick={valider}>
            Valider le dossier
          </button>
        </>
      )}
      {toast}
    </Rubrique>
  )
}

function VerificationModal({ ecoleId, onClose }) {
  const [etat, setEtat] = useState(null)
  const [erreur, setErreur] = useState('')
  const [toast, montrer] = useToast()
  const [lancee, setLancee] = useState(false)
  useEffect(() => {
    api
      .verification(ecoleId)
      .then(setEtat)
      .catch((e) => setErreur(e.message))
  }, [ecoleId])

  async function relancer() {
    setErreur('')
    try {
      setEtat(await api.verifier(ecoleId))
      setLancee(true)
      montrer('Vérification relancée, le rapport arrive par mail')
      setTimeout(onClose, 2500)
    } catch (e) {
      setErreur(e.message)
    }
  }

  const n = etat?.to_check ?? 0
  return (
    <Modal
      title="Vérification des adhérents"
      onClose={onClose}
      footer={
        <div className="contact__pied">
          <button type="button" className="btn btn--secondary" onClick={onClose}>
            Annuler
          </button>
          <button
            type="button"
            className="btn btn--primary"
            onClick={relancer}
            disabled={!etat?.can_run || etat.running || lancee || n === 0}
          >
            Relancer la vérification
          </button>
        </div>
      }
    >
      {etat && (
        <>
          <p>
            {n === 0
              ? 'Tous les dossiers sont OK.'
              : `${n} dossier${n > 1 ? 's' : ''} à vérifier. Les dossiers déjà OK ne sont pas revérifiés.`}
          </p>
          {etat.running && !lancee && <p>Une vérification est en cours ; le rapport arrive par mail.</p>}
          {!etat.can_run && <p className="muted">Vérifier les adhérents demande l’accès au Financier.</p>}
          <p className="muted">Coût cumulé des vérifications de dossiers : {enEuros(etat.cost)}</p>
        </>
      )}
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
      {toast}
    </Modal>
  )
}

// ⋮ > Vérifier les adhérents : l'écran s'ouvre hors du tableau.
export function ouvrirVerification(ecoleId) {
  const hote = document.createElement('div')
  document.body.appendChild(hote)
  const racine = createRoot(hote)
  const fermer = () => {
    racine.unmount()
    hote.remove()
  }
  racine.render(<VerificationModal ecoleId={ecoleId} onClose={fermer} />)
}
