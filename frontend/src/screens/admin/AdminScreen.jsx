import { useState } from 'react'
import SegmentedTabs from '../../components/SegmentedTabs.jsx'
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
  setVideos,
  onOpenHeures,
}) {
  const [subTab, setSubTab] = useState('eleves')

  // "Créer aussi la conversation ?" à la création d'un cours (voir
  // AdminCours.jsx: addCours, demande utilisateur du 2026-09-18) — état à
  // consommer UNE fois (voir onEditIdInitialConsomme plus bas) : sans ça,
  // quitter puis revenir sur l'onglet Conversations rouvrirait la même
  // modale en boucle.
  const [conversationAOuvrirDepuisCours, setConversationAOuvrirDepuisCours] = useState(null)

  return (
    <div className="screen screen--admin">
      <SegmentedTabs
        options={SUB_TABS}
        value={subTab}
        onChange={setSubTab}
        className="admin-screen__tabs"
      />

      {subTab === 'ecole' && (
        <AdminParametres
          ecole={ecole}
          setEcole={setEcole}
          setVideos={setVideos}
          cours={cours}
          setEleves={setEleves}
        />
      )}
      {subTab === 'eleves' && (
        <AdminEleves eleves={eleves} setEleves={setEleves} cours={cours} ecoleId={ecole.id} />
      )}
      {subTab === 'professeurs' && (
        <AdminProfesseurs
          professeurs={professeurs}
          setProfesseurs={setProfesseurs}
          cours={cours}
          ecoleId={ecole.id}
          onOpenHeures={onOpenHeures}
        />
      )}
      {subTab === 'cours' && (
        <AdminCours
          cours={cours}
          setCours={setCours}
          professeurs={professeurs}
          eleves={eleves}
          ecoleId={ecole.id}
          onConversationCreee={(conversation) => {
            setGroupes((list) => [...list, conversation])
            setConversationAOuvrirDepuisCours(conversation.id)
            setSubTab('groupes')
          }}
        />
      )}
      {subTab === 'groupes' && (
        <AdminGroupes
          groupes={groupes}
          setGroupes={setGroupes}
          professeurs={professeurs}
          eleves={eleves}
          cours={cours}
          ecoleId={ecole.id}
          editIdInitial={conversationAOuvrirDepuisCours}
          onEditIdInitialConsomme={() => setConversationAOuvrirDepuisCours(null)}
        />
      )}
    </div>
  )
}
