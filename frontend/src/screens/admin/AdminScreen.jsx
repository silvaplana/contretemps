import { useEffect, useState } from 'react'
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
  // "Nouveau groupe" depuis Messagerie (voir App.jsx : creerGroupeDepuisMessagerie)
  // — id de la conversation qu'il faut ouvrir en édition dès l'arrivée sur
  // cet écran, ou null hors de ce cas. `onGroupeAOuvrirConsomme` prévient
  // App.jsx une fois fait, pour ne pas la rouvrir plus tard.
  groupeAOuvrir,
  onGroupeAOuvrirConsomme,
}) {
  // État initial dérivé (pas un effet qui le changerait après coup — un
  // aller-retour Élèves puis Conversations serait visible) : cet écran est
  // démonté/remonté à chaque fois qu'on revient sur l'onglet Admin (voir
  // App.jsx), donc `groupeAOuvrir` reçu ici est toujours sa valeur "fraîche"
  // au moment du montage.
  const [subTab, setSubTab] = useState(() => (groupeAOuvrir != null ? 'groupes' : 'eleves'))

  // Prévient App.jsx que `groupeAOuvrir` est consommé (repris ci-dessus ET
  // par AdminGroupes ci-dessous) — sans ça, revenir plus tard sur cet
  // écran rouvrirait la même conversation en boucle.
  useEffect(() => {
    if (groupeAOuvrir != null) onGroupeAOuvrirConsomme?.()
    // Volontairement une seule fois au montage (voir commentaire ci-dessus
    // sur `subTab`) — pas à chaque fois que `groupeAOuvrir` change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div className="screen screen--admin">
      <SegmentedTabs
        options={SUB_TABS}
        value={subTab}
        onChange={setSubTab}
        className="admin-screen__tabs"
      />

      {subTab === 'ecole' && (
        <AdminParametres ecole={ecole} setEcole={setEcole} setVideos={setVideos} />
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
          editIdInitial={groupeAOuvrir}
        />
      )}
    </div>
  )
}
