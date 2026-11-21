import { useEffect, useState } from 'react'
import Modal from '../../components/Modal.jsx'
import * as api from './api.js'
import { CelluleAdhesion, CelluleContact } from './Contact.jsx'
import { CelluleVerification, RubriqueVerification, ouvrirVerification } from './Dossier.jsx'
import { ouvrirStatistiques } from './Statistiques.jsx'

// Adhérents entièrement imposés par HelloAsso (spec/modules/helloasso.md §7,
// maquette https://claude.ai/artifact/4tizDZ6Br2WxGL5MYwSQfy) : ce que le
// module apporte au tableau Admin > Élèves (`memberList` du module.js, lu
// par AdminEleves.jsx) quand la saison affichée a une campagne. Rien sans
// campagne ni module éteint : le tableau reste celui de l'école.

const euros = (centimes) =>
  (centimes / 100).toLocaleString('fr-FR', {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  })

// Jamais le mot anglais à l'écran (Seb, 18 novembre).
const ETATS = { Processed: 'Validé HelloAsso', Registered: 'Enregistré', Waiting: 'En attente', Unknown: 'En attente' }
const statut = (ligne) => (ligne.cancelled ? 'Résilié' : (ETATS[ligne.state] ?? 'En attente'))

const ETATS_PAIEMENT = {
  Authorized: 'payée',
  Registered: 'à venir',
  Pending: 'à venir',
  Waiting: 'à venir',
  Refused: 'refusée',
  Error: 'en échec',
  Canceled: 'annulée',
  Abandoned: 'abandonnée',
  Refunded: 'remboursée',
  Refunding: 'en remboursement',
}

const dateFr = (iso) => (iso ? new Date(iso).toLocaleDateString('fr-FR') : '')

// « Masquer / Afficher les photos » : par appareil, comme Sambo Admin
// (beaucoup de vignettes sur une connexion lente).
const CLE_PHOTOS = 'helloasso-photos'
function photosAffichees() {
  try {
    return localStorage.getItem(CLE_PHOTOS) !== '0'
  } catch {
    return true
  }
}
function basculerPhotos() {
  try {
    localStorage.setItem(CLE_PHOTOS, photosAffichees() ? '0' : '1')
  } catch {
    // Stockage indisponible : le réglage n'est pas retenu, sans gravité.
  }
}

// Vignettes déjà lues : la liste se redessine souvent.
const vignettes = new Map()

function Vignette({ ecoleId, ficheId, taille = 128, className }) {
  const cle = `${ecoleId}/${ficheId}/${taille}`
  const [url, setUrl] = useState(vignettes.get(cle) ?? null)
  useEffect(() => {
    if (vignettes.has(cle)) return
    let actif = true
    api
      .urlPhoto(ecoleId, ficheId, taille)
      .then((u) => {
        vignettes.set(cle, u)
        if (actif) setUrl(u)
      })
      .catch(() => {})
    return () => {
      actif = false
    }
  }, [cle, ecoleId, ficheId, taille])
  return url ? <img className={className} src={url} alt="" /> : <span className={`${className} adherents__photo-vide`} />
}

// La photo d'identité : vignette, agrandie au toucher.
function Photo({ ecoleId, ficheId, nom, grande = false }) {
  const [zoom, setZoom] = useState(false)
  return (
    <>
      <button
        type="button"
        className={grande ? 'adherents__photo adherents__photo--grande' : 'adherents__photo'}
        aria-label={`Agrandir la photo de ${nom}`}
        onClick={(e) => {
          e.stopPropagation()
          setZoom(true)
        }}
      >
        <Vignette ecoleId={ecoleId} ficheId={ficheId} className="adherents__photo-img" />
      </button>
      {zoom && (
        <Modal title={nom} onClose={() => setZoom(false)}>
          <Vignette ecoleId={ecoleId} ficheId={ficheId} taille={512} className="adherents__photo-zoom" />
          <p className="muted">Photo d’identité déposée sur HelloAsso.</p>
        </Modal>
      )}
    </>
  )
}

// Les colonnes du module (spec §7.2), dans l'ordre de la maquette.
// `cellule` reçoit la ligne HelloAsso de la fiche (undefined : pas
// d'adhésion, un prof par exemple).
const COLONNES = [
  {
    key: 'helloasso_amount',
    label: 'Montant',
    texte: (l) => (l ? euros(l.amount) : ''),
  },
  {
    key: 'helloasso_code',
    label: 'Code promo',
    texte: (l) => l?.discount_code ?? '',
  },
  {
    key: 'helloasso_photo',
    label: 'Photo',
    texte: (l) => (l?.photo ? 'Photo déposée' : ''),
    cellule: ({ ecoleId, eleve, ligne }) =>
      ligne?.photo ? <Photo ecoleId={ecoleId} ficheId={eleve.id} nom={`${eleve.prenom} ${eleve.nom}`} /> : null,
    // Masquable par le menu ⋮, sur cet appareil.
    cachee: () => !photosAffichees(),
  },
  {
    key: 'helloasso_status',
    label: 'Statut HelloAsso',
    texte: (l) => (l ? statut(l) : ''),
  },
  {
    // Seulement quand l'école a allumé la vérification des dossiers (spec §7.5).
    key: 'helloasso_check',
    label: 'Vérification',
    texte: (l) => (l?.check ? (l.check.ok ? 'OK' : 'À vérifier') : ''),
    cellule: (props) => <CelluleVerification {...props} />,
    cachee: () => !verificationAllumee,
  },
]
  .map((c) => ({ ...c, nature: 'Calculé', detail: 'HelloAsso' }))
  .concat(
    // Les boutons de Sambo Admin (spec §7.6, §7.7, étape 8).
    [
      {
        key: 'helloasso_contact',
        label: 'Contact',
        texte: (l) => (l ? `${l.mails} mail${l.mails > 1 ? 's' : ''}, ${l.sms} SMS` : ''),
        cellule: (props) => <CelluleContact {...props} />,
      },
      {
        key: 'helloasso_cancel',
        label: 'Adhésion',
        texte: (l) => (l?.cancelled ? 'Résiliée' : ''),
        cellule: (props) => <CelluleAdhesion {...props} />,
      },
    ].map((c) => ({ ...c, nature: 'Bouton', detail: 'HelloAsso' })),
  )
// Une colonne de module : { key, label, nature ('Calculé' ou 'Bouton'),
// detail, texte(ligne), cellule?({ ecoleId, eleve, ligne, relire }),
// cachee?() }.

// Le dernier tableau lu : la colonne Vérification et le menu ⋮ en dépendent.
let verificationAllumee = false
let ecoleLue = null

// → null (rien ne change) ou { members, can_refresh, form_name }.
async function charger(ecoleId) {
  try {
    const lu = await api.adherents(ecoleId)
    if (!lu.imposed) return null
    verificationAllumee = lu.checks_on
    ecoleLue = ecoleId
    // « Résilier » demande l'Accès au Financier (spec §7.7) : sur chaque ligne.
    for (const ligne of Object.values(lu.members)) ligne.can_cancel = lu.can_cancel
    return lu
  } catch (erreur) {
    // Module éteint (404) ou pas le droit : rien ne change. Serveur
    // injoignable : l'appelant réessaie (sinon « Élèves (0) », Seb 21/11).
    if (erreur.status >= 400 && erreur.status < 500) return null
    throw erreur
  }
}

// Ses colonnes dans le tableau (spec/core.md §11.1), seulement quand la
// saison affichée a une campagne.
export const memberColumns = { charger, colonnes: COLONNES }

export const memberList = {
  charger,
  // Sans affichage enregistré, le tableau de Sambo Admin (Seb, 18 novembre).
  ordreParDefaut: ['nom', 'email', ...COLONNES.map((c) => c.key)],
  // Une adhésion résiliée reste, grisée (spec §7.1).
  resiliee: (donnees, eleve) => Boolean(donnees.members[eleve.id]?.cancelled),
  // L'ordre de Sambo Admin, celui de HelloAsso : la commande la plus récente
  // d'abord (Seb, 18 novembre 2026). Une fiche sans adhésion va à la fin.
  ordre: (donnees, eleves) =>
    [...eleves].sort((a, b) => (donnees.members[a.id]?.rank ?? Infinity) - (donnees.members[b.id]?.rank ?? Infinity)),
  // Comme Sambo Admin, « Adhérents (n) » ne compte que les adhésions HelloAsso
  // non résiliées : une fiche sans adhésion (un prof, par exemple) reste dans
  // la liste, en dernier, sans être comptée.
  compte: (donnees, eleves) =>
    eleves.filter((el) => donnees.members[el.id] && !donnees.members[el.id].cancelled).length,
  // « Rafraîchir » : synchronise maintenant (la saison en cours).
  rafraichir: (ecoleId) => api.synchroniser(ecoleId),
  menu: (redessiner) => [
    { label: 'Statistiques des adhérents de la saison', icon: 'calculator', onClick: () => ouvrirStatistiques(ecoleLue) },
    ...(verificationAllumee
      ? [{ label: 'Vérifier les adhérents', icon: 'check', onClick: () => ouvrirVerification(ecoleLue) }]
      : []),
    {
      label: photosAffichees() ? 'Masquer les photos' : 'Afficher les photos',
      icon: 'camera',
      onClick: () => {
        basculerPhotos()
        redessiner()
      },
    },
  ],
  Fiche,
}

// Dans la fiche de l'adhérent (spec §7.3) : la photo, l'adhésion, les
// documents déposés (lus chez HelloAsso, jamais gardés), les réponses au
// formulaire, le payeur et les paiements.
function Fiche({ ecoleId, eleve }) {
  const [fiche, setFiche] = useState(null)
  const [erreur, setErreur] = useState('')
  const [lecture, setLecture] = useState(0)
  useEffect(() => {
    api.adherent(ecoleId, eleve.id).then(setFiche).catch(() => setFiche(null))
  }, [ecoleId, eleve.id, lecture])
  if (!fiche) return null

  async function ouvrir(index) {
    setErreur('')
    // Ouvert tout de suite (sinon le navigateur bloque la fenêtre), rempli ensuite.
    const fenetre = window.open('', '_blank')
    try {
      const url = await api.urlFichier(ecoleId, eleve.id, index)
      if (fenetre) fenetre.location.replace(url)
    } catch (e) {
      fenetre?.close()
      setErreur(e.message)
    }
  }

  const nom = `${eleve.prenom} ${eleve.nom}`
  return (
    <>
      {fiche.photo && (
        <div className="adherents__fiche-photo">
          <Photo ecoleId={ecoleId} ficheId={eleve.id} nom={nom} grande />
        </div>
      )}
      <Rubrique titre="Adhésion">
        <Ligne libelle="Formule" valeur={fiche.tier_name} />
        <Ligne libelle="Montant" valeur={euros(fiche.amount)} />
        <Ligne libelle="Code promo" valeur={fiche.discount_code} />
        <Ligne libelle="Statut HelloAsso" valeur={statut(fiche)} />
      </Rubrique>
      <RubriqueVerification
        ecoleId={ecoleId}
        eleve={eleve}
        check={fiche.check}
        onChange={() => setLecture((n) => n + 1)}
        Rubrique={Rubrique}
      />
      {fiche.files.length > 0 && (
        <Rubrique titre="Documents déposés sur HelloAsso">
          <div className="adherents__documents">
            {fiche.files.map((f) => (
              <button key={f.index} type="button" className="btn btn--secondary" onClick={() => ouvrir(f.index)}>
                {f.name}
              </button>
            ))}
          </div>
          {erreur && <p className="login-screen__erreur">{erreur}</p>}
        </Rubrique>
      )}
      {fiche.answers.length > 0 && (
        <Rubrique titre="Réponses au formulaire">
          {fiche.answers.map((a, i) => (
            <Ligne key={i} libelle={a.name} valeur={String(a.answer)} />
          ))}
          <p className="muted">Modifiable sur HelloAsso.</p>
        </Rubrique>
      )}
      <Rubrique titre="Payeur">
        <Ligne libelle="Nom" valeur={fiche.payer_name} />
        <Ligne libelle="Email" valeur={fiche.payer_email} />
      </Rubrique>
      <Rubrique titre="Paiements">
        {fiche.payments.length === 0 && <Ligne valeur="" />}
        {fiche.payments.map((p, i) => (
          <Ligne
            key={i}
            libelle={dateFr(p.date)}
            valeur={`${euros(p.amount)} ${ETATS_PAIEMENT[p.state] ?? 'à venir'}`}
          />
        ))}
      </Rubrique>
      <Rubrique titre="Messages envoyés">
        {fiche.messages.length === 0 && <Ligne valeur="Aucun" />}
        {fiche.messages.map((m, i) => (
          <Ligne
            key={i}
            libelle={`${dateFr(m.at)}, ${m.kind === 'mail' ? 'mail' : 'SMS préparé'}`}
            valeur={m.sent ? m.subject || m.body : `Pas parti : ${m.error}`}
          />
        ))}
      </Rubrique>
    </>
  )
}

// Comme dans FicheEleve.jsx.
function Rubrique({ titre, children }) {
  return (
    <section className="fiche-eleve__rubrique">
      <h3 className="fiche-eleve__titre">{titre}</h3>
      {children}
    </section>
  )
}

function Ligne({ libelle, valeur }) {
  return (
    <div className="fiche-eleve__ligne">
      {libelle && <span className="muted">{libelle}</span>}
      <span>{valeur || <span className="muted">—</span>}</span>
    </div>
  )
}
