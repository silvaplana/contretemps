import { useState } from 'react'
import './App.css'
import BottomNav from './components/BottomNav.jsx'
import Header from './components/Header.jsx'
import {
  choregraphiesParCours as initialChoregraphies,
  conversations as initialConversations,
  cours as initialCours,
  currentUser,
  ecoleActuelle,
  eleves as initialEleves,
  familleActuelle,
  groupes as initialGroupes,
  presencesParCours as initialPresences,
  professeurs as initialProfesseurs,
  videosParCours as initialVideos,
} from './data/mockData.js'
import { TABS } from './data/nav.js'
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
  const [activeTab, setActiveTab] = useState('messagerie')
  const [activeProfilId, setActiveProfilId] = useState(currentUser.id)
  const activeUser = familleActuelle.find((p) => p.id === activeProfilId) ?? currentUser

  // Données "métier", possédées ici et redescendues aux écrans.
  const [eleves, setEleves] = useState(initialEleves)
  const [professeurs, setProfesseurs] = useState(initialProfesseurs)
  const [cours, setCours] = useState(initialCours)
  const [groupes, setGroupes] = useState(initialGroupes)
  const [presences, setPresences] = useState(initialPresences)
  const [choregraphies, setChoregraphies] = useState(initialChoregraphies)
  const [videos, setVideos] = useState(initialVideos)
  const [conversations, setConversations] = useState(initialConversations)
  const [ecole, setEcole] = useState(ecoleActuelle)

  const [selectedCoursId, setSelectedCoursId] = useState(cours[0]?.id ?? null)
  const selectedCours = cours.find((c) => c.id === selectedCoursId) ?? null

  // Cours accessibles au profil actif (voir spec §4) : tous pour l'Admin,
  // seulement ceux où il est inscrit pour un Élève (pas de Professeur dans
  // la famille de démo actuelle, voir mockData.familleActuelle).
  const coursVisibles =
    activeUser.type === 'eleve'
      ? cours.filter((c) => eleves.find((e) => e.id === activeUser.id)?.coursIds.includes(c.id))
      : cours

  // Bascule de profil famille (voir spec §2.1) : si l'onglet en cours n'est
  // pas accessible au rôle du nouveau profil (ex. Admin → Élève, sur
  // l'onglet Admin), on retombe sur Messagerie plutôt que sur un écran
  // inaccessible. Le cours sélectionné est aussi ajusté s'il n'est plus
  // visible pour ce profil (ex. Élève inscrit à un seul cours).
  function switchProfil(id) {
    setActiveProfilId(id)
    const profil = familleActuelle.find((p) => p.id === id)
    const tab = TABS.find((t) => t.key === activeTab)
    if (profil && tab && !tab.roles.includes(profil.type)) {
      setActiveTab('messagerie')
    }
    if (profil?.type === 'eleve') {
      const coursDeLeleve = cours.filter((c) =>
        eleves.find((e) => e.id === profil.id)?.coursIds.includes(c.id),
      )
      if (!coursDeLeleve.find((c) => c.id === selectedCoursId)) {
        setSelectedCoursId(coursDeLeleve[0]?.id ?? null)
      }
    }
  }

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

  // Ajoute une colonne de date à la table de présence d'un cours (voir
  // PresenceScreen.jsx). Pas de doublon : une date déjà présente est ignorée.
  function addDatePresence(coursId, dateLabel) {
    setPresences((byC) => {
      const courant = byC[coursId] ?? { dates: [], parEleve: {} }
      if (courant.dates.includes(dateLabel)) return byC
      return { ...byC, [coursId]: { ...courant, dates: [...courant.dates, dateLabel] } }
    })
  }

  if (!loggedIn) {
    return (
      <LoginScreen
        onLogin={() => {
          setActiveProfilId(currentUser.id)
          setActiveTab('messagerie')
          setLoggedIn(true)
        }}
      />
    )
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
        cours={coursVisibles}
        selectedCoursId={selectedCoursId}
        onSelectCours={setSelectedCoursId}
        user={activeUser}
        famille={familleActuelle}
        onSwitchProfil={switchProfil}
        onNavigate={setActiveTab}
        onLogout={() => setLoggedIn(false)}
      />

      <main className="app__content">
        {activeTab === 'admin' && activeUser.type === 'admin' && (
          <AdminScreen
            eleves={eleves}
            setEleves={setEleves}
            professeurs={professeurs}
            setProfesseurs={setProfesseurs}
            cours={cours}
            setCours={setCours}
            groupes={groupes}
            setGroupes={setGroupes}
            ecole={ecole}
            setEcole={setEcole}
          />
        )}

        {activeTab === 'presence' &&
          (activeUser.type === 'admin' || activeUser.type === 'professeur') && (
            <PresenceScreen
              cours={selectedCours}
              eleves={eleves}
              professeurs={professeurs}
              data={presences[selectedCoursId]}
              onCycle={cycleStatut}
              onAddDate={addDatePresence}
            />
          )}

        {activeTab === 'choregraphie' && (
          <ChoregraphieScreen
            cours={selectedCours}
            list={choregraphies[selectedCoursId] ?? []}
            setList={setChoregraphies}
            eleves={eleves}
            videos={videos[selectedCoursId] ?? []}
            setVideos={setVideos}
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
          <ProfilScreen
            user={activeUser}
            famille={familleActuelle}
            onSwitchProfil={switchProfil}
            onLogout={() => setLoggedIn(false)}
          />
        )}
      </main>

      <BottomNav active={activeTab} onChange={setActiveTab} role={activeUser.type} />
    </div>
  )
}

export default App
