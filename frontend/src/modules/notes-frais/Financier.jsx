import { useCallback, useEffect, useState } from 'react'
import * as api from '../../api/notesFrais.js'
import * as finApi from '../finances/api.js'
import * as sessionApi from '../../api/session.js'
import MenuEntete from '../../components/MenuEntete.jsx'
import SegmentedTabs from '../../components/SegmentedTabs.jsx'
import AssembleeGenerale, { requestGeneralTemplate, requestNewAssembly } from '../finances/AssembleeGenerale.jsx'
import Bilan, { requestNewReport } from '../finances/Bilan.jsx'
import Comptes, { requestBank, requestStatementImport } from '../finances/Comptes.jsx'
import { FICHE_PIECE_EVENT, SOUS_ONGLET_EVENT } from '../finances/navigation.js'
import { requestStatements } from '../finances/RelevesGrille.jsx'
import { requestPlanComptable } from '../finances/compta/PlanComptable.jsx'
import { requestSoldesDepart } from '../finances/compta/SoldesDepart.jsx'
import { requestBalance } from '../finances/compta/Balance.jsx'
import Previsionnel, { requestNewForecast } from '../finances/Previsionnel.jsx'
import MesNotesDeFrais from './MesNotesDeFrais.jsx'
import { Compte } from './commun.jsx'
import Exterieurs from './Exterieurs.jsx'
import Pieces, { AnnulerImportModal, ChoixPersonneModal, NoteModal } from './Pieces.jsx'
import './notes-frais.css'

const ECRAN_LARGE = '(min-width: 900px)'
const TAILLES = [
  { part: 0.33, label: '⅓' },
  { part: 0.5, label: '½' },
  { part: 0.67, label: '⅔' },
]

const SOUS_ONGLETS = [
  { value: 'comptes', label: 'Comptes' },
  { value: 'pieces', label: 'Pièces' },
  { value: 'bilan', label: 'Bilan' },
  { value: 'ag', label: 'AG' },
  { value: 'previsionnel', label: 'Prévisionnel' },
]

// Onglet Financier, trésoriers et Super User seulement (spec/modules/
// financier.md) : Comptes, Pièces (dont les notes de frais, notes-de-frais.md
// §7), Bilan, Assemblée générale et Prévisionnel.
// `docs` : l'écran Docs de l'appli hôte, à ouvrir à côté du bilan (Seb, 10/11).
const NOMS_A_COTE = { comptes: 'Comptes', pieces: 'Pièces', docs: 'Docs' }

export default function Financier({ docs = null }) {
  // Repart du dernier sous-onglet affiché sur cet appareil.
  const [sousOnglet, setSousOnglet] = useState(() => {
    const dernier = sessionApi.lireEcran('financier')
    return SOUS_ONGLETS.some((o) => o.value === dernier) ? dernier : 'pieces'
  })
  useEffect(() => {
    sessionApi.sauvegarderEcran('financier', sousOnglet)
  }, [sousOnglet])
  // Un autre écran demande un sous-onglet (Bilan › Préparer → Pièces › Rapprocher).
  useEffect(() => {
    const aller = (e) => {
      if (SOUS_ONGLETS.some((o) => o.value === e.detail)) setSousOnglet(e.detail)
    }
    window.addEventListener(SOUS_ONGLET_EVENT, aller)
    return () => window.removeEventListener(SOUS_ONGLET_EVENT, aller)
  }, [])
  // La fiche d'une pièce demandée par un autre écran (Comptes › Balance), par-dessus
  // cet écran : la fermer revient là où on était.
  const [fichePiece, setFichePiece] = useState(null)
  useEffect(() => {
    const ouvrir = (e) => {
      api.notePourTresorier(e.detail).then(setFichePiece).catch(() => {})
    }
    window.addEventListener(FICHE_PIECE_EVENT, ouvrir)
    return () => window.removeEventListener(FICHE_PIECE_EVENT, ouvrir)
  }, [])
  // Comptes ou Pièces à côté du bilan (Seb, 10/11 ; financier.md §8.10) : sur
  // ordinateur un volet à droite, sa largeur réglée par la barre du milieu ou
  // ⅓ ½ ⅔ ; sur téléphone l'écran en entier, « ← Revenir au bilan ».
  const [aCote, setACote] = useState(null) // null | 'comptes' | 'pieces'
  const [part, setPart] = useState(0.5)
  const [retourBilan, setRetourBilan] = useState(false)
  const [docsPlein, setDocsPlein] = useState(false) // téléphone : Docs en entier depuis le Bilan
  const [large, setLarge] = useState(() => window.matchMedia?.(ECRAN_LARGE).matches ?? false)
  useEffect(() => {
    const mq = window.matchMedia?.(ECRAN_LARGE)
    if (!mq) return undefined
    const suivre = () => setLarge(mq.matches)
    mq.addEventListener('change', suivre)
    return () => mq.removeEventListener('change', suivre)
  }, [])
  // Dans le Bilan, la rangée « Bilan · Comptes · Pièces · Docs » (Seb, 10/11) :
  // Bilan à gauche, toujours allumé ; les autres s'ouvrent à côté.
  function voir(v) {
    if (v === 'bilan') setACote(null)
    else if (large) setACote((x) => (x === v ? null : v))
    else if (v === 'docs') setDocsPlein(true)
    else {
      setSousOnglet(v)
      setRetourBilan(true)
    }
  }
  function glisser(e) {
    const barre = e.currentTarget
    const zone = barre.parentElement.getBoundingClientRect()
    barre.setPointerCapture(e.pointerId)
    const bouger = (ev) => setPart(Math.min(0.75, Math.max(0.25, (zone.right - ev.clientX) / zone.width)))
    const lacher = () => {
      barre.removeEventListener('pointermove', bouger)
      barre.removeEventListener('pointerup', lacher)
      barre.removeEventListener('pointercancel', lacher)
    }
    barre.addEventListener('pointermove', bouger)
    barre.addEventListener('pointerup', lacher)
    barre.addEventListener('pointercancel', lacher)
  }

  // Saisie pour quelqu'un (menu ⋯) : d'abord choisir la personne, puis les
  // mêmes écrans que Profil › « Mes notes de frais », à son nom.
  const [choix, setChoix] = useState(null) // null | 'depense' | 'note'
  const [exterieurs, setExterieurs] = useState(false)
  const [annulerImport, setAnnulerImport] = useState(false)
  const [piecesVersion, setPiecesVersion] = useState(0) // relire les pièces après un import annulé
  const [pour, setPour] = useState(null) // { personne, action }
  useEffect(() => () => api.agirPour(null), [])
  // Badges : ce qui attend une action de qui regarde (financier.md §8.3 bis).
  const [aFaire, setAFaire] = useState({})
  // Pièces : des pièces (à valider par nature, virements à faire). Comptes :
  // les lignes de banque de la saison en cours sans compte du plan (Seb,
  // 31/10 : une pièce n'est pas une ligne, chaque sous-onglet compte les siennes).
  const [aClasser, setAClasser] = useState(0)
  const rechargerAFaire = useCallback(() => {
    api
      .compteursTresorerie()
      .then(setAFaire)
      .catch(() => {})
    Promise.all([finApi.historique(), finApi.saisons()])
      .then(([ledger, saisons]) => {
        const courante = saisons.seasons.find((s) => s.current)
        setAClasser(
          ledger.rows.filter(
            (r) => !r.transfer && !r.account && (!courante || (r.date >= courante.startDate && r.date <= courante.endDate))
          ).length
        )
      })
      .catch(() => {})
  }, [])
  useEffect(rechargerAFaire, [rechargerAFaire])
  const totalAFaire = Object.values(aFaire).reduce((a, b) => a + b, 0)

  if (pour) {
    return (
      <MesNotesDeFrais
        key={pour.personne.person_id}
        pour={pour.personne}
        nouvelleDepense={pour.action === 'depense'}
        onBack={() => {
          api.agirPour(null)
          setPour(null)
        }}
      />
    )
  }

  const pieces = (
    <Pieces key={piecesVersion} aFaire={aFaire} onCompteurs={setAFaire} onChange={rechargerAFaire} onPour={(personne, action) => {
      api.agirPour(personne.person_id)
      setPour({ personne, action })
    }} />
  )
  const volet = sousOnglet === 'bilan' && aCote && large

  return (
    <div className={`screen nf-screen${volet ? ' nf-screen--a-cote' : ''}`}>
      <MenuEntete
        label="Actions du Financier"
        actions={
          sousOnglet === 'comptes'
            ? [
                { label: 'Se connecter aux comptes en banque', icon: 'calculator', onClick: requestBank },
                { label: 'Importer des relevés', icon: 'paperclip', onClick: requestStatementImport },
                { label: 'Relevés', icon: 'check', onClick: requestStatements },
                { label: 'Plan comptable', icon: 'docs', onClick: requestPlanComptable },
                { label: 'Soldes de départ', icon: 'calculator', onClick: requestSoldesDepart },
                { label: 'Balance', icon: 'docs', onClick: requestBalance },
              ]
            : sousOnglet === 'bilan'
              ? [{ label: 'Nouveau bilan', icon: 'plus', onClick: requestNewReport }]
              : sousOnglet === 'ag'
                ? [
                    { label: 'Nouvelle AG', icon: 'plus', onClick: requestNewAssembly },
                    { label: 'Modèle général de PowerPoint…', icon: 'paperclip', onClick: requestGeneralTemplate },
                  ]
                : sousOnglet === 'previsionnel'
                  ? [{ label: 'Nouveau prévisionnel', icon: 'plus', onClick: requestNewForecast }]
                  : [
                { label: 'Créer une dépense pour quelqu’un', icon: 'plus', onClick: () => setChoix('depense') },
                { label: 'Envoyer une note pour quelqu’un', icon: 'send', onClick: () => setChoix('note') },
                { label: 'Extérieurs', icon: 'users', onClick: () => setExterieurs(true) },
                { label: 'Annuler le dernier import', icon: 'trash', onClick: () => setAnnulerImport(true) },
              ]
        }
      />
      {exterieurs && <Exterieurs onClose={() => setExterieurs(false)} />}
      {fichePiece && (
        <NoteModal
          key={fichePiece.id}
          note={fichePiece}
          nature={fichePiece.nature}
          onClose={() => setFichePiece(null)}
          onFait={() => {
            setFichePiece(null)
            rechargerAFaire()
          }}
        />
      )}
      {annulerImport && (
        <AnnulerImportModal
          onClose={() => setAnnulerImport(false)}
          onFait={() => {
            setAnnulerImport(false)
            rechargerAFaire()
            setPiecesVersion((v) => v + 1)
          }}
        />
      )}
      {choix && (
        <ChoixPersonneModal
          onClose={() => setChoix(null)}
          onChoisie={(personne) => {
            api.agirPour(personne.person_id)
            setPour({ personne, action: choix })
            setChoix(null)
          }}
        />
      )}
      <SegmentedTabs
        options={SOUS_ONGLETS.map((o) =>
          o.value === 'pieces'
            ? { ...o, label: <>{o.label}<Compte n={totalAFaire} /></> }
            : o.value === 'comptes'
              ? { ...o, label: <>{o.label}<Compte n={aClasser} banque /></> }
              : o,
        )}
        value={sousOnglet}
        onChange={(v) => {
          setSousOnglet(v)
          setRetourBilan(false)
        }}
        className="admin-screen__tabs"
      />
      {((retourBilan && sousOnglet !== 'bilan') || (docsPlein && sousOnglet === 'bilan')) && (
        <button
          type="button"
          className="btn btn--secondary nf-retour-bilan"
          onClick={() => {
            setSousOnglet('bilan')
            setRetourBilan(false)
            setDocsPlein(false)
          }}
        >
          ← Revenir au bilan
        </button>
      )}
      {sousOnglet === 'bilan' && !docsPlein && (
        <div className="segmented nf-vue-bilan" aria-label="Voir avec le bilan">
          {[
            { value: 'bilan', label: 'Bilan', on: true },
            { value: 'comptes', label: 'Comptes', on: volet && aCote === 'comptes' },
            { value: 'pieces', label: 'Pièces', on: volet && aCote === 'pieces' },
            ...(docs ? [{ value: 'docs', label: 'Docs', on: volet && aCote === 'docs' }] : []),
          ].map((o) => (
            <button
              key={o.value}
              type="button"
              aria-pressed={o.on}
              className={`segmented__option ${o.on ? 'is-active' : ''}`}
              onClick={() => voir(o.value)}
            >
              {o.label}
            </button>
          ))}
        </div>
      )}
      {volet ? (
        <div className="nf-a-cote">
          <div className="nf-a-cote__bilan">
            <Bilan />
          </div>
          <div className="nf-a-cote__barre" role="separator" aria-label="Largeur du volet" onPointerDown={glisser}>
            <span />
          </div>
          <section className="nf-a-cote__volet" style={{ width: `${part * 100}%` }} aria-label={`À côté du bilan : ${NOMS_A_COTE[aCote]}`}>
            <div className="nf-a-cote__tete">
              <button type="button" className="nf-a-cote__retour" onClick={() => setACote(null)} aria-label="Retour">
                ←
              </button>
              <h2>
                <span className="muted">À côté du bilan :</span> {NOMS_A_COTE[aCote]}
              </h2>
              <div className="nf-a-cote__tailles">
                {TAILLES.map((t) => (
                  <button
                    key={t.label}
                    type="button"
                    className={Math.abs(part - t.part) < 0.02 ? 'nf-a-cote__taille nf-a-cote__taille--on' : 'nf-a-cote__taille'}
                    onClick={() => setPart(t.part)}
                  >
                    {t.label}
                  </button>
                ))}
              </div>
            </div>
            <div className={`nf-a-cote__corps nf-a-cote__corps--${aCote}`}>
              {aCote === 'comptes' ? <Comptes onChange={rechargerAFaire} /> : aCote === 'docs' ? docs : pieces}
            </div>
          </section>
        </div>
      ) : docsPlein && sousOnglet === 'bilan' ? (
        docs
      ) : sousOnglet === 'comptes' ? (
        <Comptes onChange={rechargerAFaire} />
      ) : sousOnglet === 'bilan' ? (
        <Bilan />
      ) : sousOnglet === 'ag' ? (
        <AssembleeGenerale />
      ) : sousOnglet === 'previsionnel' ? (
        <Previsionnel />
      ) : (
        pieces
      )}
    </div>
  )
}
