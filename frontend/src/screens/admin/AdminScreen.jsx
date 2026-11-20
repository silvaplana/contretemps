import { useEffect, useMemo, useState } from 'react'
import { useApparence } from '../../api/apparence.js'
import { useSaisonConsultee } from '../../api/saison.js'
import { MODULES, listeImposee } from '../../app/modules.js'
import * as sessionApi from '../../api/session.js'
import { useLieu } from '../../app/lieu.js'
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
  barre,
}) {
  // Les sous-onglets des modules allumés (`adminTabs`, ex. « Paiements
  // HelloAsso », spec/modules/helloasso.md §7.4), après Cours, ou après le
  // sous-onglet nommé par `after` (ex. Essais après Élèves) ; seulement
  // une fois la liste des modules lue (aucun sous-onglet de passage).
  const ongletsModules = useMemo(
    () => MODULES.filter((m) => modules.some((x) => x.key === m.key && x.enabled)).flatMap((m) => m.adminTabs ?? []),
    [modules],
  )
  // Pastille d'un sous-onglet de module (`badge(ecoleId)` → nombre, ex. les
  // impayés de « Paiements HelloAsso ») : relue à chaque changement d'onglet.
  const [pastilles, setPastilles] = useState({})
  // Saison imposée par un module (HelloAsso) : « Élèves (n) » compte comme
  // le titre d'Admin > Élèves, sans les résiliées (Seb, 19 novembre 2026).
  // Admin > Élèves redonne son nombre (`onCompte`) après un Rafraîchir.
  // Tout est relu quand on change de saison affichée (Seb, 19 novembre 2026).
  const saisonId = useSaisonConsultee()?.id ?? null
  const [imposee, setImposee] = useState(null)
  const [compteImpose, setCompteImpose] = useState(null)
  useEffect(() => {
    if (!ecole?.id) return
    setCompteImpose(null)
    listeImposee(ecole.id)
      .then(setImposee)
      .catch(() => setImposee(null))
  }, [ecole?.id, saisonId])
  const nombreEleves = compteImpose ?? (imposee ? imposee.liste.compte(imposee.donnees, eleves) : eleves.length)
  // Repart du dernier sous-onglet affiché sur cet appareil.
  const [subTab, setSubTab] = useState(() => {
    const dernier = sessionApi.lireEcran('admin')
    const connus = [...SUB_TABS, ...MODULES.flatMap((m) => m.adminTabs ?? [])]
    return connus.some((o) => o.value === dernier) ? dernier : 'eleves'
  })
  useEffect(() => {
    sessionApi.sauvegarderEcran('admin', subTab)
  }, [subTab])
  useEffect(() => {
    if (!ecole?.id) return
    for (const o of ongletsModules.filter((x) => x.badge)) {
      o.badge(ecole.id)
        .then((n) => setPastilles((p) => ({ ...p, [o.value]: n })))
        .catch(() => null)
    }
  }, [ecole?.id, ongletsModules, subTab, saisonId])

  // Effectif affiché directement dans l'onglet, "Élèves (179)" (demande
  // utilisateur). Compté sur `eleves`, la liste réellement chargée : le
  // nombre se remet donc à jour tout seul après un ajout, une
  // suppression ou un import, sans appel supplémentaire au serveur.
  // Les mots École, Élèves, Profs et Cours sont ceux que l'école a choisis
  // (Personnalisation de l'application > Vocabulaire).
  const { motEcole, motEleves, motProfs, motCours } = useApparence()
  const sousOnglets = useMemo(() => {
    const mots = { ecole: motEcole, eleves: `${motEleves} (${nombreEleves})`, professeurs: motProfs, cours: motCours }
    const libelle = ({ value, label }) => ({
      value,
      label: pastilles[value] > 0 ? (
        <>
          {label}
          <span className="admin-onglet__pastille">{pastilles[value]}</span>
        </>
      ) : (
        label
      ),
    })
    const apres = (cle) => ongletsModules.filter((o) => o.after === cle).map(libelle)
    return [
      ...SUB_TABS.flatMap((onglet) => [mots[onglet.value] ? { ...onglet, label: mots[onglet.value] } : onglet, ...apres(onglet.value)]),
      ...ongletsModules.filter((o) => !SUB_TABS.some((s) => s.value === o.after)).map(libelle),
    ]
  }, [nombreEleves, motEcole, motEleves, motProfs, motCours, ongletsModules, pastilles])

  // Un module éteint depuis : retour aux élèves.
  const onglet = sousOnglets.some((o) => o.value === subTab) ? subTab : 'eleves'
  const ongletModule = ongletsModules.find((o) => o.value === onglet)
  // Pour l'assistant (app/lieu.js) : le sous-onglet, avec les mots de l'école.
  useLieu([{ ecole: motEcole, eleves: motEleves, professeurs: motProfs, cours: motCours }[onglet] ?? ongletModule?.label])

  return (
    <div className="screen screen--admin">
      <SegmentedTabs
        options={sousOnglets}
        value={onglet}
        onChange={setSubTab}
        className="admin-screen__tabs"
      />

      {onglet === 'ecole' && (
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
          barre={barre}
        />
      )}
      {onglet === 'eleves' && (
        <AdminEleves eleves={eleves} setEleves={setEleves} cours={cours} ecoleId={ecole.id} onCompte={setCompteImpose} />
      )}
      {onglet === 'professeurs' && (
        <AdminProfesseurs
          professeurs={professeurs}
          setProfesseurs={setProfesseurs}
          cours={cours}
          ecoleId={ecole.id}
          onOpenHeures={onOpenHeures}
        />
      )}
      {ongletModule && <ongletModule.Ecran ecoleId={ecole.id} />}
      {onglet === 'cours' && (
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
