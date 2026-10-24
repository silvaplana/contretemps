import { useEffect, useMemo, useState } from 'react'
import { useApparence } from '../../api/apparence.js'
import * as sessionApi from '../../api/session.js'
import SegmentedTabs from '../../components/SegmentedTabs.jsx'
import AdminCours from './AdminCours.jsx'
import AdminEleves from './AdminEleves.jsx'
import AdminParametres from './AdminParametres.jsx'
import AdminProfesseurs from './AdminProfesseurs.jsx'

const SUB_TABS = [
  { value: 'ecole', label: 'École' },
  { value: 'eleves', label: 'Élèves' },
  { value: 'professeurs', label: 'Profs' },
  { value: 'cours', label: 'Cours' },
]

// Onglet Admin (voir spec/SPEC.md §5.1) : réservé au rôle Admin, 4 sous-onglets
// — "École" en premier (le plus à gauche). Les groupes de la messagerie se
// gèrent dans l'onglet Messages (19 octobre, Seb). Si les 4 ne tiennent pas sur une
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
  choregraphies,
  setChoregraphies,
  onOpenHeures,
  activeUser,
  onSaisonCreee,
  onSaisonSupprimee,
  onMonRoleTresorier,
  modules,
  onModulesChange,
}) {
  // Repart du dernier sous-onglet affiché sur cet appareil.
  const [subTab, setSubTab] = useState(() => {
    const dernier = sessionApi.lireEcran('admin')
    return SUB_TABS.some((o) => o.value === dernier) ? dernier : 'eleves'
  })
  useEffect(() => {
    sessionApi.sauvegarderEcran('admin', subTab)
  }, [subTab])

  // Effectif affiché directement dans l'onglet, "Élèves (179)" (demande
  // utilisateur). Compté sur `eleves`, la liste réellement chargée : le
  // nombre se remet donc à jour tout seul après un ajout, une
  // suppression ou un import, sans appel supplémentaire au serveur.
  // Les mots École, Élèves, Profs et Cours sont ceux que l'école a choisis
  // (Personnalisation de l'application > Vocabulaire).
  const { motEcole, motEleves, motProfs, motCours } = useApparence()
  const sousOnglets = useMemo(() => {
    const mots = { ecole: motEcole, eleves: `${motEleves} (${eleves.length})`, professeurs: motProfs, cours: motCours }
    return SUB_TABS.map((onglet) => (mots[onglet.value] ? { ...onglet, label: mots[onglet.value] } : onglet))
  }, [eleves.length, motEcole, motEleves, motProfs, motCours])

  return (
    <div className="screen screen--admin">
      <SegmentedTabs
        options={sousOnglets}
        value={subTab}
        onChange={setSubTab}
        className="admin-screen__tabs"
      />

      {subTab === 'ecole' && (
        <AdminParametres
          ecole={ecole}
          setEcole={setEcole}
          choregraphies={choregraphies}
          setChoregraphies={setChoregraphies}
          cours={cours}
          eleves={eleves}
          setEleves={setEleves}
          activeUser={activeUser}
          professeurs={professeurs}
          onSaisonCreee={onSaisonCreee}
          onSaisonSupprimee={onSaisonSupprimee}
          onMonRoleTresorier={onMonRoleTresorier}
          modules={modules}
          onModulesChange={onModulesChange}
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
          groupes={groupes}
          setGroupes={setGroupes}
        />
      )}
    </div>
  )
}
