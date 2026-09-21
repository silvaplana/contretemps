import { useRef, useState } from 'react'
import * as ecolesApi from '../../api/ecoles.js'
import * as inscriptionsApi from '../../api/inscriptions.js'
import Icon from '../../components/Icon.jsx'
import Modal from '../../components/Modal.jsx'
import { useFermerAuClicExterieur } from '../../hooks/useFermerAuClicExterieur.js'
import { estConfigureDrive } from '../../utils/googleDrive.js'
import IntegrerFichierElevesModal from './IntegrerFichierElevesModal.jsx'

const JOURS = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
const PERIODICITES = [
  { valeur: 'jour', label: 'Chaque jour' },
  { valeur: 'semaine', label: 'Chaque semaine' },
  { valeur: 'mois', label: 'Chaque mois (le 1er)' },
]

// Destination du "Sauvegarder École" manuel (voir api/ecoles.js) —
// mémorisée PAR NAVIGATEUR (localStorage), pas en base : c'est un
// confort d'usage propre à cet appareil, pas une donnée d'école (voir
// "Programmer sauvegarde École", elle, bien en base — demande utilisateur
// explicite, partagée entre admins). "Google Drive" n'est proposé que si
// VITE_GOOGLE_CLIENT_ID est configuré (voir googleDrive.js).
const CLE_DESTINATION = 'contretemps-sauvegarde-destination'

function destinationMemorisee() {
  try {
    const valeur = localStorage.getItem(CLE_DESTINATION)
    return valeur === 'drive' && estConfigureDrive() ? 'drive' : 'local'
  } catch {
    return 'local'
  }
}

// Menu ⋮ "Sauvegarde" d'Admin > École (5 entrées, voir spec — demande
// utilisateur explicite) :
// 1. "Sauvegarder École" — génère + télécharge tout de suite les 2
//    fichiers (export humain + sauvegarde technique complète).
// 2. "Programmer sauvegarde École" — réglage EN BASE (voir
//    ecoles/models.py : sauvegarde_*), partagé entre tous les admins/
//    appareils — un worker séparé (backend/src/app/sauvegarde_worker.py)
//    génère alors les 2 fichiers côté serveur à l'heure dite, en filet de
//    sécurité (jamais perdu même si personne n'a l'appli ouverte).
// 3. "Télécharger les nouveaux inscrits" — reprend le bouton existant
//    (voir api/inscriptions.js), juste déplacé ici.
// 4. "Supprimer Données École" — IRRÉVERSIBLE, confirmation par saisie du
//    nom de l'école (voir ConfirmationNomModal).
// 5. "Importer sauvegarde" — ÉCRASE tout depuis un fichier technique,
//    même confirmation, puis recharge la page (demande utilisateur
//    explicite : "Puis la recharge") pour repartir d'un état propre.
// 6. "Intégrer fichier élèves officiel" — MÊME modale que le bouton
//    "Importer" d'Admin > Élèves (voir IntegrerFichierElevesModal.jsx,
//    demande utilisateur explicite : une seule implémentation).
export default function SauvegardeEcoleMenu({ ecole, cours, setEleves }) {
  const [menuOuvert, setMenuOuvert] = useState(false)
  const [vue, setVue] = useState(null) // null | 'programmer' | 'supprimer' | 'importer' | 'integrerFichier'
  const [erreur, setErreur] = useState(null)
  const [destination, setDestination] = useState(destinationMemorisee)
  const menuRef = useRef(null)
  useFermerAuClicExterieur(menuRef, menuOuvert, () => setMenuOuvert(false))

  function changerDestination(valeur) {
    setDestination(valeur)
    try {
      localStorage.setItem(CLE_DESTINATION, valeur)
    } catch {
      // Stockage indisponible (navigation privée...) : le choix ne
      // survivra pas à la fermeture de l'onglet, tant pis — pas bloquant
      // pour la fonctionnalité elle-même (voir artifact-capabilities :
      // toujours prévoir un lecture/écriture qui peut échouer).
    }
  }

  async function sauvegarder() {
    setMenuOuvert(false)
    setErreur(null)
    try {
      // Séquentiel, pas Promise.all : 2 boîtes "Enregistrer sous" (ou 2
      // consentements Drive) ouvertes en même temps prêteraient à
      // confusion (laquelle est laquelle ?).
      await ecolesApi.telechargerExportHumain(ecole.id, destination)
      await ecolesApi.telechargerExportTechnique(ecole.id, destination)
    } catch (err) {
      setErreur(err.message)
    }
  }

  function telechargerInscriptions() {
    setMenuOuvert(false)
    setErreur(null)
    inscriptionsApi.telechargerNouvellesInscriptions(ecole.id).catch((err) => setErreur(err.message))
  }

  function ouvrir(nomVue) {
    setVue(nomVue)
    setMenuOuvert(false)
  }

  return (
    <>
      <div className="header-menu" ref={menuRef}>
        <button
          type="button"
          className="icon-btn"
          onClick={() => setMenuOuvert((o) => !o)}
          aria-label="Menu sauvegarde"
        >
          <Icon name="moreVertical" />
        </button>
        {menuOuvert && (
          <div className="dropdown-menu header-menu__panel">
            {estConfigureDrive() && (
              <div className="header-menu__destination" onClick={(e) => e.stopPropagation()}>
                <span className="muted">Destination de "Sauvegarder École"</span>
                <label>
                  <input
                    type="radio"
                    name="sauvegarde-destination"
                    checked={destination === 'local'}
                    onChange={() => changerDestination('local')}
                  />
                  Cet appareil
                </label>
                <label>
                  <input
                    type="radio"
                    name="sauvegarde-destination"
                    checked={destination === 'drive'}
                    onChange={() => changerDestination('drive')}
                  />
                  Google Drive
                </label>
              </div>
            )}
            <button type="button" onClick={sauvegarder}>
              <Icon name="folder" size={18} /> Sauvegarder École
            </button>
            <button type="button" onClick={() => ouvrir('programmer')}>
              <Icon name="clock" size={18} /> Programmer sauvegarde École
            </button>
            <button type="button" onClick={telechargerInscriptions}>
              <Icon name="fileCheck" size={18} /> Télécharger les nouveaux inscrits
            </button>
            <button type="button" onClick={() => ouvrir('importer')}>
              <Icon name="folder" size={18} /> Importer sauvegarde
            </button>
            <button type="button" onClick={() => ouvrir('integrerFichier')}>
              <Icon name="fileCheck" size={18} /> Intégrer fichier élèves officiel
            </button>
            <button type="button" className="header-menu__danger" onClick={() => ouvrir('supprimer')}>
              <Icon name="trash" size={18} /> Supprimer Données École
            </button>
          </div>
        )}
      </div>

      {erreur && <p className="admin-panel__erreur">{erreur}</p>}

      {vue === 'programmer' && <ProgrammerSauvegardeModal ecole={ecole} onClose={() => setVue(null)} />}
      {vue === 'supprimer' && <SupprimerDonneesModal ecole={ecole} onClose={() => setVue(null)} />}
      {vue === 'importer' && <ImporterSauvegardeModal ecole={ecole} onClose={() => setVue(null)} />}
      {vue === 'integrerFichier' && (
        <IntegrerFichierElevesModal
          ecoleId={ecole.id}
          cours={cours}
          setEleves={setEleves}
          onClose={() => setVue(null)}
        />
      )}
    </>
  )
}

// --- "Programmer sauvegarde École" ---

function ProgrammerSauvegardeModal({ ecole, onClose }) {
  const [active, setActive] = useState(ecole.sauvegardeActive)
  const [periodicite, setPeriodicite] = useState(ecole.sauvegardePeriodicite ?? 'semaine')
  const [jourSemaine, setJourSemaine] = useState(ecole.sauvegardeJourSemaine ?? 0)
  const [heure, setHeure] = useState(ecole.sauvegardeHeure ?? '03:00')
  const [enregistrementEnCours, setEnregistrementEnCours] = useState(false)
  const [erreur, setErreur] = useState(null)

  async function enregistrer() {
    if (enregistrementEnCours) return
    setEnregistrementEnCours(true)
    setErreur(null)
    try {
      await ecolesApi.programmerSauvegarde(ecole.id, {
        active,
        periodicite,
        jourSemaine: periodicite === 'semaine' ? jourSemaine : null,
        heure,
      })
      onClose()
    } catch (err) {
      setErreur(err.message)
    } finally {
      setEnregistrementEnCours(false)
    }
  }

  return (
    <Modal
      title="Programmer sauvegarde École"
      onClose={onClose}
      footer={
        <button
          type="button"
          className="btn btn--primary btn--block"
          disabled={enregistrementEnCours}
          onClick={enregistrer}
        >
          Enregistrer
        </button>
      }
    >
      <p className="muted">
        Réglage partagé entre tous les admins de l'école, sur tous les appareils — un déclenchement
        automatique génère les 2 fichiers de sauvegarde et les garde en sécurité sur le serveur.
      </p>

      <label className="checkbox-inline">
        <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} />
        Sauvegarde programmée activée
      </label>

      <label htmlFor="sauvegarde-periodicite">Périodicité</label>
      <select
        id="sauvegarde-periodicite"
        className="field-input"
        value={periodicite}
        onChange={(e) => setPeriodicite(e.target.value)}
      >
        {PERIODICITES.map((p) => (
          <option key={p.valeur} value={p.valeur}>
            {p.label}
          </option>
        ))}
      </select>

      {periodicite === 'semaine' && (
        <>
          <label htmlFor="sauvegarde-jour">Jour</label>
          <select
            id="sauvegarde-jour"
            className="field-input"
            value={jourSemaine}
            onChange={(e) => setJourSemaine(Number(e.target.value))}
          >
            {JOURS.map((j, i) => (
              <option key={j} value={i}>
                {j}
              </option>
            ))}
          </select>
        </>
      )}

      <label htmlFor="sauvegarde-heure">Heure</label>
      <input
        id="sauvegarde-heure"
        type="time"
        className="field-input"
        value={heure}
        onChange={(e) => setHeure(e.target.value)}
      />

      {erreur && <p className="admin-panel__erreur">{erreur}</p>}
    </Modal>
  )
}

// --- Confirmation partagée par "Supprimer" et "Importer" (irréversibles,
// décision utilisateur explicite : retaper le nom exact de l'école) ---

function ConfirmationNomModal({ titre, description, nomEcole, boutonLabel, enCours, erreur, onConfirm, onClose }) {
  const [saisie, setSaisie] = useState('')
  const pretACConfirmer = saisie.trim() === nomEcole

  return (
    <Modal title={titre} onClose={onClose}>
      <p>{description}</p>
      <label htmlFor="confirmation-nom-ecole">
        Tapez <strong>{nomEcole}</strong> pour confirmer
      </label>
      <input
        id="confirmation-nom-ecole"
        className="field-input"
        value={saisie}
        onChange={(e) => setSaisie(e.target.value)}
        autoComplete="off"
      />
      {erreur && <p className="admin-panel__erreur">{erreur}</p>}
      <button
        type="button"
        className="btn btn--danger btn--block"
        disabled={!pretACConfirmer || enCours}
        onClick={onConfirm}
        style={{ marginTop: 12 }}
      >
        {boutonLabel}
      </button>
    </Modal>
  )
}

// --- "Supprimer Données École" ---

function SupprimerDonneesModal({ ecole, onClose }) {
  const [enCours, setEnCours] = useState(false)
  const [erreur, setErreur] = useState(null)

  async function confirmer() {
    if (enCours) return
    setEnCours(true)
    setErreur(null)
    try {
      await ecolesApi.supprimerDonnees(ecole.id)
      // Toutes les données (élèves, profs, cours, conversations,
      // présences...) viennent de disparaître : un rechargement complet
      // est le seul moyen sûr de resynchroniser tout l'état de l'appli
      // (mêmes principe que "Importer sauvegarde", voir ImporterSauvegardeModal).
      window.location.reload()
    } catch (err) {
      setErreur(err.message)
      setEnCours(false)
    }
  }

  return (
    <ConfirmationNomModal
      titre="Supprimer Données École"
      description={
        <>
          Supprime <strong>définitivement</strong> tous les élèves, professeurs, cours, conversations,
          messages et présences de cette école — seuls le nom de l'école et le compte admin le plus
          ancien sont conservés. Cette action est <strong>irréversible</strong>.
        </>
      }
      nomEcole={ecole.nom}
      boutonLabel="Supprimer définitivement"
      enCours={enCours}
      erreur={erreur}
      onConfirm={confirmer}
      onClose={onClose}
    />
  )
}

// --- "Importer sauvegarde" ---

function ImporterSauvegardeModal({ ecole, onClose }) {
  const [fichier, setFichier] = useState(null)
  const [enCours, setEnCours] = useState(false)
  const [erreur, setErreur] = useState(null)

  async function confirmer() {
    if (enCours || !fichier) return
    setEnCours(true)
    setErreur(null)
    try {
      await ecolesApi.restaurer(ecole.id, fichier)
      // Demande utilisateur explicite : "Puis la recharge" — voir
      // SupprimerDonneesModal, même raison (tout l'état de l'appli doit
      // repartir de zéro après un tel écrasement).
      window.location.reload()
    } catch (err) {
      setErreur(err.message)
      setEnCours(false)
    }
  }

  if (!fichier) {
    return (
      <Modal title="Importer sauvegarde" onClose={onClose}>
        <p>
          Choisissez un fichier de sauvegarde technique (<code>..._techBackup.xlsx</code>, voir
          "Sauvegarder École") — son contenu remplacera <strong>entièrement</strong> les données
          actuelles de cette école.
        </p>
        <input
          type="file"
          accept=".xlsx"
          onChange={(e) => setFichier(e.target.files[0] ?? null)}
        />
      </Modal>
    )
  }

  return (
    <ConfirmationNomModal
      titre="Importer sauvegarde"
      description={
        <>
          Le fichier <strong>{fichier.name}</strong> va <strong>écraser définitivement</strong> toutes
          les données actuelles de cette école (élèves, professeurs, cours, conversations, messages,
          présences). Cette action est <strong>irréversible</strong>.
        </>
      }
      nomEcole={ecole.nom}
      boutonLabel="Écraser et restaurer"
      enCours={enCours}
      erreur={erreur}
      onConfirm={confirmer}
      onClose={onClose}
    />
  )
}
