import { useEffect, useState } from 'react'
import './App.css'
import * as authApi from './api/auth.js'
import * as choregraphiesApi from './api/choregraphies.js'
import * as comptesApi from './api/comptes.js'
import * as conversationsApi from './api/conversations.js'
import * as coursApi from './api/cours.js'
import * as elevesApi from './api/eleves.js'
import * as messagesApi from './api/messages.js'
import * as presenceApi from './api/presence.js'
import * as profsApi from './api/profs.js'
import * as videosApi from './api/videos.js'
import BottomNav from './components/BottomNav.jsx'
import Header from './components/Header.jsx'
import { TABS } from './data/nav.js'
import AdminScreen from './screens/admin/AdminScreen.jsx'
import ChoregraphieScreen from './screens/ChoregraphieScreen.jsx'
import HeuresScreen from './screens/HeuresScreen.jsx'
import LoginScreen from './screens/LoginScreen.jsx'
import MessagerieScreen from './screens/MessagerieScreen.jsx'
import PresenceScreen from './screens/PresenceScreen.jsx'
import ProfilScreen from './screens/ProfilScreen.jsx'
import VideoScreen from './screens/VideoScreen.jsx'

// Rôle Admin, Professeur ou Élève selon le compte connecté (voir
// spec/SPEC.md). Toutes les données viennent du vrai backend via
// api/<domaine>.js (voir api/README.md) — plus de mode maquette.
function App() {
  const [loggedIn, setLoggedIn] = useState(false)
  const [activeTab, setActiveTab] = useState('messagerie')
  // Compte réellement connecté (voir api/auth.js : `resultat.compte`) —
  // toujours renseigné une fois `loggedIn` vrai (voir onLogin ci-dessous).
  // Le repli `activeUser` ci-dessous (objet vide) ne sert qu'à ce que le
  // rendu qui précède l'écran de connexion (coursDuProfil, etc., voir plus
  // bas) ne plante pas AVANT ce premier login.
  const [compteReel, setCompteReel] = useState(null)
  const activeUser = compteReel ?? { id: null, type: null, nom: '', prenom: '', initiales: '' }

  // "Ma famille" (Profil) et "Changer de profil" (Header) : la vraie
  // famille du compte réel connecté (voir api/comptes.js : listerFamille).
  const [familleReelle, setFamilleReelle] = useState([])
  useEffect(() => {
    if (compteReel) comptesApi.listerFamille(compteReel.id).then(setFamilleReelle)
    else setFamilleReelle([])
    // Volontaire : seul l'id doit déclencher un refetch, pas chaque patch
    // de mettreAJourActiveUser (email/téléphone/code de récupération) qui
    // change l'identité de l'objet `compteReel` sans changer de compte.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [compteReel?.id])

  // Profil > crayon email/code de récupération (admin, voir
  // ProfilScreen.jsx) — persiste côté backend puis met à jour l'affichage
  // sans attendre une reconnexion.
  async function mettreAJourActiveUser(patch) {
    await comptesApi.modifier(activeUser.id, patch)
    setCompteReel((u) => ({ ...u, ...patch }))
  }

  function logout() {
    setCompteReel(null)
    setLoggedIn(false)
  }

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

  // Données "métier", possédées ici et redescendues aux écrans, toutes
  // chargées de façon async via api/<domaine>.js (voir api/README.md) —
  // rechargées à chaque connexion, pas seulement au montage.
  const [eleves, setEleves] = useState([])
  const [professeurs, setProfesseurs] = useState([])
  const [cours, setCours] = useState([])
  const [groupes, setGroupes] = useState([])
  const [presences, setPresences] = useState({})
  const [choregraphies, setChoregraphies] = useState({})
  const [videos, setVideos] = useState({})
  const [conversations, setConversations] = useState([])
  const [ecole, setEcole] = useState({
    id: null,
    nom: '',
    codePostal: '',
    codeAccesAdmin: '',
    codeAccesProf: '',
    codeAccesEleve: '',
  })

  useEffect(() => {
    if (!loggedIn) return
    elevesApi.lister(ecole.id).then(setEleves)
    profsApi.lister(ecole.id).then(setProfesseurs)
    coursApi.lister(ecole.id).then(setCours)
    conversationsApi.listerEcole(ecole.id).then(setGroupes)
  }, [loggedIn, ecole.id])

  // Messagerie (voir spec/SPEC.md §5.5/§6.9) : liste réelle, filtrée par
  // appartenance (backend: lister_du_compte). Redéclenché quand `cours`
  // arrive (pas encore prêt au tout premier rendu post-connexion) pour
  // que le nom des conversations automatiques de cours soit correct dès
  // que possible (voir api/messages.js : nomAffiche).
  useEffect(() => {
    if (compteReel) messagesApi.listerAvecMessages(ecole.id, compteReel.id, cours).then(setConversations)
    else setConversations([])
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [compteReel?.id, ecole.id, cours])

  // Réception en direct (voir api/messages.js : ouvrirFluxEvenements) :
  // UN SEUL flux SSE ouvert dès la connexion, fermé à la déconnexion —
  // pas un flux par conversation ouverte (voir le commentaire de
  // ouvrirFluxEvenements). Un message qui arrive pour une conversation
  // pas encore connue localement (ex. tout juste ajoutée à un groupe) est
  // ignoré ici : elle apparaîtra au prochain rechargement complet (rare).
  useEffect(() => {
    if (!compteReel) return
    return messagesApi.ouvrirFluxEvenements(compteReel.id, {
      onMessage: ({ conversation_id, message }) => {
        setConversations((liste) => {
          const conv = liste.find((c) => c.id === conversation_id)
          if (!conv) return liste
          // Déjà présent (mon propre envoi, déjà ajouté localement par
          // ConversationThreadScreen.jsx avant même que ce flux ne le
          // confirme) : rien à faire, pas de doublon.
          if (conv.messages.some((m) => m.id === message.id)) return liste
          const nouveauMessage = messagesApi.versMessageEcran(message, compteReel.id, conv.membres)
          return liste.map((c) =>
            c.id === conversation_id ? { ...c, messages: [...c.messages, nouveauMessage] } : c,
          )
        })
        // "Reçu" dès que mon client l'a effectivement reçu (même
        // convention que listerAvecMessages) — jamais pour mon propre
        // message (pas de delivery à moi-même, voir messages.py: envoyer).
        if (message.expediteur_id !== compteReel.id) messagesApi.marquerRecu(message.id, compteReel.id)
      },
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [compteReel?.id])

  const [selectedCoursId, setSelectedCoursId] = useState(null)
  const selectedCours = cours.find((c) => c.id === selectedCoursId) ?? null

  // `cours` charge de façon async désormais (voir ci-dessus) : plus rien
  // pour sélectionner un premier cours par défaut au montage — on le fait
  // ici, dès que la liste arrive (et seulement si la sélection actuelle
  // n'existe plus/pas encore dans cette liste).
  useEffect(() => {
    if (cours.length > 0 && !cours.find((c) => c.id === selectedCoursId)) {
      setSelectedCoursId(cours[0].id)
    }
  }, [cours, selectedCoursId])

  // Présence : dépend de la liste des cours (voir api/presence.js, mode
  // réel — a besoin de savoir quels cours interroger). Attend que `cours`
  // soit chargé plutôt que de partir avec une liste vide.
  useEffect(() => {
    if (loggedIn && cours.length > 0) {
      presenceApi.listerTout(cours.map((c) => c.id)).then(setPresences)
    }
  }, [loggedIn, cours])

  // Chorégraphies : contrairement à eleves/profs/cours/presence, chargées
  // seulement pour le cours actuellement sélectionné (voir
  // ChoregraphieScreen.jsx/VideoScreen.jsx : jamais utilisées pour un
  // autre cours en même temps) — pas besoin de tout charger d'un coup.
  useEffect(() => {
    if (loggedIn && selectedCoursId) {
      choregraphiesApi.lister(selectedCoursId).then((liste) =>
        setChoregraphies((byC) => ({ ...byC, [selectedCoursId]: liste })),
      )
    }
  }, [loggedIn, selectedCoursId])

  // Vidéos : même principe que les chorégraphies ci-dessus — seulement
  // le cours actuellement sélectionné (voir VideoScreen.jsx/
  // ChoregraphieScreen.jsx : jamais utilisées pour un autre cours en
  // même temps).
  useEffect(() => {
    if (loggedIn && selectedCoursId) {
      videosApi.lister(selectedCoursId).then((liste) =>
        setVideos((byC) => ({ ...byC, [selectedCoursId]: liste })),
      )
    }
  }, [loggedIn, selectedCoursId])

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

  // Bascule de profil famille (voir spec §2.1/§2.2) : `code` absent -> pas
  // de montée en privilège, on relit juste le compte visé (voir
  // api/auth.js: basculerLibre) ; `code` fourni -> vérifié pour de vrai
  // côté serveur (basculerAvecCode/confirmerBascule) — voir Header.jsx :
  // CodeConfirmModal, qui affiche une erreur et NE bascule PAS si le code
  // est faux (une erreur ici remonte donc jusque là, volontairement pas de
  // try/catch). Si l'onglet en cours n'est pas accessible au rôle du
  // nouveau profil (ex. Admin → Élève, sur l'onglet Admin), on retombe sur
  // Messagerie plutôt que sur un écran inaccessible. Le cours sélectionné
  // est aussi ajusté s'il n'est plus visible pour ce profil (ex. Élève
  // inscrit à un seul cours).
  async function switchProfil(id, code) {
    const profil = familleReelle.find((p) => p.id === id)
    if (!profil) return
    const nouveauCompte = code ? await authApi.confirmerBascule(id, code) : await authApi.basculerLibre(id)
    setCompteReel(nouveauCompte)

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

  // Données via api/presence.js (voir api/README.md) — `presences` reste
  // un seul objet {[coursId]: {dates, parEleve, parProf}} comme avant,
  // juste rempli/modifié via la couche api désormais.
  async function cycleStatut(coursId, eleveId, index, cycle) {
    const courant = presences[coursId] ?? { dates: [], parEleve: {}, parProf: {} }
    const historique = courant.parEleve[eleveId] ?? courant.dates.map(() => 'present')
    const actuel = historique[index] ?? 'present'
    const suivant = cycle[(cycle.indexOf(actuel) + 1) % cycle.length]

    // MAJ optimiste : l'icône change au clic, sans attendre le réseau (bug
    // signalé — "l'icône met du temps à changer"). En mode réel,
    // definirStatutEleve fait plusieurs aller-retours (liste des séances,
    // PUT, puis reconstruction complète du cours, voir api/presence.js),
    // un délai très perceptible sur un vrai réseau pour une simple case
    // qu'on clique. La réponse du serveur écrase quand même le résultat
    // ensuite, donc pas de désync durable si jamais elle diffère.
    const nouvelHistorique = [...historique]
    nouvelHistorique[index] = suivant
    setPresences((byC) => ({
      ...byC,
      [coursId]: { ...courant, parEleve: { ...courant.parEleve, [eleveId]: nouvelHistorique } },
    }))

    const donnees = await presenceApi.definirStatutEleve(coursId, eleveId, index, suivant)
    setPresences((byC) => ({ ...byC, [coursId]: donnees }))
  }

  // Ajoute une colonne de date à la table de présence d'un cours (voir
  // PresenceScreen.jsx) — `dateIso` complet ('YYYY-MM-DD'), pas juste le
  // libellé affiché, pour que le mode réel puisse créer une vraie séance
  // datée (voir api/presence.js).
  async function addDatePresence(coursId, dateIso) {
    const donnees = await presenceApi.ajouterDate(coursId, dateIso)
    setPresences((byC) => ({ ...byC, [coursId]: donnees }))
  }

  // Heures réelles d'un professeur pour une séance (voir spec §5.2/§6.6) :
  // heureDebutReelle / heureFinReelle / depassementMinutes, un des 3 champs
  // à la fois (édition case par case).
  async function setHeureProf(coursId, profId, index, champ, valeur) {
    // MAJ optimiste : même cause/même correctif que cycleStatut ci-dessus
    // (bug signalé — "l'affichage est lent, même problème que pour les
    // présences élèves"). L'utilisateur tape dans le champ, l'affichage
    // ne doit pas attendre le réseau (plusieurs aller-retours en mode
    // réel, voir api/presence.js).
    const courant = presences[coursId] ?? { dates: [], parEleve: {}, parProf: {} }
    const historique =
      courant.parProf[profId] ??
      courant.dates.map(() => ({ heureDebutReelle: '', heureFinReelle: '', depassementMinutes: '' }))
    const nouvelHistorique = [...historique]
    // Défauts explicites avant le spread de l'existant : `historique[index]`
    // peut être absent (ex. juste après l'ajout d'une date, voir
    // ajouterDateMaquette/Reel qui n'étend pas parProf) — sans ça,
    // `{...undefined, [champ]: valeur}` ne garderait QUE ce champ, les
    // deux autres deviendraient `undefined` (warning React "value ne
    // doit pas être undefined" sur les inputs contrôlés voisins).
    nouvelHistorique[index] = {
      heureDebutReelle: '',
      heureFinReelle: '',
      depassementMinutes: '',
      ...nouvelHistorique[index],
      [champ]: valeur,
    }
    setPresences((byC) => ({
      ...byC,
      [coursId]: { ...courant, parProf: { ...courant.parProf, [profId]: nouvelHistorique } },
    }))

    const donnees = await presenceApi.definirHeureProf(coursId, profId, index, champ, valeur)
    setPresences((byC) => ({ ...byC, [coursId]: donnees }))
  }

  if (!loggedIn) {
    return (
      <LoginScreen
        // `resultat` ({ compte, ecole }) vient de api/auth.js — `compte`
        // déjà à la forme `activeUser` (voir auth.js : versActiveUserEcran).
        // `ecole` est la vraie école résolue côté backend (voir auth.js :
        // resoudreEcoleReelle) — eleves/profs/cours/... en dépendent tous
        // (voir les useEffect ci-dessus, ecole.id).
        onLogin={(resultat) => {
          setCompteReel(resultat.compte)
          setEcole(resultat.ecole)
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
        famille={familleReelle}
        onSwitchProfil={switchProfil}
        onNavigate={setActiveTab}
        onLogout={logout}
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
            setVideos={setVideos}
            onOpenHeures={(profId) => openHeures(profId, 'admin')}
          />
        )}

        {activeTab === 'heures' && (
          <HeuresScreen
            professeur={professeurs.find((p) => p.id === heuresProfId)}
            cours={cours}
            presences={presences}
            estAdmin={activeUser.type === 'admin'}
            onBack={() => setActiveTab(heuresRetour)}
          />
        )}

        {activeTab === 'presence' &&
          (activeUser.type === 'admin' || activeUser.type === 'professeur') && (
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
          )}

        {activeTab === 'choregraphie' && (
          <ChoregraphieScreen
            cours={selectedCours}
            list={choregraphies[selectedCoursId] ?? []}
            setList={setChoregraphies}
            eleves={eleves}
            videos={videos[selectedCoursId] ?? []}
            setVideos={setVideos}
            // Consultation seule pour un élève (voir spec §2.1 sur les
            // droits par rôle) — Admin/Professeur peuvent créer/éditer.
            peutModifier={activeUser.type !== 'eleve'}
            uploaderId={activeUser.id}
          />
        )}

        {activeTab === 'video' && (
          <VideoScreen
            cours={selectedCours}
            list={videos}
            setList={setVideos}
            choregraphies={choregraphies[selectedCoursId] ?? []}
            uploaderId={activeUser.id}
          />
        )}

        {activeTab === 'messagerie' && (
          <MessagerieScreen
            conversations={conversations}
            setConversations={setConversations}
            compteId={activeUser.id}
          />
        )}

        {activeTab === 'profil' && (
          <ProfilScreen
            user={activeUser}
            famille={familleReelle}
            onLogout={logout}
            onOpenMesHeures={() => openHeures(activeUser.id, 'profil')}
            onUpdateUser={mettreAJourActiveUser}
          />
        )}
      </main>

      <BottomNav active={activeTab} onChange={setActiveTab} role={activeUser.type} />
    </div>
  )
}

export default App
