import { useState } from 'react'
import './App.css'
import BottomNav from './components/BottomNav.jsx'
import Header from './components/Header.jsx'
import {
  choregraphiesParCours as initialChoregraphies,
  conversations as initialConversations,
  cours as initialCours,
  currentUser,
  eleves as initialEleves,
  groupes as initialGroupes,
  presencesParCours as initialPresences,
  professeurs as initialProfesseurs,
  videosParCours as initialVideos,
} from './data/mockData.js'
import AdminScreen from './screens/admin/AdminScreen.jsx'
import ChoregraphieScreen from './screens/ChoregraphieScreen.jsx'
import LoginScreen from './screens/LoginScreen.jsx'
import MessagerieScreen from './screens/MessagerieScreen.jsx'
import PresenceScreen from './screens/PresenceScreen.jsx'
import ProfilScreen from './screens/ProfilScreen.jsx'
import VideoScreen from './screens/VideoScreen.jsx'

// Maquette front-end du rôle Admin (voir spec/SPEC.md). Toutes les données
// sont en mémoire (voir src/data/mockData.js) : rien n'est encore persisté
// côté backend, c'est l'objet de cette étape.
function App() {
  const [loggedIn, setLoggedIn] = useState(false)
  const [activeTab, setActiveTab] = useState('admin')

  // Données "métier", possédées ici et redescendues aux écrans.
  const [eleves, setEleves] = useState(initialEleves)
  const [professeurs, setProfesseurs] = useState(initialProfesseurs)
  const [cours, setCours] = useState(initialCours)
  const [groupes, setGroupes] = useState(initialGroupes)
  const [presences, setPresences] = useState(initialPresences)
  const [choregraphies, setChoregraphies] = useState(initialChoregraphies)
  const [videos, setVideos] = useState(initialVideos)
  const [conversations, setConversations] = useState(initialConversations)

  const [selectedCoursId, setSelectedCoursId] = useState(cours[0]?.id ?? null)
  const selectedCours = cours.find((c) => c.id === selectedCoursId) ?? null

  function cycleStatut(coursId, eleveId, index, cycle) {
    setPresences((byC) => {
      const courant = byC[coursId] ?? { dates: [], parEleve: {} }
      const historique = courant.parEleve[eleveId] ?? courant.dates.map(() => 'present')
      const actuel = historique[index] ?? 'present'
      const suivant = cycle[(cycle.indexOf(actuel) + 1) % cycle.length]
      const miseAJour = [...historique]
      miseAJour[index] = suivant
      return {
        ...byC,
        [coursId]: { ...courant, parEleve: { ...courant.parEleve, [eleveId]: miseAJour } },
      }
    })
  }

  if (!loggedIn) {
    return <LoginScreen onLogin={() => setLoggedIn(true)} />
  }

  const headerMode = activeTab === 'admin' || activeTab === 'profil' ? 'simple' : 'course'
  const headerTitle =
    activeTab === 'admin'
      ? 'Administration'
      : activeTab === 'profil'
        ? 'Profil'
        : 'Sélectionner un cours'

  return (
    <div className="app">
      <Header
        mode={headerMode}
        title={headerTitle}
        cours={cours}
        selectedCoursId={selectedCoursId}
        onSelectCours={setSelectedCoursId}
        user={currentUser}
        onNavigate={setActiveTab}
        onLogout={() => setLoggedIn(false)}
      />

      <main className="app__content">
        {activeTab === 'admin' && (
          <AdminScreen
            eleves={eleves}
            setEleves={setEleves}
            professeurs={professeurs}
            setProfesseurs={setProfesseurs}
            cours={cours}
            setCours={setCours}
            groupes={groupes}
            setGroupes={setGroupes}
          />
        )}

        {activeTab === 'presence' && (
          <PresenceScreen
            cours={selectedCours}
            eleves={eleves}
            data={presences[selectedCoursId]}
            onCycle={cycleStatut}
          />
        )}

        {activeTab === 'choregraphie' && (
          <ChoregraphieScreen
            cours={selectedCours}
            list={choregraphies[selectedCoursId] ?? []}
            setList={setChoregraphies}
            eleves={eleves}
          />
        )}

        {activeTab === 'video' && (
          <VideoScreen
            cours={selectedCours}
            list={videos}
            setList={setVideos}
            choregraphies={choregraphies[selectedCoursId] ?? []}
          />
        )}

        {activeTab === 'messagerie' && (
          <MessagerieScreen conversations={conversations} setConversations={setConversations} />
        )}

        {activeTab === 'profil' && (
          <ProfilScreen user={currentUser} onLogout={() => setLoggedIn(false)} />
        )}
      </main>

      <BottomNav active={activeTab} onChange={setActiveTab} />
    </div>
  )
}

export default App
