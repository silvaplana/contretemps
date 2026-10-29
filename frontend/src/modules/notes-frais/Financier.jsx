import { useCallback, useEffect, useState } from 'react'
import * as api from '../../api/notesFrais.js'
import * as sessionApi from '../../api/session.js'
import MenuEntete from '../../components/MenuEntete.jsx'
import SegmentedTabs from '../../components/SegmentedTabs.jsx'
import AssembleeGenerale, { requestGeneralTemplate, requestNewAssembly } from '../finances/AssembleeGenerale.jsx'
import Bilan, { requestNewReport } from '../finances/Bilan.jsx'
import Comptes, { requestBank, requestStatementImport } from '../finances/Comptes.jsx'
import { requestPlanComptable } from '../finances/compta/PlanComptable.jsx'
import Previsionnel, { requestNewForecast } from '../finances/Previsionnel.jsx'
import MesNotesDeFrais from './MesNotesDeFrais.jsx'
import { Compte } from './commun.jsx'
import Pieces, { ChoixPersonneModal } from './Pieces.jsx'
import './notes-frais.css'

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
export default function Financier() {
  // Repart du dernier sous-onglet affiché sur cet appareil.
  const [sousOnglet, setSousOnglet] = useState(() => {
    const dernier = sessionApi.lireEcran('financier')
    return SOUS_ONGLETS.some((o) => o.value === dernier) ? dernier : 'pieces'
  })
  useEffect(() => {
    sessionApi.sauvegarderEcran('financier', sousOnglet)
  }, [sousOnglet])
  // Saisie pour quelqu'un (menu ⋯) : d'abord choisir la personne, puis les
  // mêmes écrans que Profil › « Mes notes de frais », à son nom.
  const [choix, setChoix] = useState(null) // null | 'depense' | 'note'
  const [pour, setPour] = useState(null) // { personne, action }
  useEffect(() => () => api.agirPour(null), [])
  // Badges : ce qui attend une action de qui regarde (financier.md §8.3 bis).
  const [aFaire, setAFaire] = useState({})
  const rechargerAFaire = useCallback(() => {
    api
      .compteursTresorerie()
      .then(setAFaire)
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

  return (
    <div className="screen nf-screen">
      <MenuEntete
        label="Actions du Financier"
        actions={
          sousOnglet === 'comptes'
            ? [
                { label: 'Se connecter aux comptes en banque', icon: 'calculator', onClick: requestBank },
                { label: 'Importer des relevés', icon: 'paperclip', onClick: requestStatementImport },
                { label: 'Plan comptable', icon: 'docs', onClick: requestPlanComptable },
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
              ]
        }
      />
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
          o.value === 'pieces' ? { ...o, label: <>{o.label}<Compte n={totalAFaire} /></> } : o,
        )}
        value={sousOnglet}
        onChange={setSousOnglet}
        className="admin-screen__tabs"
      />
      {sousOnglet === 'comptes' ? (
        <Comptes />
      ) : sousOnglet === 'bilan' ? (
        <Bilan />
      ) : sousOnglet === 'ag' ? (
        <AssembleeGenerale />
      ) : sousOnglet === 'previsionnel' ? (
        <Previsionnel />
      ) : (
        <Pieces aFaire={aFaire} onCompteurs={setAFaire} onChange={rechargerAFaire} onPour={(personne, action) => {
          api.agirPour(personne.person_id)
          setPour({ personne, action })
        }} />
      )}
    </div>
  )
}
