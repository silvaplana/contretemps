import { useEffect, useRef, useState } from 'react'
import * as saisonsApi from '../../api/saisons.js'
import Icon from '../../components/Icon.jsx'

// « Créer une saison » en un écran (spec/modules/saisons.md §3, maquette
// « Créer une saison ») : tout est prérempli, un bouton. « Changer… » ouvre
// un morceau : sa structure (élèves seulement) et ses données.

const ANNULER_MS = 10000

// Les champs du socle, toujours sur la fiche (voir ChampsMembres.jsx).
const SOCLE = [
  { id: 'nom', label: 'Nom, prénom', vu: 'tout le monde' },
  { id: 'email', label: 'Email', vu: 'la personne' },
  { id: 'payeur', label: 'Email du payeur', vu: 'la personne' },
  { id: 'telephone', label: 'Téléphone', vu: 'la personne' },
]

// Ce qui se recopie, dans l'ordre des lignes. `besoin` : la case qui doit
// être cochée d'abord (on ne recopie pas des cours sans leurs profs, ni des
// élèves sans leurs cours).
const MORCEAUX = [
  { cle: 'eleves', titre: 'Les élèves', le: 'les élèves', besoin: 'cours' },
  { cle: 'profs', titre: 'Les profs', le: 'les profs' },
  { cle: 'cours', titre: 'Les cours', le: 'les cours', besoin: 'profs' },
  { cle: 'documents', titre: 'Les documents' },
]

// Proposition pour la saison suivante : "2026-2027" -> "2027-2028", dates
// décalées d'un an. Juste un point de départ, tout reste modifiable.
function saisonSuivante(courante) {
  const decaler = (iso) => (iso ? `${Number(iso.slice(0, 4)) + 1}${iso.slice(4)}` : '')
  const annees = courante?.nom.match(/^(\d{4})-(\d{4})$/)
  return {
    nom: annees ? `${Number(annees[1]) + 1}-${Number(annees[2]) + 1}` : '',
    dateDebut: decaler(courante?.dateDebut),
    dateFin: decaler(courante?.dateFin),
  }
}

const pluriel = (n, mot) => `${n} ${mot}${n > 1 ? 's' : ''}`
const vuPar = (c) => (c.others_see ? 'tout le monde' : c.member_sees ? 'la personne' : 'les admins')

export default function CreerSaison({ ecoleId, courante, documents, onCreer, onClose }) {
  const [champs, setChamps] = useState(() => saisonSuivante(courante))
  const [contenu, setContenu] = useState(null)
  // Par défaut : profs, cours et documents recopiés ; élèves non (ils se
  // réinscrivent).
  const [recopier, setRecopier] = useState({ eleves: false, profs: true, cours: true, documents: true })
  const [structure, setStructure] = useState('last') // 'last' | 'base'
  const [masques, setMasques] = useState(() => new Set())
  const [ecran, setEcran] = useState(null) // null | clé d'un morceau | 'structure'
  const [erreur, setErreur] = useState(null)
  const [enCours, setEnCours] = useState(false)
  const [toast, setToast] = useState(null)
  const minuteur = useRef(null)

  useEffect(() => {
    saisonsApi.contenu(ecoleId).then(setContenu, (e) => setErreur(e.message))
  }, [ecoleId])
  useEffect(() => () => clearTimeout(minuteur.current), [])

  const morceaux = MORCEAUX.filter((m) => m.cle !== 'documents' || documents)
  // Une saison qui commence avant la courante : une saison passée, créée
  // après coup pour la remplir (bilan d'une année). Rien n'est recopié.
  const passee = Boolean(champs.dateDebut) && champs.dateDebut < courante.dateDebut
  const choisis = (contenu?.champs ?? []).filter((c) => c.key)
  const ajoutes = structure === 'last' ? (contenu?.champs ?? []).filter((c) => !c.key) : []

  function cocher(cle, coche) {
    setRecopier((r) => {
      const suite = { ...r, [cle]: coche }
      // Décocher une case décoche celles qui en ont besoin.
      if (!coche) for (const m of MORCEAUX) if (m.besoin === cle) suite[m.cle] = false
      if (!coche && cle === 'profs') suite.eleves = false
      return suite
    })
  }

  function montrerToast(texte, annuler) {
    clearTimeout(minuteur.current)
    setToast({ texte, annuler })
    minuteur.current = setTimeout(() => setToast(null), ANNULER_MS)
  }

  function basculer(id) {
    const masquer = !masques.has(id)
    const changer = (cache) =>
      setMasques((m) => {
        const suite = new Set(m)
        if (cache) suite.add(id)
        else suite.delete(id)
        return suite
      })
    changer(masquer)
    montrerToast(masquer ? 'Champ masqué, ses valeurs sont gardées' : 'Champ affiché', () => changer(!masquer))
  }

  function resume(m) {
    if (m.cle === 'documents') return `Le dossier de la saison · ${recopier.documents ? 'recopié' : 'vide'}`
    const base = m.cle === 'eleves' && structure === 'base' ? 'Structure de base' : `Comme ${courante.nom}`
    return `${base} · ${recopier[m.cle] ? 'recopiés' : 'sans les données de l’an dernier'}`
  }

  function libelleCase(cle) {
    const n = contenu?.[cle] ?? 0
    if (cle === 'eleves') return `Recopier ${n > 1 ? 'les ' : 'l’'}${pluriel(n, 'élève')} de ${courante.nom}, sans leurs paiements`
    if (cle === 'profs') return `Recopier ${n > 1 ? 'les ' : 'le '}${pluriel(n, 'professeur')} de ${courante.nom}`
    if (cle === 'cours') return `Recopier ${n > 1 ? 'les ' : 'le '}${n} cours de ${courante.nom}, avec leurs horaires et leurs profs`
    return 'Recopier le dossier de la saison'
  }

  async function creer() {
    setErreur(null)
    setEnCours(true)
    try {
      await onCreer({
        ...champs,
        cases: recopier,
        structureEleves: structure,
        champsMasques: [...masques].filter((id) => structure === 'last' || choisis.some((c) => c.id === id)),
      })
    } catch (err) {
      setErreur(err.message)
      setEnCours(false)
    }
  }

  const ligne = (c, verrouille) => {
    const cache = masques.has(c.id)
    return (
      <div key={c.id} className={`creer-saison__champ${cache ? ' creer-saison__champ--cache' : ''}`}>
        <span className="creer-saison__nom">
          {c.label}
          <small>vu par {c.vu ?? vuPar(c)}</small>
        </span>
        <span className="creer-saison__nature">Saisi</span>
        <button
          type="button"
          className="creer-saison__oeil"
          disabled={verrouille}
          aria-label={`${cache ? 'Afficher' : 'Masquer'} ${c.label}`}
          onClick={() => basculer(c.id)}
        >
          <Icon name={cache ? 'eyeOff' : 'eye'} size={22} />
        </button>
      </div>
    )
  }

  let titre = 'Créer une saison'
  let retour = onClose
  let corps
  if (ecran === 'structure') {
    titre = 'Structure : les élèves'
    retour = () => setEcran('eleves')
    corps = (
      <>
        <p className="creer-saison__note">L’œil masque un champ sans effacer ses valeurs.</p>
        <div className="creer-saison__groupe">Toujours là</div>
        {SOCLE.map((c) => ligne(c, true))}
        {choisis.length > 0 && <div className="creer-saison__groupe">Choisis par Contretemps</div>}
        {choisis.map((c) => ligne(c, false))}
        {ajoutes.length > 0 && <div className="creer-saison__groupe">Ajoutés par vous</div>}
        {ajoutes.map((c) => ligne(c, false))}
        <button type="button" className="btn btn--primary btn--block creer-saison__principal" onClick={() => setEcran('eleves')}>
          OK
        </button>
      </>
    )
  } else if (ecran) {
    const m = MORCEAUX.find((x) => x.cle === ecran)
    const besoin = m.besoin && MORCEAUX.find((x) => x.cle === m.besoin)
    const bloque = Boolean(besoin) && !recopier[m.besoin]
    titre = m.titre
    retour = () => setEcran(null)
    const visibles = [...choisis, ...ajoutes].filter((c) => !masques.has(c.id))
    corps = (
      <>
        {m.cle === 'eleves' && (
          <>
            <div className="creer-saison__partie">La structure</div>
            <div className="champs__seg" role="group" aria-label="Structure">
              <button type="button" aria-pressed={structure === 'last'} onClick={() => setStructure('last')}>
                Celle de {courante.nom}
              </button>
              <button type="button" aria-pressed={structure === 'base'} onClick={() => setStructure('base')}>
                Structure de base
              </button>
            </div>
            <p className="creer-saison__note">
              {structure === 'last'
                ? 'Les champs de l’an dernier, y compris ceux que vous aviez ajoutés.'
                : 'Ce que propose Contretemps, sans vos champs de l’an dernier.'}
            </p>
            <div className="creer-saison__cadre">
              <strong>{pluriel(SOCLE.length + visibles.length, 'champ')}</strong>
              <p className="creer-saison__note">
                {[
                  `${SOCLE.length} toujours là`,
                  `${choisis.filter((c) => !masques.has(c.id)).length} choisis par Contretemps`,
                  ajoutes.some((c) => !masques.has(c.id))
                    ? `à vous : ${ajoutes.filter((c) => !masques.has(c.id)).map((c) => c.label).join(', ')}`
                    : 'aucun ajouté par vous',
                ].join(' · ')}
              </p>
              <button type="button" className="creer-saison__lien" onClick={() => setEcran('structure')}>
                Regarder…
              </button>
            </div>
          </>
        )}
        <div className="creer-saison__partie">Les données</div>
        <label className="champs__case">
          <input
            type="checkbox"
            checked={recopier[m.cle] && !bloque}
            disabled={bloque}
            onChange={(e) => cocher(m.cle, e.target.checked)}
          />
          <span>
            {libelleCase(m.cle)}
            {bloque && <small className="creer-saison__aide">Recopiez d’abord {besoin.le}.</small>}
          </span>
        </label>
        <button type="button" className="btn btn--primary btn--block creer-saison__principal" onClick={() => setEcran(null)}>
          OK
        </button>
      </>
    )
  } else {
    corps = (
      <>
        <div className="form-fields">
          <label htmlFor="saison-nom">Nom</label>
          <input
            id="saison-nom"
            className="field-input"
            value={champs.nom}
            placeholder="ex. 2027-2028"
            onChange={(e) => setChamps((c) => ({ ...c, nom: e.target.value }))}
          />
        </div>
        <div className="creer-saison__dates">
          <div className="form-fields">
            <label htmlFor="saison-debut">Début</label>
            <input
              id="saison-debut"
              type="date"
              className="field-input"
              value={champs.dateDebut}
              onChange={(e) => setChamps((c) => ({ ...c, dateDebut: e.target.value }))}
            />
          </div>
          <div className="form-fields">
            <label htmlFor="saison-fin">Fin</label>
            <input
              id="saison-fin"
              type="date"
              className="field-input"
              value={champs.dateFin}
              onChange={(e) => setChamps((c) => ({ ...c, dateFin: e.target.value }))}
            />
          </div>
        </div>
        {!passee && (
        <div className="creer-saison__lignes">
          <div className="creer-saison__ligne">
            <span>
              <strong>L’école</strong>
              <span>Comme {courante.nom} · recopiés</span>
            </span>
          </div>
          {morceaux.map((m) => (
            <div key={m.cle} className="creer-saison__ligne">
              <span>
                <strong>{m.titre}</strong>
                <span>{resume(m)}</span>
              </span>
              <button type="button" className="creer-saison__lien" onClick={() => setEcran(m.cle)}>
                Changer…
              </button>
            </div>
          ))}
        </div>
        )}
        {erreur && <p className="login-screen__erreur">{erreur}</p>}
        <button
          type="button"
          className="btn btn--primary btn--block creer-saison__principal"
          disabled={enCours || !contenu || !champs.nom.trim() || !champs.dateDebut || !champs.dateFin}
          onClick={creer}
        >
          Créer la saison {champs.nom.trim()}
        </button>
        <p className="creer-saison__note">
          {passee
            ? `Saison passée : ${courante.nom} reste la saison en cours. La nouvelle saison est créée vide, ouverte aux modifications, et aucun mail n’est envoyé.`
            : `${courante.nom} passe en lecture seule, telle qu’elle était.`}
        </p>
      </>
    )
  }

  return (
    <div className="creer-saison" role="dialog" aria-label={titre}>
      <div className="thread-screen__header">
        <button type="button" className="icon-btn" onClick={retour} aria-label="Retour">
          <Icon name="chevronLeft" size={22} />
        </button>
        <h2 className="creer-saison__titre">{titre}</h2>
      </div>
      <div className="creer-saison__corps">{corps}</div>
      {toast && (
        <div className="admin-groupes__toast" role="status">
          <span>{toast.texte}</span>
          <button
            type="button"
            onClick={() => {
              clearTimeout(minuteur.current)
              setToast(null)
              toast.annuler()
            }}
          >
            Annuler
          </button>
        </div>
      )}
    </div>
  )
}
