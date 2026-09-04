import { useState } from 'react'
import SegmentedTabs from '../../components/SegmentedTabs.jsx'
import AdminCours from './AdminCours.jsx'
import AdminEleves from './AdminEleves.jsx'
import AdminGroupes from './AdminGroupes.jsx'
import AdminProfesseurs from './AdminProfesseurs.jsx'

const SUB_TABS = [
  { value: 'eleves', label: 'Elèves' },
  { value: 'professeurs', label: 'Profs' },
  { value: 'cours', label: 'Cours' },
  { value: 'groupes', label: 'Groupes' },
]

// Onglet Admin (voir spec/SPEC.md 5.1) : réservé au rôle Admin, 4 sous-onglets.
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
}) {
  const [subTab, setSubTab] = useState('eleves')

  return (
    <div className="screen">
      <SegmentedTabs options={SUB_TABS} value={subTab} onChange={setSubTab} />

      {subTab === 'eleves' && (
        <AdminEleves eleves={eleves} setEleves={setEleves} cours={cours} />
      )}
      {subTab === 'professeurs' && (
        <AdminProfesseurs
          professeurs={professeurs}
          setProfesseurs={setProfesseurs}
          cours={cours}
        />
      )}
      {subTab === 'cours' && (
        <AdminCours cours={cours} setCours={setCours} professeurs={professeurs} eleves={eleves} />
      )}
      {subTab === 'groupes' && (
        <AdminGroupes
          groupes={groupes}
          setGroupes={setGroupes}
          professeurs={professeurs}
          cours={cours}
        />
      )}
    </div>
  )
}
