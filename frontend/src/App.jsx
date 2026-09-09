import { useEffect, useState } from 'react'
import './App.css'
import * as elevesApi from './api/eleves.js'
import BottomNav from './components/BottomNav.jsx'
import Header from './components/Header.jsx'
import ZoneMigration from './components/ZoneMigration.jsx'
import {
  choregraphiesParCours as initialChoregraphies,
  conversations as initialConversations,
  cours as initialCours,
  currentUser,
  ecoleActuelle,
  familleActuelle,
  groupes as initialGroupes,
  presencesParCours as initialPresences,
  professeurs as initialProfesseurs,
  videosParCours as initialVideos,
} from './data/mockData.js'
import { TABS } from './data/nav.js'
import AdminScreen from './screens/admin/AdminScreen.jsx'
import ChoregraphieScreen from './screens/ChoregraphieScreen.jsx'
import HeuresScreen from './screens/HeuresScreen.jsx'
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

  // Écran "Comptage d'heures" (voir spec §5.7) : pas un onglet de nav
  // principal, ouvert depuis Admin > Professeurs ou Profil > "Mes heures" —
  // on retient qui consulter et où revenir au clic sur "Retour".
  const [heuresProfId, setHeuresProfId] = useState(null)
  const [heuresRetour, setHeuresRetour] = useState('profil')
  function openHeures(profId, retour) {
    setHeuresProfId(profId)
    setHeuresRetour(retour)
    setActiveTab('heures')
  }

  // Données "métier", possédées ici et redescendues aux écrans.
  // `eleves` seul passe par api/eleves.js (voir api/README.md) — chargé de
  // façon async, les autres restent en dur pour l'instant (pas encore
  // migrés). Recharge à chaque connexion (donc aussi après "Voir une
  // maquette"), pas seulement au montage.
  const [eleves, setEleves] = useState([])
  const [professeurs, setProfesseurs] = useState(initialProfesseurs)
  const [cours, setCours] = useState(initialCours)
  const [groupes, setGroupes] = useState(initialGroupes)
  const [presences, setPresences] = useState(initialPresences)
  const [choregraphies, setChoregraphies] = useState(initialChoregraphies)
  const [videos, setVideos] = useState(initialVideos)
  const [conversations, setConversations] = useState(initialConversations)
  const [ecole, setEcole] = useState(ecoleActuelle)

  useEffect(() => {
    if (loggedIn) elevesApi.lister(ecole.id).then(setEleves)
  }, [loggedIn, ecole.id])

  const [selectedCoursId, setSelectedCoursId] = useState(cours[0]?.id ?? null)
  const selectedCours = cours.find((c) => c.id === selectedCoursId) ?? null

  // "Ajouter une date" (Présence) : contrôlé ici, pas en état interne à
  // PresenceScreen, pour que le menu 3 points de l'en-tête (voir Header)
  // puisse aussi déclencher la modale — même action que le "+".
  const [presenceShowAdd, setPresenceShowAdd] = useState(false)

  // Cours accessibles à un profil donné (voir spec §4) : tous pour l'Admin,
  // ceux où il est inscrit pour un Élève, ceux qu'il enseigne pour un Prof.
  function coursDuProfil(profil) {
    if (profil.type === 'eleve') {
      return cours.filter((c) => eleves.find((e) => e.id === profil.id)?.coursIds.includes(c.id))
    }
    if (profil.type === 'professeur') {
      return cours.filter((c) => c.professeurId === profil.id)
    }
    return cours
  }
  const coursVisibles = coursDuProfil(activeUser)

  // Bascule de profil famille (voir spec §2.1) : si l'onglet en cours n'est
  // pas accessible au rôle du nouveau profil (ex. Admin → Élève, sur
  // l'onglet Admin), on retombe sur Messagerie plutôt que sur un écran
  // inaccessible. Le cours sélectionné est aussi ajusté s'il n'est plus
  // visible pour ce profil (ex. Élève inscrit à un seul cours).
  function switchProfil(id) {
    setActiveProfilId(id)
    const profil = familleActuelle.find((p) => p.id === id)
    if (!profil) return
    const tab = TABS.find((t) => t.key === activeTab)
    if (tab && !tab.roles.includes(profil.type)) {
      setActiveTab('messagerie')
    }
    // 'heures' n'est pas dans TABS (pas un onglet principal) : le cas ci-
    // dessus ne le couvre pas — on quitte aussi l'écran Heures si le nouveau
    // profil n'a pas le droit de voir celles consultées (pas admin, et pas
    // le prof concerné lui-même).
    if (activeTab === 'heures' && profil.type !== 'admin' && profil.id !== heuresProfId) {
      setActiveTab('profil')
    }
    const coursDuNouveauProfil = coursDuProfil(profil)
    if (!coursDuNouveauProfil.find((c) => c.id === selectedCoursId)) {
      setSelectedCoursId(coursDuNouveauProfil[0]?.id ?? null)
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

  // Heures réelles d'un professeur pour une séance (voir spec §5.2/§6.6) :
  // heureDebutReelle / heureFinReelle / depassementMinutes, un des 3 champs
  // à la fois (édition case par case).
  function setHeureProf(coursId, profId, index, champ, valeur) {
    setPresences((byC) => {
      const courant = byC[coursId] ?? { dates: [], parEleve: {}, parProf: {} }
      const historique =
        courant.parProf?.[profId] ??
        courant.dates.map(() => ({ heureDebutReelle: '', heureFinReelle: '', depassementMinutes: '' }))
      const miseAJour = [...historique]
      miseAJour[index] = { ...miseAJour[index], [champ]: valeur }
      return {
        ...byC,
        [coursId]: { ...courant, parProf: { ...courant.parProf, [profId]: miseAJour } },
      }
    })
  }

  if (!loggedIn) {
    return (
      <LoginScreen
        // `resultat` ({ compte, modeDemo }) vient de api/auth.js — pas encore
        // exploité pour sourcer les données de l'app (eleves/cours/... restent
        // depuis mockData.js quel que soit le mode, voir api/README.md) : ça
        // viendra quand chaque domaine aura sa propre couche api/<domaine>.js.
        onLogin={() => {
          setActiveProfilId(currentUser.id)
          setActiveTab('messagerie')
          setLoggedIn(true)
        }}
      />
    )
  }

  const headerMode =
    activeTab === 'admin' || activeTab === 'profil' || activeTab === 'heures' ? 'simple' : 'course'
  const headerTitle =
    activeTab === 'admin'
      ? 'Administration'
      : activeTab === 'profil'
        ? 'Profil'
        : activeTab === 'heures'
          ? 'Heures'
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
        menuExtra={
          activeTab === 'presence'
            ? {
                label: 'Ajouter une nouvelle date',
                icon: 'plus',
                onClick: () => setPresenceShowAdd(true),
              }
            : undefined
        }
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
            onOpenHeures={(profId) => openHeures(profId, 'admin')}
          />
        )}

        {activeTab === 'heures' && (
          <ZoneMigration domaine="presence">
            <HeuresScreen
              professeur={professeurs.find((p) => p.id === heuresProfId)}
              cours={cours}
              presences={presences}
              estAdmin={activeUser.type === 'admin'}
              onBack={() => setActiveTab(heuresRetour)}
            />
          </ZoneMigration>
        )}

        {activeTab === 'presence' &&
          (activeUser.type === 'admin' || activeUser.type === 'professeur') && (
            <ZoneMigration domaine="presence">
              <PresenceScreen
                cours={selectedCours}
                eleves={eleves}
                professeurs={professeurs}
                data={presences[selectedCoursId]}
                activeUser={activeUser}
                onCycle={cycleStatut}
                onAddDate={addDatePresence}
                onSetHeureProf={setHeureProf}
                showAdd={presenceShowAdd}
                setShowAdd={setPresenceShowAdd}
              />
            </ZoneMigration>
          )}

        {activeTab === 'choregraphie' && (
          <ZoneMigration domaine="choregraphies">
            <ChoregraphieScreen
              cours={selectedCours}
              list={choregraphies[selectedCoursId] ?? []}
              setList={setChoregraphies}
              eleves={eleves}
              videos={videos[selectedCoursId] ?? []}
              setVideos={setVideos}
            />
          </ZoneMigration>
        )}

        {activeTab === 'video' && (
          <ZoneMigration domaine="videos">
            <VideoScreen
              cours={selectedCours}
              list={videos}
              setList={setVideos}
              choregraphies={choregraphies[selectedCoursId] ?? []}
            />
          </ZoneMigration>
        )}

        {activeTab === 'messagerie' && (
          <ZoneMigration domaine="messagerie">
            <MessagerieScreen conversations={conversations} setConversations={setConversations} />
          </ZoneMigration>
        )}

        {activeTab === 'profil' && (
          <ProfilScreen
            user={activeUser}
            famille={familleActuelle}
            onSwitchProfil={switchProfil}
            onLogout={() => setLoggedIn(false)}
            onOpenMesHeures={() => openHeures(activeUser.id, 'profil')}
          />
        )}
      </main>

      <BottomNav active={activeTab} onChange={setActiveTab} role={activeUser.type} />
    </div>
  )
}

export default App
