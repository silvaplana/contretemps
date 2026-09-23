import { useEffect, useRef, useState } from 'react'
import './App.css'
import * as authApi from './api/auth.js'
import * as choregraphiesApi from './api/choregraphies.js'
import * as comptesApi from './api/comptes.js'
import * as conversationsApi from './api/conversations.js'
import * as coursApi from './api/cours.js'
import * as elevesApi from './api/eleves.js'
import * as installationApi from './api/installation.js'
import * as messagesApi from './api/messages.js'
import * as notificationsApi from './api/notifications.js'
import * as presenceApi from './api/presence.js'
import * as profsApi from './api/profs.js'
import * as saisonApi from './api/saison.js'
import * as sessionApi from './api/session.js'
import * as videosApi from './api/videos.js'
import { signalerFrappeRecue } from './utils/frappeIndicateur.js'
import { useMessagesEnvoyes } from './utils/messageOutbox.js'
import { appliquerEtatConnexion, initialiserPresence } from './utils/presenceEnLigne.js'
import { useTeleversementsTermines } from './utils/videoUploads.js'
import BandeauInstallation from './components/BandeauInstallation.jsx'
import BandeauNotifications from './components/BandeauNotifications.jsx'
import BottomNav from './components/BottomNav.jsx'
import Header from './components/Header.jsx'
import Logo from './components/Logo.jsx'
import { TABS } from './data/nav.js'
import { aUnDesRoles, isAdmin, isEleve, isProf, isSuperuser } from './data/roles.js'
import AdminScreen from './screens/admin/AdminScreen.jsx'
import ChoixEcoleScreen from './screens/ChoixEcoleScreen.jsx'
import ChoregraphieScreen from './screens/ChoregraphieScreen.jsx'
import HeuresScreen from './screens/HeuresScreen.jsx'
import InstallationScreen from './screens/InstallationScreen.jsx'
import LoginScreen from './screens/LoginScreen.jsx'
import MessagerieScreen from './screens/MessagerieScreen.jsx'
import PresenceScreen from './screens/PresenceScreen.jsx'
import ProfilScreen from './screens/ProfilScreen.jsx'
import SupervisionScreen from './screens/SupervisionScreen.jsx'
import VideoScreen from './screens/VideoScreen.jsx'

// Rôle Admin, Professeur ou Élève selon le compte connecté (voir
// spec/SPEC.md). Toutes les données viennent du vrai backend via
// api/<domaine>.js (voir api/README.md) — plus de mode maquette.
// Aucune école choisie : avant la connexion, et pour le Superuser (§2.5)
// tant qu'il n'a pas choisi dans quelle école intervenir.
const ECOLE_VIDE = {
  id: null,
  nom: '',
  codePostal: '',
  codeAccesAdmin: '',
  codeAccesProf: '',
  codeAccesEleve: '',
}

function App() {
  const [loggedIn, setLoggedIn] = useState(false)
  // Écran plein écran d'installation (voir screens/InstallationScreen.jsx) —
  // recalculé (voir onLogin plus bas ET l'effet de restauration ci-dessous)
  // à chaque arrivée dans l'appli, connexion explicite OU reconnexion
  // silencieuse via la session mémorisée (voir api/session.js) — les deux
  // comptent : désinstaller l'appli n'efface PAS cette session (mécanismes
  // indépendants, bug signalé le 2026-09-22), donc rouvrir après
  // désinstallation redonne une session restaurée, pas un vrai écran de
  // connexion. Ne s'affiche que si l'appli n'est pas déjà installée et que
  // "Ne plus me demander" n'a jamais été coché sur cet appareil.
  const [installationAMontrer, setInstallationAMontrer] = useState(false)
  // Arrivée dans Chrome par transfert direct (voir l'effet de restauration
  // ci-dessous et api/installation.js : compteDepuisHandoff) — demande
  // utilisateur du 2026-09-23 : pas un 2e écran plein écran bloquant juste
  // après avoir déjà dû choisir Chrome, direct dans l'appli fonctionnelle
  // avec juste un bandeau non bloquant (voir BandeauInstallation.jsx) pour
  // le clic que Chrome exige quand même pour le vrai geste d'installation.
  const [bandeauInstallationAMontrer, setBandeauInstallationAMontrer] = useState(false)
  const [activeTab, setActiveTab] = useState('messagerie')
  // Compte réellement connecté (voir api/auth.js : `resultat.compte`) —
  // toujours renseigné une fois `loggedIn` vrai (voir onLogin ci-dessous).
  // Le repli `activeUser` ci-dessous (objet vide) ne sert qu'à ce que le
  // rendu qui précède l'écran de connexion (coursDuProfil, etc., voir plus
  // bas) ne plante pas AVANT ce premier login.
  const [compteReel, setCompteReel] = useState(null)
  const activeUser = compteReel ?? { id: null, type: null, nom: '', prenom: '', initiales: '' }

  // Session persistante (voir spec §2.2, api/session.js) : au tout
  // premier rendu, on ne sait pas encore s'il y a un profil à restaurer
  // (localStorage, vérifié via le backend — voir authApi.restaurerSession)
  // — `restaurationEnCours` évite d'afficher un flash de l'écran de
  // connexion pendant cette (courte) vérification. Un compte introuvable
  // (supprimé depuis, etc.) efface l'entrée sauvegardée et retombe
  // normalement sur l'écran de connexion.
  const [restaurationEnCours, setRestaurationEnCours] = useState(true)
  useEffect(() => {
    // Arrivée depuis un AUTRE navigateur via "Lancer l'installation" (voir
    // api/installation.js: ouvrirDansChrome/compteDepuisHandoff, demande
    // utilisateur du 2026-09-23 : "on sait que le login est réussi", pas la
    // peine de repasser par LoginScreen) — prioritaire sur la session
    // mémorisée localement, qui ne peut de toute façon pas exister sur un
    // navigateur fraîchement arrivé ici pour la première fois.
    const compteIdHandoff = installationApi.compteDepuisHandoff()
    const compteId = compteIdHandoff ?? sessionApi.lireCompteSauvegarde()
    if (!compteId) {
      setRestaurationEnCours(false)
      return
    }
    async function verifierPuisRestaurer() {
      // Désinstallation probable (demande utilisateur du 2026-09-22) :
      // cette session a déjà tourné en standalone (voir
      // marquerSessionLieeInstallation ci-dessous) mais ne l'est plus
      // maintenant — sauf si le navigateur confirme que l'appli est
      // encore installée ailleurs (voir api/installation.js). Une
      // session qui n'a JAMAIS tourné en standalone (utilisée seulement
      // au navigateur), OU qui vient d'un transfert tout juste reçu (voir
      // compteIdHandoff, sans historique local par définition), n'est
      // jamais concernée.
      if (
        compteIdHandoff == null &&
        installationApi.sessionEtaitLieeInstallation() &&
        !installationApi.estInstallee()
      ) {
        const toujoursInstallee = await installationApi.estToujoursInstalleeSelonNavigateur()
        if (toujoursInstallee !== true) {
          sessionApi.effacerCompteSauvegarde()
          installationApi.oublierLienInstallation()
          // "Ne plus me demander" n'a de sens que par rapport à
          // l'installation en cours (demande utilisateur du 2026-09-23) :
          // une désinstallation remet la question à zéro, même si elle
          // avait déjà été cochée avant.
          installationApi.oublierNeJamaisDemander()
          setRestaurationEnCours(false)
          return
        }
      }
      if (installationApi.estInstallee()) installationApi.marquerSessionLieeInstallation()

      // Saisons (spec §2.6) : la fiche mémorisée peut dater d'une saison
      // terminée depuis. Si la personne a été recopiée dans la saison
      // courante, on reprend directement sa nouvelle fiche, sans
      // reconnexion (décision utilisateur du 2026-09-24) ; sinon la
      // restauration échoue plus bas et ramène à l'écran de connexion.
      const idCourant = (await comptesApi.ficheCourante(compteId).catch(() => null)) ?? compteId
      if (idCourant !== compteId && sessionApi.lireCompteSauvegarde() !== null) {
        sessionApi.sauvegarderCompte(idCourant)
      }

      authApi
        .restaurerSession(idCourant)
        .then(({ compte, ecole: ecoleRestauree }) => {
          if (idCourant !== compteId) notificationsApi.transfererAbonnement(compte.id)
          setCompteReel(compte)
          setEcole(ecoleRestauree ?? ECOLE_VIDE)
          setLoggedIn(true)
          const proposerInstallation = !installationApi.estInstallee() && !installationApi.neJamaisDemander()
          if (compteIdHandoff != null) {
            // Arrivée par transfert (voir plus haut) : direct dans l'appli
            // fonctionnelle (demande du 2026-09-23 : "pas dans l'écran
            // d'installation, dans l'appli"), le bandeau non bloquant
            // (BandeauInstallation.jsx) propose l'installation par-dessus
            // plutôt qu'un 2e écran plein écran juste après avoir déjà dû
            // choisir Chrome. Mémorisée tout de suite (pas d'écran
            // Oui/Non à traiter sur ce chemin, voir onContinuer plus bas
            // pour l'autre cas).
            sessionApi.sauvegarderCompte(compte.id)
            setBandeauInstallationAMontrer(proposerInstallation)
          } else {
            // Même logique que la connexion explicite (voir onLogin plus
            // bas) : une session restaurée compte aussi comme "connexion"
            // pour cette invitation (bug signalé le 2026-09-22) — la
            // session n'est cela dit mémorisée pour de bon qu'une fois
            // cette invitation traitée (voir onContinuer plus bas), jamais
            // ici.
            setInstallationAMontrer(proposerInstallation)
          }
        })
        .catch(() => sessionApi.effacerCompteSauvegarde())
        .finally(() => {
          if (compteIdHandoff != null) installationApi.oublierHandoff()
          setRestaurationEnCours(false)
        })
    }
    verifierPuisRestaurer()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

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
    // Le code de récupération n'est jamais gardé en clair à l'écran, comme
    // côté serveur : seulement s'il est défini (voir api/auth.js).
    const { codeRecuperation, ...reste } = patch
    setCompteReel((u) => ({
      ...u,
      ...reste,
      ...(codeRecuperation !== undefined && { codeRecuperationDefini: Boolean(codeRecuperation.trim()) }),
    }))
  }

  function logout() {
    saisonApi.consulterSaison(null)
    setCompteReel(null)
    setLoggedIn(false)
    // Déconnexion volontaire : n'importe qui rouvrant l'appli sur cet
    // appareil doit retomber sur l'écran de connexion, pas être
    // reconnecté tout seul (voir api/session.js).
    sessionApi.effacerCompteSauvegarde()
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
  // Comptes admin de l'école — jusqu'ici chargés seulement dans
  // AdminGroupes (Admin > Messagerie). Repris ici aussi pour la
  // recherche "Nouvelle discussion" de Messagerie (voir
  // ConversationListScreen.jsx), qui doit pouvoir proposer n'importe quel
  // compte de l'école (admin compris), pas seulement élèves/profs.
  const [admins, setAdmins] = useState([])
  const [presences, setPresences] = useState({})
  const [choregraphies, setChoregraphies] = useState({})
  const [videos, setVideos] = useState({})
  // Upload vidéo par blocs (voir screens/video/AjouterVideo.jsx et
  // utils/videoUploads.js) : une vidéo ajoutée "en_cours" continue son
  // envoi en tâche de fond, indépendamment de l'écran affiché — ce hook
  // la rafraîchit ici, au niveau où `videos`/`setVideos` vivent, pour que
  // ça marche même si l'utilisateur a quitté l'écran Vidéo/Chorégraphie
  // entre-temps.
  useTeleversementsTermines((videoFraiche) => {
    setVideos((byC) => ({
      ...byC,
      [videoFraiche.coursId]: (byC[videoFraiche.coursId] ?? []).map((v) =>
        v.id === videoFraiche.id ? videoFraiche : v,
      ),
    }))
  })
  const [conversations, setConversations] = useState([])
  // "Nouveau groupe" (menu 3 points de Messagerie, voir menuExtra
  // ci-dessous) — la modale elle-même vit dans MessagerieScreen.jsx (pas
  // ici) : ce booléen ne fait que la déclencher, App.jsx étant le seul
  // ancêtre commun avec Header (qui porte le bouton).
  const [nouveauGroupeOuvert, setNouveauGroupeOuvert] = useState(false)
  const [ecole, setEcole] = useState(ECOLE_VIDE)

  // Saisons (spec §2.6) : saison affichée (voir api/saison.js). `null` = la
  // courante ; sinon un admin consulte une ancienne saison, en lecture
  // seule dans toute l'appli (bandeau, actions d'écriture masquées — voir
  // App.css : .app--lecture-seule —, et refus du serveur en dernier
  // recours).
  const saisonConsultee = saisonApi.useSaisonConsultee()
  const lectureSeule = Boolean(saisonConsultee)
  // Incrémenté pour tout recharger depuis le serveur (voir les effets de
  // chargement plus bas) : saison créée, écriture refusée...
  const [versionDonnees, setVersionDonnees] = useState(0)
  // Message bref après une écriture refusée dans une ancienne saison.
  const [avisSaison, setAvisSaison] = useState(null)

  // Bascule vers la fiche de la même personne dans la nouvelle saison
  // (spec §2.6) — sa fiche actuelle vient de passer en lecture seule
  // (saison créée par elle-même ou par un autre admin). Sans reconnexion ;
  // les notifications de cet appareil suivent (voir
  // api/notifications.js : transfererAbonnement). Plusieurs requêtes
  // peuvent signaler la même bascule en même temps : une seule est faite.
  const basculeEnCours = useRef(null)
  async function basculerVersFiche(nouvelId) {
    if (!nouvelId || basculeEnCours.current === nouvelId || compteReel?.id === nouvelId) return
    basculeEnCours.current = nouvelId
    try {
      const { compte } = await authApi.restaurerSession(nouvelId)
      saisonApi.consulterSaison(null)
      if (sessionApi.lireCompteSauvegarde() !== null) sessionApi.sauvegarderCompte(compte.id)
      setCompteReel(compte)
      setVersionDonnees((v) => v + 1)
      notificationsApi.transfererAbonnement(compte.id)
    } catch {
      logout()
    } finally {
      basculeEnCours.current = null
    }
  }

  // Signaux du serveur liés aux saisons, repérés sur n'importe quelle
  // requête (voir api/identite.js).
  useEffect(() => {
    if (!compteReel) return
    function surSignal(e) {
      const { code, compteId } = e.detail
      if (code === 'nouvelle_saison') basculerVersFiche(compteId)
      else if (code === 'hors_saison') logout()
      else if (code === 'lecture_seule') {
        setAvisSaison('Cette saison est terminée : consultation seulement.')
        // Défait les modifications déjà affichées (mises à jour optimistes).
        setVersionDonnees((v) => v + 1)
      }
    }
    window.addEventListener(saisonApi.EVENEMENT_SAISON, surSignal)
    return () => window.removeEventListener(saisonApi.EVENEMENT_SAISON, surSignal)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [compteReel?.id])

  useEffect(() => {
    if (!avisSaison) return
    const minuteur = setTimeout(() => setAvisSaison(null), 4000)
    return () => clearTimeout(minuteur)
  }, [avisSaison])

  // Retour dans l'appli (téléphone rallumé, onglet remis au premier plan) :
  // une saison a pu être créée entre-temps. Beaucoup de routes de lecture
  // n'identifient pas l'appelant, donc ne signaleraient jamais la bascule
  // d'elles-mêmes. Pas pour le Superuser, qui n'a pas de saison.
  useEffect(() => {
    if (!compteReel || isSuperuser(compteReel)) return
    function verifier() {
      if (document.visibilityState !== 'visible') return
      comptesApi
        .ficheCourante(compteReel.id)
        .then((id) => {
          if (id === null) logout()
          else if (id !== compteReel.id) basculerVersFiche(id)
        })
        .catch(() => {})
    }
    document.addEventListener('visibilitychange', verifier)
    return () => document.removeEventListener('visibilitychange', verifier)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [compteReel?.id])

  // Autre saison affichée : tout ce qui est par cours repart de zéro (les
  // cours eux-mêmes changent), rechargé par les effets ci-dessous.
  useEffect(() => {
    setPresences({})
    setChoregraphies({})
    setVideos({})
    setSelectedCoursId(null)
  }, [saisonConsultee?.id])

  // Saison supprimée (Admin > École) : l'admin garde sa fiche (ancienne
  // saison supprimée), bascule sur sa fiche de la saison redevenue
  // courante (il a supprimé la courante), ou est déconnecté s'il n'en a
  // pas. Renvoie vrai s'il garde sa fiche (voir SaisonsSection.jsx).
  function surSaisonSupprimee({ compteId, saisonId }) {
    if (saisonApi.lireSaisonConsultee()?.id === saisonId) saisonApi.consulterSaison(null)
    if (compteId == null) {
      logout()
      return false
    }
    if (compteId !== compteReel?.id) {
      basculerVersFiche(compteId)
      return false
    }
    setVersionDonnees((v) => v + 1)
    return true
  }

  function surSaisonCreee({ compteId }) {
    saisonApi.consulterSaison(null)
    if (compteId && compteId !== compteReel?.id) basculerVersFiche(compteId)
    else setVersionDonnees((v) => v + 1)
  }

  // Superuser (§2.5) : l'école choisie est retenue sur l'appareil (voir
  // api/session.js), et on peut en changer depuis Profil.
  function choisirEcole(e) {
    setEcole({ ...ECOLE_VIDE, ...e })
    sessionApi.sauvegarderEcoleChoisie(e.id)
    setActiveTab('admin')
  }
  function changerEcole() {
    setEcole(ECOLE_VIDE)
    sessionApi.sauvegarderEcoleChoisie(null)
  }

  // Recharge élèves/profs/cours — au premier chargement ET à chaque
  // `cours_maj` reçu par SSE (voir plus bas), pour tenir le sélecteur de
  // cours à jour en direct (demande utilisateur du 2026-09-19) : création/
  // modification/suppression d'un cours, ou changement d'inscription
  // élève/professeur, chez N'IMPORTE QUEL compte de l'école (voir
  // backend/src/cours/receiver.py: _publier_cours_maj — diffusé à tout le
  // monde, filtré ici par rôle comme d'habitude, voir coursDuProfil).
  function resynchroniserCours() {
    elevesApi.lister(ecole.id).then(setEleves)
    profsApi.lister(ecole.id).then(setProfesseurs)
    coursApi.lister(ecole.id).then(setCours)
  }

  useEffect(() => {
    // Pas d'école choisie (Superuser, §2.5) : rien à charger encore.
    if (!loggedIn || !ecole.id) return
    resynchroniserCours()
    conversationsApi.listerEcole(ecole.id).then(setGroupes)
    comptesApi.listerAdmins(ecole.id).then(setAdmins)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loggedIn, ecole.id, saisonConsultee?.id, versionDonnees])

  // Recharge tout depuis le serveur (liste + messages + présence, voir
  // utils/presenceEnLigne.js) — au premier chargement ET à chaque
  // reconnexion du flux SSE (voir l'effet juste en dessous : onReconnect)
  // pour rattraper ce qui a pu être manqué pendant une coupure (bug
  // signalé : "des fois les messages n'arrivent pas", surtout sur
  // téléphone — voir ouvrirFluxEvenements pour le pourquoi).
  function resynchroniserConversations() {
    if (!compteReel) return
    // Ancienne saison (spec §2.6) : toutes ses conversations, la fiche
    // courante de l'admin n'y étant membre de rien.
    const lister = saisonApi.lireSaisonConsultee() ? messagesApi.listerToutesAvecMessages : messagesApi.listerAvecMessages
    lister(ecole.id, compteReel.id, cours).then((liste) => {
      setConversations(liste)
      initialiserPresence(liste.flatMap((c) => c.membres))
    })
  }

  // Messagerie (voir spec/SPEC.md §5.5/§6.9) : liste réelle, filtrée par
  // appartenance (backend: lister_du_compte). Redéclenché quand `cours`
  // arrive (pas encore prêt au tout premier rendu post-connexion) pour
  // que le nom des conversations automatiques de cours soit correct dès
  // que possible (voir api/messages.js : nomAffiche).
  useEffect(() => {
    if (compteReel && ecole.id) resynchroniserConversations()
    else setConversations([])
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [compteReel?.id, ecole.id, cours, saisonConsultee?.id, versionDonnees])

  // Réception en direct (voir api/messages.js : ouvrirFluxEvenements) :
  // UN SEUL flux SSE ouvert dès la connexion, fermé à la déconnexion —
  // pas un flux par conversation ouverte (voir le commentaire de
  // ouvrirFluxEvenements). Un message qui arrive pour une conversation PAS
  // ENCORE connue localement (typiquement un DM tout juste créé par
  // l'AUTRE partie — bug signalé : "je crée une conversation, j'envoie un
  // message, elle ne se crée pas chez l'autre") va la chercher plutôt que
  // de l'ignorer.
  useEffect(() => {
    if (!compteReel) return
    return messagesApi.ouvrirFluxEvenements(compteReel.id, {
      onMessage: ({ conversation_id, message }) => {
        // Consultation d'une ancienne saison : la liste affichée n'est pas
        // celle de ce message (rechargée au retour à la saison courante).
        if (saisonApi.lireSaisonConsultee()) return
        setConversations((liste) => {
          const conv = liste.find((c) => c.id === conversation_id)
          if (!conv) {
            messagesApi.obtenirConversation(conversation_id, compteReel.id, cours).then((nouvelleConv) => {
              setConversations((liste2) =>
                liste2.some((c) => c.id === nouvelleConv.id) ? liste2 : [...liste2, nouvelleConv],
              )
              initialiserPresence(nouvelleConv.membres)
            })
            return liste
          }
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
      onEtatConnexion: appliquerEtatConnexion,
      onEcrit: ({ conversation_id, compte_id }) => signalerFrappeRecue(conversation_id, compte_id),
      onReconnect: resynchroniserConversations,
      // Composition/nom changé (création de groupe, renommage,
      // ajout/retrait de membre — voir backend/src/messagerie/
      // receiver.py: _publier_conversation_maj). Demande utilisateur du
      // 2026-09-18 : "Nouveau groupe" doit apparaître EN DIRECT chez les
      // autres membres, pas seulement chez son créateur. Même mécanique
      // que pour un DM tout juste créé ci-dessus (onMessage) : on va
      // chercher la conversation à jour plutôt que d'essayer de deviner
      // ce qui a changé.
      onConversationMaj: ({ conversation_id }) => {
        if (saisonApi.lireSaisonConsultee()) return
        messagesApi.obtenirConversation(conversation_id, compteReel.id, cours).then((conv) => {
          setConversations((liste) =>
            liste.some((c) => c.id === conv.id) ? liste.map((c) => (c.id === conv.id ? conv : c)) : [...liste, conv],
          )
          initialiserPresence(conv.membres)
        })
      },
      // Conversation disparue DE CHEZ MOI (supprimée, ou moi retiré de
      // ses membres) — voir _publier_conversation_supprimee : rien à
      // re-télécharger, juste la retirer localement.
      onConversationSupprimee: ({ conversation_id }) => {
        setConversations((liste) => liste.filter((c) => c.id !== conversation_id))
      },
      // Une livraison de MON message a changé (reçu/lu — voir backend :
      // _publier_statut_message). Bug signalé : la coche ne passait au
      // bleu qu'en fermant/rouvrant le fil, jamais en direct pendant que
      // l'autre lisait le message.
      onMessageStatut: ({ conversation_id, message }) => {
        setConversations((liste) => {
          const conv = liste.find((c) => c.id === conversation_id)
          if (!conv) return liste
          const messageMaj = messagesApi.versMessageEcran(message, compteReel.id, conv.membres)
          return liste.map((c) =>
            c.id === conversation_id
              ? { ...c, messages: c.messages.map((m) => (m.id === messageMaj.id ? messageMaj : m)) }
              : c,
          )
        })
      },
      onCoursMaj: resynchroniserCours,
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [compteReel?.id])

  // Un message envoyé via la file d'attente (voir utils/messageOutbox.js
  // et ConversationThreadScreen.jsx) vient de réussir — au tout premier
  // essai, ou après un ou plusieurs renvois automatiques. Câblé ici
  // (pas dans ConversationThreadScreen.jsx) pour que ça marche même si
  // l'utilisateur a changé d'écran/de conversation pendant que le renvoi
  // était en cours (même principe que useTeleversementsTermines).
  useMessagesEnvoyes((messageBrut) => {
    if (!compteReel) return
    setConversations((liste) => {
      const conv = liste.find((c) => c.id === messageBrut.conversation_id)
      if (!conv) return liste
      if (conv.messages.some((m) => m.id === messageBrut.id)) return liste
      const nouveauMessage = messagesApi.versMessageEcran(messageBrut, compteReel.id, conv.membres)
      return liste.map((c) =>
        c.id === messageBrut.conversation_id ? { ...c, messages: [...c.messages, nouveauMessage] } : c,
      )
    })
  })

  // Ferme les notifications système déjà affichées (voir api/notifications.js :
  // viderNotifications) dès qu'on (r)ouvre l'appli — signalé : sur Android,
  // le badge sur l'icône (nombre de notifs PAS ENCORE balayées dans le
  // tiroir) restait bloqué au dernier chiffre après avoir lu les messages
  // DANS l'appli, puisque ça ne fermait jamais, en soi, ces notifs déjà
  // affichées. Une fois au montage/login (`compteReel` posé) ET à chaque
  // retour au premier plan (onglet remis au premier plan, ou PWA relancée
  // depuis l'icône).
  useEffect(() => {
    if (!compteReel) return
    notificationsApi.viderNotifications()
    function surVisibilite() {
      if (document.visibilityState === 'visible') notificationsApi.viderNotifications()
    }
    document.addEventListener('visibilitychange', surVisibilite)
    return () => document.removeEventListener('visibilitychange', surVisibilite)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [compteReel?.id])

  // Notifications autorisées sur le téléphone mais plus d'abonnement sur
  // cet appareil (ex. appli réinstallée) : réabonnement silencieux, sans
  // rien demander (voir api/notifications.js : reabonnerSiAutorise).
  useEffect(() => {
    if (compteReel) notificationsApi.reabonnerSiAutorise(compteReel.id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [compteReel?.id])

  // Total des messages non lus, toutes conversations confondues — même
  // donnée que le badge par conversation (voir api/messages.js :
  // compterNonLus), utilisée à la fois pour le badge de BottomNav.jsx
  // (dans l'appli) et pour le badge de l'ICÔNE DE L'APPLI elle-même
  // (écran d'accueil, voir juste ci-dessous) : un point rouge fixe ne
  // suffisait pas (demande) — sans appel explicite à setAppBadge, l'OS ne
  // sait afficher au mieux qu'un simple indicateur "il y a une notif",
  // jamais le vrai nombre.
  const totalNonLus = conversations.reduce((total, c) => total + messagesApi.compterNonLus(c), 0)

  // Redéclenché à chaque fois que ce total change (nouveau message via
  // SSE, ou fil ouvert qui repasse des messages à "lu") — tient à jour le
  // badge de l'icône même appli ouverte, pas seulement à la (ré)ouverture
  // (voir l'effet juste au-dessus, qui LUI ne s'occupe que des
  // notifications système, pas de ce badge).
  useEffect(() => {
    if (!compteReel) return
    notificationsApi.definirBadge(totalNonLus)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [compteReel?.id, totalNonLus])

  const [selectedCoursId, setSelectedCoursId] = useState(null)
  const selectedCours = cours.find((c) => c.id === selectedCoursId) ?? null

  // `cours` charge de façon async désormais (voir ci-dessus) : plus rien
  // pour sélectionner un premier cours par défaut au montage — on le fait
  // ici, dès que la liste arrive (et seulement si la sélection actuelle
  // n'existe plus/pas encore dans cette liste).
  //
  // Filtré par `coursDuProfil` (déclarée plus bas, mais une function
  // declaration est "hoisted" — appelable ici sans souci), PAS la liste
  // brute `cours` : bug signalé (demande utilisateur du 2026-09-19), si
  // le cours affiché disparaît (supprimé, ou moi retiré de ses
  // élèves/professeurs — voir onCoursMaj plus haut) ou n'est simplement
  // plus visible pour ce rôle, il faut basculer sur un cours dont
  // l'utilisateur fait encore partie, pas n'importe lequel de l'école.
  useEffect(() => {
    const visibles = coursDuProfil(activeUser)
    if (visibles.length > 0 && !visibles.find((c) => c.id === selectedCoursId)) {
      setSelectedCoursId(visibles[0].id)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cours, eleves, activeUser, selectedCoursId])

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
  }, [loggedIn, selectedCoursId, versionDonnees])

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
  }, [loggedIn, selectedCoursId, versionDonnees])

  // "Ajouter une date" (Présence) : contrôlé ici, pas en état interne à
  // PresenceScreen, pour que le menu 3 points de l'en-tête (voir Header)
  // puisse aussi déclencher la modale — même action que le "+".
  const [presenceShowAdd, setPresenceShowAdd] = useState(false)

  // Cours accessibles à un profil donné (voir spec §4) : tous pour l'Admin,
  // ceux où il est inscrit pour un Élève, ceux qu'il enseigne pour un Prof.
  // Admin testé en PREMIER : un professeur-admin a l'union des droits
  // (spec §3), donc tous les cours, pas seulement ceux qu'il enseigne.
  function coursDuProfil(profil) {
    if (isAdmin(profil)) {
      return cours
    }
    if (isProf(profil)) {
      return cours.filter((c) => c.professeurId === profil.id)
    }
    if (isEleve(profil)) {
      return cours.filter((c) => eleves.find((e) => e.id === profil.id)?.coursIds.includes(c.id))
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
    // Seul un admin consulte une ancienne saison (spec §2.6) : un autre
    // profil repart toujours de la saison courante.
    saisonApi.consulterSaison(null)
    const nouveauCompte = code ? await authApi.confirmerBascule(id, code) : await authApi.basculerLibre(id)
    setCompteReel(nouveauCompte)
    // Le profil ACTIF est celui qui doit être restauré à la prochaine
    // ouverture (voir api/session.js) — pas figé sur l'identité du login
    // initial : si on bascule vers un enfant puis ferme l'appli, elle
    // doit rouvrir sur ce même enfant.
    sessionApi.sauvegarderCompte(nouveauCompte.id)

    const tab = TABS.find((t) => t.key === activeTab)
    if (tab && !aUnDesRoles(profil, tab.roles)) {
      setActiveTab('messagerie')
    }
    // 'heures' n'est pas dans TABS (pas un onglet principal) : le cas ci-
    // dessus ne le couvre pas — on quitte aussi l'écran Heures si le nouveau
    // profil n'a pas le droit de voir celles consultées (pas admin, et pas
    // le prof concerné lui-même).
    if (activeTab === 'heures' && !isAdmin(profil) && profil.id !== heuresProfId) {
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
    if (lectureSeule) return
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
    if (lectureSeule) return
    const donnees = await presenceApi.ajouterDate(coursId, dateIso)
    setPresences((byC) => ({ ...byC, [coursId]: donnees }))
  }

  // Heures réelles d'un professeur pour une séance (voir spec §5.2/§6.6) :
  // heureDebutReelle / heureFinReelle / depassementMinutes, un des 3 champs
  // à la fois (édition case par case).
  async function setHeureProf(coursId, profId, index, champ, valeur) {
    if (lectureSeule) return
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

  // Écran vide (juste la marque) pendant la vérification d'une session
  // sauvegardée (voir l'effet en tête de fonction) — évite un flash de
  // l'écran de connexion à chaque ouverture d'appli quand une session
  // est bien restaurée.
  if (restaurationEnCours) {
    return (
      <div className="login-screen">
        <div className="login-screen__brand">
          <Logo size={110} />
          <h1>Contretemps</h1>
        </div>
      </div>
    )
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
          saisonApi.consulterSaison(null)
          setCompteReel(resultat.compte)
          setEcole(resultat.ecole ?? ECOLE_VIDE)
          setActiveTab('messagerie')
          setLoggedIn(true)
          // Si l'appli tourne déjà en standalone à cet instant (rare pour
          // une connexion EXPLICITE, mais possible après une déconnexion
          // manuelle depuis l'appli installée) : lie cette session à
          // l'installation (voir api/installation.js et l'effet de
          // restauration ci-dessus, qui détecte la désinstallation).
          if (installationApi.estInstallee()) installationApi.marquerSessionLieeInstallation()
          const montrerInstallation = !installationApi.estInstallee() && !installationApi.neJamaisDemander()
          setInstallationAMontrer(montrerInstallation)
          // Se rappeler de ce profil pour la prochaine ouverture de
          // l'appli (voir api/session.js et l'effet de restauration en
          // tête de fonction). Si l'écran d'installation va s'afficher,
          // on attend la réponse (voir onContinuer plus bas) avant
          // d'écrire quoi que ce soit ici — demande utilisateur du
          // 2026-09-23 : répondre "Oui" peut rediriger vers un AUTRE
          // navigateur (Chrome) pour une vraie installation, auquel cas
          // CE navigateur-ci (ex. Samsung Internet) n'a jamais besoin de
          // mémoriser cette session pour de bon.
          if (!montrerInstallation) sessionApi.sauvegarderCompte(resultat.compte.id)
        }}
      />
    )
  }

  if (installationAMontrer) {
    return (
      <InstallationScreen
        compteId={activeUser.id}
        onContinuer={() => {
          // Mémorisée seulement maintenant (voir onLogin ci-dessus) —
          // jamais si "Oui" a mené vers Chrome entre-temps (ouvrirDansChrome
          // navigue hors de cette page : ce code ne s'exécute alors jamais
          // dans CE navigateur-ci).
          sessionApi.sauvegarderCompte(activeUser.id)
          setInstallationAMontrer(false)
        }}
      />
    )
  }

  // Superuser sans école choisie (juste connecté, ou "Changer d'école") :
  // il choisit d'abord où intervenir (§2.5).
  if (isSuperuser(activeUser) && !ecole.id) {
    return <ChoixEcoleScreen onChoisir={choisirEcole} onLogout={logout} />
  }

  const headerMode =
    activeTab === 'admin' || activeTab === 'profil' || activeTab === 'heures' || activeTab === 'supervision'
      ? 'simple'
      : 'course'
  const headerTitle =
    activeTab === 'admin'
      ? 'Administration'
      : activeTab === 'profil'
        ? 'Profil'
        : activeTab === 'heures'
          ? 'Heures'
          : activeTab === 'supervision'
            ? 'Supervision'
            : 'Sélectionner un cours'

  return (
    <div className={lectureSeule ? 'app app--lecture-seule' : 'app'}>
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
          lectureSeule
            ? undefined
            : activeTab === 'presence'
            ? {
                label: 'Ajouter une nouvelle date',
                icon: 'plus',
                onClick: () => setPresenceShowAdd(true),
              }
            : activeTab === 'messagerie' && isAdmin(activeUser)
              ? {
                  label: 'Nouveau groupe',
                  icon: 'plus',
                  onClick: () => setNouveauGroupeOuvert(true),
                }
              : undefined
        }
      />

      {/* Consultation d'une ancienne saison (spec §2.6), rappel toujours
          visible, sur tous les écrans. */}
      {lectureSeule && (
        <div className="bandeau-saison" role="status">
          <span>
            Saison <strong>{saisonConsultee.nom}</strong> : consultation, lecture seule
          </span>
          <button type="button" className="btn btn--secondary" onClick={() => saisonApi.consulterSaison(null)}>
            Revenir à la saison courante
          </button>
        </div>
      )}
      {avisSaison && (
        <div className="bandeau-saison bandeau-saison--avis" role="alert">
          {avisSaison}
        </div>
      )}

      {/* Arrivée par transfert depuis "Lancer l'installation" (voir plus
          haut, BandeauInstallation.jsx) : propose l'installation en un clic
          sans bloquer l'accès à l'appli. */}
      <BandeauInstallation
        visible={bandeauInstallationAMontrer}
        onTermine={() => setBandeauInstallationAMontrer(false)}
      />

      {/* Notifications jamais encore acceptées ni refusées sur cet appareil :
          bandeau "Activer" (voir BandeauNotifications.jsx). */}
      <BandeauNotifications key={activeUser.id} compteId={activeUser.id} />

      <main className="app__content">
        {activeTab === 'admin' && isAdmin(activeUser) && (
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
            activeUser={activeUser}
            onSaisonCreee={surSaisonCreee}
            onSaisonSupprimee={surSaisonSupprimee}
          />
        )}

        {activeTab === 'heures' && (
          <HeuresScreen
            professeur={professeurs.find((p) => p.id === heuresProfId)}
            cours={cours}
            presences={presences}
            estAdmin={isAdmin(activeUser)}
            onBack={() => setActiveTab(heuresRetour)}
          />
        )}

        {activeTab === 'presence' &&
          aUnDesRoles(activeUser, ['admin', 'professeur']) && (
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
            peutModifier={aUnDesRoles(activeUser, ['admin', 'professeur'])}
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
            viewerRole={activeUser.type}
            ecoleId={ecole.id}
            admins={admins}
            professeurs={professeurs}
            eleves={eleves}
            cours={cours}
            nouveauGroupeOuvert={nouveauGroupeOuvert}
            onFermerNouveauGroupe={() => setNouveauGroupeOuvert(false)}
          />
        )}

        {activeTab === 'supervision' && isSuperuser(activeUser) && <SupervisionScreen />}

        {activeTab === 'profil' && (
          <ProfilScreen
            user={activeUser}
            famille={familleReelle}
            onLogout={logout}
            onOpenMesHeures={() => openHeures(activeUser.id, 'profil')}
            onUpdateUser={mettreAJourActiveUser}
            onChangerEcole={isSuperuser(activeUser) ? changerEcole : undefined}
          />
        )}
      </main>

      <BottomNav
        active={activeTab}
        onChange={setActiveTab}
        profil={activeUser}
        alertes={{ messagerie: totalNonLus }}
      />
    </div>
  )
}

export default App
