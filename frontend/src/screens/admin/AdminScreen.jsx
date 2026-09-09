import { useState } from 'react'
import SegmentedTabs from '../../components/SegmentedTabs.jsx'
import ZoneMigration from '../../components/ZoneMigration.jsx'
import AdminCours from './AdminCours.jsx'
import AdminEleves from './AdminEleves.jsx'
import AdminGroupes from './AdminGroupes.jsx'
import AdminParametres from './AdminParametres.jsx'
import AdminProfesseurs from './AdminProfesseurs.jsx'

const SUB_TABS = [
  { value: 'ecole', label: 'École' },
  { value: 'eleves', label: 'Elèves' },
  { value: 'professeurs', label: 'Profs' },
  { value: 'cours', label: 'Cours' },
  { value: 'groupes', label: 'Conversations' },
]

// Onglet Admin (voir spec/SPEC.md §5.1) : réservé au rôle Admin, 5 sous-onglets
// — "École" en premier (le plus à gauche). Si les 5 ne tiennent pas sur une
// ligne, SegmentedTabs passe à la ligne plutôt que de défiler (voir App.css).
// L'état de toutes les données de gestion est possédé ici et redescendu aux
// autres écrans (Présence, Chorégraphie, Vidéo...) via App.jsx.
export default function AdminScreen({
  eleves,
  setEleves,
  professeurs,
  setProfesseurs,
  cours,
  setCours,
  groupes,
  setGroupes,
  ecole,
  setEcole,
  onOpenHeures,
}) {
  const [subTab, setSubTab] = useState('eleves')

  return (
    <div className="screen">
      <SegmentedTabs options={SUB_TABS} value={subTab} onChange={setSubTab} />

      {subTab === 'ecole' && <AdminParametres ecole={ecole} setEcole={setEcole} />}
      {subTab === 'eleves' && (
        <AdminEleves eleves={eleves} setEleves={setEleves} cours={cours} ecoleId={ecole.id} />
      )}
      {subTab === 'professeurs' && (
        <ZoneMigration domaine="profs">
          <AdminProfesseurs
            professeurs={professeurs}
            setProfesseurs={setProfesseurs}
            cours={cours}
            onOpenHeures={onOpenHeures}
          />
        </ZoneMigration>
      )}
      {subTab === 'cours' && (
        <ZoneMigration domaine="cours">
          <AdminCours cours={cours} setCours={setCours} professeurs={professeurs} eleves={eleves} />
        </ZoneMigration>
      )}
      {subTab === 'groupes' && (
        <ZoneMigration domaine="messagerie">
          <AdminGroupes
            groupes={groupes}
            setGroupes={setGroupes}
            professeurs={professeurs}
            eleves={eleves}
            cours={cours}
          />
        </ZoneMigration>
      )}
    </div>
  )
}
