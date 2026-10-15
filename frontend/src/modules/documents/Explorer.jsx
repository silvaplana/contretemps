import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Modal from '../../components/Modal.jsx'
import { documentsApi } from '../../api/documents.js'
import FolderPicker from './FolderPicker.jsx'
import NewScreen from './NewScreen.jsx'
import Properties from './Properties.jsx'
import Share from './Share.jsx'
import Arbre from './Arbre.jsx'
import Trash from './Trash.jsx'
import Viewer from './Viewer.jsx'
import { BubbleIcon, FamilyDot, FileIcon, FolderIcon, PlusIcon, StatusBadge, StatusIcon } from './icons.jsx'
import { FAMILIES, STATUSES, isImage } from './kinds.js'
import { subtitle } from './format.js'
import './documents.css'

// Explorateur de l'onglet Docs (spec appbase documents.md §6, §7 ; maquette
// validée par Seb le 15 octobre). Module isolé, futur module d'AppBase :
// il ne connaît que l'organisation et parle au serveur par api/documents.js.
//
// Gestes (§6.3 bis) :
// - téléphone : toucher = ouvrir ; appui long (ou ⋯) = menu des actions ;
// - ordinateur : clic = sélectionner, double clic = ouvrir, clic droit =
//   menu ; glisser une ligne sur un dossier = déplacer ; glisser des
//   fichiers du PC = importer (sur un dossier : dedans) ; Ctrl+C / Ctrl+X /
//   Ctrl+V = copier, couper, coller ; Ctrl+V d'une capture = importer ;
//   Suppr = corbeille.

const LONG_PRESS_MS = 500
const TOAST_MS = 10000

function Thumb({ api, item }) {
  const [url, setUrl] = useState(null)
  useEffect(() => {
    let lien = null
    let annule = false
    api.blobUrl(item.id, { thumbnail: true }).then(
      (u) => {
        if (annule) URL.revokeObjectURL(u)
        else setUrl((lien = u))
      },
      () => {},
    )
    return () => {
      annule = true
      if (lien) URL.revokeObjectURL(lien)
    }
  }, [api, item.id, item.updated_at])
  if (!url) return <FileIcon name={item.name} />
  return <img className="dx-thumb" src={url} alt="" />
}

function ItemIcon({ api, item }) {
  if (item.kind === 'folder') return <FolderIcon restricted={item.restricted} />
  if (isImage(item) && item.has_thumbnail) return <Thumb api={api} item={item} />
  return <FileIcon name={item.name} family={item.family} />
}

function hasFiles(e) {
  return Array.from(e.dataTransfer?.types ?? []).includes('Files')
}

// Dernier endroit ouvert (espace + dossier), gardé sur l'appareil sous la
// clé `memoire` donnée par l'appli : on y revient la fois suivante.
function lireEndroit(memoire) {
  try {
    const x = memoire && JSON.parse(localStorage.getItem(memoire) ?? 'null')
    if (x && typeof x.space === 'string') return { space: x.space, folder: Number.isInteger(x.folder) ? x.folder : null }
  } catch {
    // stockage indisponible (navigation privée) : on part de Privé
  }
  return { space: 'private', folder: null }
}

// Ordinateur (écran large et souris) : arborescence à gauche, façon Google
// Drive (Seb, 15 octobre). Le téléphone garde l'affichage d'une colonne.
const ECRAN_BUREAU = '(min-width: 900px) and (hover: hover) and (pointer: fine)'

function useBureau() {
  const [bureau, setBureau] = useState(() => window.matchMedia?.(ECRAN_BUREAU).matches ?? false)
  useEffect(() => {
    const mq = window.matchMedia?.(ECRAN_BUREAU)
    if (!mq) return undefined
    const suivre = (e) => setBureau(e.matches)
    mq.addEventListener('change', suivre)
    return () => mq.removeEventListener('change', suivre)
  }, [])
  return bureau
}

export default function Explorer({ orgId, memoire }) {
  const bureau = useBureau()
  const api = useMemo(() => documentsApi(orgId), [orgId])
  const [spaces, setSpaces] = useState([])
  const [space, setSpace] = useState(() => lireEndroit(memoire).space)
  const [folder, setFolder] = useState(() => lireEndroit(memoire).folder)
  const [data, setData] = useState(null)
  const [erreur, setErreur] = useState('')
  const [filtreStatut, setFiltreStatut] = useState(null)
  const [filtreFamille, setFiltreFamille] = useState(null)
  const [bulle, setBulle] = useState(null)
  const [recherche, setRecherche] = useState(null)
  const [trouves, setTrouves] = useState(null)
  const [selection, setSelection] = useState(null)
  const [feuille, setFeuilleEtat] = useState(null)
  const feuilleOuverteA = useRef(0)
  const setFeuille = (valeur) => {
    if (valeur) feuilleOuverteA.current = Date.now()
    setFeuilleEtat(valeur)
  }
  const [plus, setPlus] = useState(false)
  const [proprietes, setProprietes] = useState(null)
  const [partage, setPartage] = useState(null)
  const [nouveau, setNouveau] = useState(false)
  const [vue, setVue] = useState(null)
  const [choix, setChoix] = useState(null) // { item, mode: 'move' | 'copy' }
  const [nom, setNom] = useState(null) // { mode: 'folder' | 'rename', item?, value }
  const [corbeille, setCorbeille] = useState(false)
  const [pressePapier, setPressePapier] = useState(null) // { item, mode: 'copy' | 'cut' }
  const [toast, setToast] = useState(null)
  const [survol, setSurvol] = useState(null) // id du dossier survolé, ou 'list'
  const fichiers = useRef(null)
  const appui = useRef(null)
  const [glisse, setGlisseEtat] = useState(null) // { item, x, y, actif } : glisser au doigt
  const glisseRef = useRef(null)
  const setGlisse = (valeur) => {
    glisseRef.current = valeur
    setGlisseEtat(valeur)
  }
  const listeRef = useRef(null)
  const pointerMoveRef = useRef(null)
  const pointerUpRef = useRef(null)
  // Glisser-déposer du navigateur seulement avec une souris : au doigt,
  // c'est l'appui long puis glisser ci-dessous.
  const souris = useMemo(() => window.matchMedia?.('(hover: hover) and (pointer: fine)').matches ?? true, [])
  const minuteurToast = useRef(null)
  const minuteurBulle = useRef(null)

  const montrerToast = useCallback((texte, annuler) => {
    clearTimeout(minuteurToast.current)
    setToast({ texte, annuler })
    // Annuler reste proposé 10 s (§6.0 bis) ; un simple message, 4 s.
    minuteurToast.current = setTimeout(() => setToast(null), annuler ? TOAST_MS : 4000)
  }, [])

  const echec = useCallback((e) => montrerToast(e.message ?? String(e)), [montrerToast])

  useEffect(() => {
    api.spaces().then(setSpaces, (e) => setErreur(e.message))
  }, [api])

  const recharger = useCallback(async () => {
    try {
      const x = await api.browse(space, folder)
      setData(x)
      setErreur('')
    } catch (e) {
      // Dossier supprimé ou plus accessible, espace retiré : on repart
      // de la racine, puis de Privé.
      if (e.status === 404 && folder) {
        setFolder(null)
        return
      }
      if (e.status === 404 && space !== 'private') {
        setSpace('private')
        return
      }
      setErreur(e.message)
    }
  }, [api, space, folder])

  useEffect(() => {
    if (!memoire) return
    try {
      localStorage.setItem(memoire, JSON.stringify({ space, folder }))
    } catch {
      // stockage indisponible : tant pis, on repartira de Privé
    }
  }, [memoire, space, folder])

  useEffect(() => {
    recharger()
  }, [recharger])

  const rechercheActive = recherche != null && recherche.trim().length >= 2
  const resultats = rechercheActive && trouves ? trouves.r : null
  useEffect(() => {
    if (!rechercheActive) return undefined
    let annule = false
    const t = setTimeout(() => {
      api.search(space, recherche).then((r) => !annule && setTrouves({ q: recherche, r }), () => {})
    }, 250)
    return () => {
      annule = true
      clearTimeout(t)
    }
  }, [api, space, recherche, rechercheActive])

  function ouvrir(item) {
    setFeuille(null)
    setPlus(false)
    if (item.kind === 'folder') {
      if (item.space !== space) setSpace(item.space)
      setFolder(item.id)
      setRecherche(null)
      setSelection(null)
    } else {
      setVue(item)
    }
  }

  function allerA(id) {
    setFolder(id)
    setSelection(null)
  }

  function changerEspace(cle) {
    setSpace(cle)
    setFolder(null)
    setSelection(null)
    setRecherche(null)
  }

  const peutAjouter = Boolean(data?.can_add)

  async function importer(liste, dossierId = folder) {
    const tous = Array.from(liste ?? [])
    if (tous.length === 0) return
    montrerToast(tous.length > 1 ? `Envoi de ${tous.length} fichiers…` : `Envoi de « ${tous[0].name} »…`)
    let ok = 0
    for (const f of tous) {
      try {
        await api.upload(space, dossierId, f)
        ok += 1
      } catch (e) {
        echec(e)
      }
    }
    await recharger()
    if (ok) montrerToast(ok > 1 ? `${ok} fichiers importés` : `« ${tous[0].name} » importé`)
  }

  async function supprimer(item) {
    setFeuille(null)
    try {
      await api.remove(item.id)
      setSelection(null)
      await recharger()
      montrerToast(`« ${item.name} » mis à la corbeille`, async () => {
        await api.restore(item.id)
        await recharger()
      })
    } catch (e) {
      echec(e)
    }
  }

  async function deplacer(item, versEspace, versDossier) {
    const avant = { space: item.space, parent: folder }
    try {
      await api.move(item.id, versEspace, versDossier)
      await recharger()
      montrerToast(`« ${item.name} » déplacé`, async () => {
        await api.move(item.id, avant.space, avant.parent)
        await recharger()
      })
    } catch (e) {
      echec(e)
    }
  }

  async function copier(item, versEspace, versDossier) {
    try {
      const copie = await api.copy(item.id, versEspace, versDossier)
      await recharger()
      montrerToast(`« ${copie.name} » collé`, async () => {
        await api.remove(copie.id)
        await recharger()
      })
    } catch (e) {
      echec(e)
    }
  }

  async function coller() {
    if (!pressePapier) return
    const { item, mode } = pressePapier
    if (mode === 'cut') {
      setPressePapier(null)
      await deplacer(item, space, folder)
    } else {
      await copier(item, space, folder)
    }
  }

  async function telecharger(item, version) {
    try {
      const url = await api.blobUrl(item.id, { version: version?.id })
      const a = document.createElement('a')
      a.href = url
      a.download = version ? version.filename : item.name
      document.body.appendChild(a)
      a.click()
      a.remove()
      setTimeout(() => URL.revokeObjectURL(url), 60000)
    } catch (e) {
      echec(e)
    }
  }

  async function validerNom() {
    const valeur = nom.value.trim()
    if (!valeur) return
    try {
      if (nom.mode === 'folder') {
        await api.createFolder(space, folder, valeur)
      } else if (valeur !== nom.item.name) {
        const ancien = nom.item.name
        const id = nom.item.id
        await api.rename(id, valeur)
        montrerToast(`Renommé en « ${valeur} »`, async () => {
          await api.rename(id, ancien)
          await recharger()
        })
      }
      setNom(null)
      await recharger()
    } catch (e) {
      echec(e)
    }
  }

  // --- Clavier et presse-papier (ordinateur) ---
  useEffect(() => {
    function surTouche(e) {
      if (e.target.closest?.('input, textarea, [contenteditable="true"]')) return
      if (proprietes || partage || vue || nom || choix || nouveau || corbeille) return
      const ctrl = e.ctrlKey || e.metaKey
      if (ctrl && e.key === 'c' && selection) {
        setPressePapier({ item: selection, mode: 'copy' })
        montrerToast(`« ${selection.name} » copié : ouvrez un dossier puis Ctrl+V`)
      } else if (ctrl && e.key === 'x' && selection && selection.can_restructure !== false) {
        setPressePapier({ item: selection, mode: 'cut' })
        montrerToast(`« ${selection.name} » coupé : ouvrez un dossier puis Ctrl+V`)
      } else if (ctrl && e.key === 'v' && pressePapier && peutAjouter) {
        e.preventDefault()
        coller()
      } else if ((e.key === 'Delete' || e.key === 'Backspace') && selection) {
        e.preventDefault()
        supprimer(selection)
      } else if (e.key === 'Enter' && selection) {
        ouvrir(selection)
      } else if (e.key === 'Escape') {
        setSelection(null)
        setFeuille(null)
      }
    }
    function surColler(e) {
      if (e.target.closest?.('input, textarea')) return
      const liste = Array.from(e.clipboardData?.files ?? [])
      if (liste.length && peutAjouter) {
        e.preventDefault()
        importer(liste)
      }
    }
    window.addEventListener('keydown', surTouche)
    window.addEventListener('paste', surColler)
    return () => {
      window.removeEventListener('keydown', surTouche)
      window.removeEventListener('paste', surColler)
    }
  })

  // --- Gestes sur une ligne ---
  // Appui long sans bouger : menu. Appui long puis glisser : déplacer
  // (téléphone, §6.3 bis) ; on lâche sur un dossier ou sur le fil d'Ariane.
  function pointerDown(e, item) {
    if (e.button !== 0 || e.target.closest('.dx-more')) return
    const ligneEl = e.currentTarget
    const x = e.clientX
    const y = e.clientY
    appui.current = {
      item,
      x,
      y,
      id: e.pointerId,
      souris: e.pointerType === 'mouse',
      long: false,
      t: setTimeout(() => {
        const a = appui.current
        if (!a) return
        a.long = true
        try {
          ligneEl.setPointerCapture(a.id)
        } catch {
          // pointeur déjà relâché
        }
        if (navigator.vibrate) {
          try {
            navigator.vibrate(15)
          } catch {
            // vibration indisponible
          }
        }
        // Souris : l'appui long ouvre le menu tout de suite (le glisser
        // passe par le glisser-déposer du navigateur).
        if (a.souris) {
          setFeuille(item)
          return
        }
        setGlisse({ item, x, y, actif: false })
      }, LONG_PRESS_MS),
    }
  }

  function cibleSous(x, y, item) {
    const el = document.elementFromPoint(x, y)?.closest('[data-drop-folder]')
    if (!el) return null
    const id = el.dataset.dropFolder
    if (id === String(item.id)) return null
    return id === 'root' ? 'root' : Number(id)
  }

  function pointerMove(e) {
    const a = appui.current
    if (!a) return
    const loin = Math.hypot(e.clientX - a.x, e.clientY - a.y) > 10
    if (!a.long) {
      if (loin) {
        clearTimeout(a.t)
        appui.current = null
      }
      return
    }
    if (a.souris || (!loin && !glisseRef.current?.actif)) return
    const cible = cibleSous(e.clientX, e.clientY, a.item)
    setGlisse({ item: a.item, x: e.clientX, y: e.clientY, actif: true })
    setSurvol(cible)
    // Défilement automatique près des bords de la liste.
    const liste = listeRef.current
    if (liste) {
      const r = liste.getBoundingClientRect()
      if (e.clientY < r.top + 56) liste.scrollTop -= 12
      else if (e.clientY > r.bottom - 56) liste.scrollTop += 12
    }
  }

  function pointerUp(e) {
    const a = appui.current
    const g = glisseRef.current
    appui.current = null
    setGlisse(null)
    if (!a) return
    const item = a.item
    clearTimeout(a.t)
    if (a.long) {
      if (a.souris) return
      if (g?.actif) {
        const cible = cibleSous(e.clientX, e.clientY, item)
        setSurvol(null)
        if (cible === 'root') {
          if (folder != null) deplacer(item, space, null)
        } else if (cible != null && cible !== folder) {
          deplacer(item, space, cible)
        }
      } else {
        setFeuille(item)
      }
      return
    }
    if (a.souris) setSelection(item)
    else ouvrir(item)
  }

  useEffect(() => {
    pointerMoveRef.current = pointerMove
    pointerUpRef.current = pointerUp
  })

  function annulerAppui() {
    if (appui.current) clearTimeout(appui.current.t)
    appui.current = null
    setGlisse(null)
    setSurvol(null)
  }

  // Pendant le glisser au doigt, la page ne défile pas, et on suit le
  // doigt où qu'il aille (au-dessus du fil d'Ariane, de la bulle d'aide…).
  const arme = Boolean(glisse)
  useEffect(() => {
    if (!arme) return undefined
    const bloquer = (e) => e.cancelable && e.preventDefault()
    const bouger = (e) => pointerMoveRef.current(e)
    const lacher = (e) => pointerUpRef.current(e)
    document.addEventListener('touchmove', bloquer, { passive: false })
    window.addEventListener('pointermove', bouger)
    window.addEventListener('pointerup', lacher)
    return () => {
      document.removeEventListener('touchmove', bloquer)
      window.removeEventListener('pointermove', bouger)
      window.removeEventListener('pointerup', lacher)
    }
  }, [arme])

  // --- Glisser-déposer (ordinateur) ---
  function dragStart(e, item) {
    annulerAppui()
    e.dataTransfer.setData('application/x-dx-node', String(item.id))
    e.dataTransfer.effectAllowed = 'move'
    setSelection(item)
  }

  function dragOver(e, cible) {
    const interne = Array.from(e.dataTransfer.types).includes('application/x-dx-node')
    if (!interne && !hasFiles(e)) return
    if (cible !== 'list' && interne && selection?.id === cible) return
    e.preventDefault()
    e.stopPropagation()
    e.dataTransfer.dropEffect = interne ? 'move' : 'copy'
    setSurvol(cible)
  }

  function drop(e, cibleDossier) {
    e.preventDefault()
    e.stopPropagation()
    setSurvol(null)
    const id = e.dataTransfer.getData('application/x-dx-node')
    if (id) {
      const item = data?.items.find((x) => String(x.id) === id)
      if (item && cibleDossier && item.id !== cibleDossier) deplacer(item, space, cibleDossier)
      return
    }
    if (e.dataTransfer.files?.length) importer(e.dataTransfer.files, cibleDossier ?? folder)
  }

  // --- Affichage ---
  const items = resultats ?? data?.items ?? []
  const visible = (x) => (!filtreStatut || x.status === filtreStatut) && (!filtreFamille || x.family === filtreFamille)
  // Dossiers des saisons passées : en lecture seule, regroupés à part sous
  // « Saisons précédentes » (Seb, 15 octobre).
  const anciennesSaisons = items.filter((x) => x.system_kind === 'period' && !x.period_current && visible(x))
  const dossiers = items.filter((x) => x.kind === 'folder' && visible(x) && !anciennesSaisons.includes(x))
  const lesFichiers = items.filter((x) => x.kind === 'file' && visible(x))
  const libelleEspace = spaces.find((s) => s.key === space)?.label ?? ''

  function montrerBulle(texte) {
    setBulle(texte)
    setTimeout(() => setBulle((b) => (b === texte ? null : b)), 1500)
  }

  function boutonFiltre({ cle, actif, onClick, titre, className = '', children }) {
    const minuteur = minuteurBulle
    return (
      <button
        key={cle}
        type="button"
        className={`dx-fi ${className}${actif ? ' dx-fi--on' : ''}`}
        title={titre}
        aria-label={titre}
        aria-pressed={actif}
        onClick={onClick}
        onPointerDown={(e) => {
          if (e.pointerType !== 'mouse') minuteur.current = setTimeout(() => montrerBulle(titre), 450)
        }}
        onPointerUp={() => clearTimeout(minuteur.current)}
        onPointerLeave={() => clearTimeout(minuteur.current)}
        onContextMenu={(e) => e.preventDefault()}
      >
        {children}
      </button>
    )
  }

  function ligne(item) {
    const estDossier = item.kind === 'folder'
    const sousTitre = resultats && item.path ? item.path.map((p) => p.name).join(' › ') || libelleEspace : subtitle(item)
    return (
      <div
        key={item.id}
        role="button"
        tabIndex={0}
        className={`dx-row${estDossier ? ' dx-row--dir' : ''}${selection?.id === item.id ? ' dx-row--sel' : ''}${survol === item.id ? ' dx-row--drop' : ''}${glisse?.item.id === item.id ? ' dx-row--lift' : ''}${pressePapier?.mode === 'cut' && pressePapier.item.id === item.id ? ' dx-row--cut' : ''}`}
        data-drop-folder={estDossier ? item.id : undefined}
        draggable={souris && item.system_kind == null}
        onDragStart={(e) => dragStart(e, item)}
        onDragOver={estDossier ? (e) => dragOver(e, item.id) : undefined}
        onDragLeave={estDossier ? () => setSurvol((s) => (s === item.id ? null : s)) : undefined}
        onDrop={estDossier ? (e) => drop(e, item.id) : undefined}
        onPointerDown={(e) => pointerDown(e, item)}
        onPointerMove={(e) => !glisseRef.current && pointerMove(e)}
        onPointerUp={(e) => !glisseRef.current && pointerUp(e)}
        onPointerCancel={annulerAppui}
        onDoubleClick={() => ouvrir(item)}
        onContextMenu={(e) => {
          e.preventDefault()
          // Au doigt, Android envoie aussi un clic droit sur l'appui long :
          // l'appui long est déjà géré ci-dessus.
          if (appui.current && !appui.current.souris) return
          annulerAppui()
          setSelection(item)
          setFeuille(item)
        }}
        onKeyDown={(e) => {
          if (e.key === ' ') {
            e.preventDefault()
            setFeuille(item)
          }
        }}
      >
        <ItemIcon api={api} item={item} />
        <div className="dx-meta">
          <div className="dx-n">
            {item.name}
            {item.system_kind === 'period' && item.period_current && <span className="dx-current">en cours</span>}
          </div>
          <div className="dx-s">
            {item.status && <StatusBadge status={item.status} compact />} {item.closed_period && item.system_kind === 'period' ? '🔒 ' : ''}
            {sousTitre}
          </div>
        </div>
        {estDossier ? (
          <span className="dx-chev" aria-hidden="true">›</span>
        ) : (
          <button
            type="button"
            className="dx-more"
            aria-label={`Actions sur ${item.name}`}
            onClick={(e) => {
              e.stopPropagation()
              setFeuille(item)
            }}
          >
            ⋯
          </button>
        )}
      </div>
    )
  }

  // Actions du menu (≤ 6 + « Plus… », §6.2) ; grisées avec la raison.
  function actions(item) {
    const systeme = item.system_kind != null
    const lecture = item.level === 'view' || item.closed_period
    const restructurer = !systeme && !item.frozen && peutAjouterDans(item)
    const raison = systeme
      ? 'Dossier de l’appli : ni renommé, ni déplacé, ni supprimé'
      : item.closed_period
        ? 'Saison terminée : lecture seule'
        : item.frozen
          ? 'Officiel : figé'
          : 'Vous ne pouvez pas modifier ici'
    const principales = [
      { icone: '↗', libelle: 'Ouvrir', faire: () => ouvrir(item) },
      { icone: '👥', libelle: 'Partager', faire: () => (setFeuille(null), setPartage(item)), off: item.space === 'personal' && 'Espace Personnel : déplacez-le pour partager' },
      { icone: '✎', libelle: 'Renommer', faire: () => (setFeuille(null), setNom({ mode: 'rename', item, value: item.name })), off: !restructurer && raison },
      { icone: '➜', libelle: 'Déplacer…', faire: () => (setFeuille(null), setChoix({ item, mode: 'move' })), off: !restructurer && raison },
      { icone: '☰', libelle: 'Propriétés', faire: () => (setFeuille(null), setProprietes({ id: item.id, tab: 'Infos' })), hl: true },
      { icone: '🗑', libelle: 'Supprimer', faire: () => supprimer(item), off: !restructurer && raison, danger: true },
    ]
    const autres = [
      { icone: '⧉', libelle: 'Copier', faire: () => (setFeuille(null), setPressePapier({ item, mode: 'copy' }), montrerToast(`« ${item.name} » copié : ouvrez un dossier puis « Coller ici »`)), off: systeme && 'Copiez plutôt son contenu' },
      { icone: '⧉', libelle: 'Copier vers…', faire: () => (setFeuille(null), setChoix({ item, mode: 'copy' })), off: systeme && 'Copiez plutôt son contenu' },
      ...(item.kind === 'file'
        ? [
            { icone: '⤓', libelle: 'Télécharger', faire: () => (setFeuille(null), telecharger(item)) },
            { icone: '⤒', libelle: 'Nouvelle version…', faire: () => (setFeuille(null), setProprietes({ id: item.id, tab: 'Infos' })), off: (lecture || item.frozen) && raison },
          ]
        : []),
    ]
    return { principales, autres }
  }

  // Renommer, déplacer, supprimer : il faut pouvoir modifier le dossier
  // où l'élément se trouve (le dossier affiché, ou son dossier dans une
  // recherche — le serveur tranchera alors).
  function peutAjouterDans(item) {
    if (resultats) return item.level !== 'view'
    return peutAjouter && !item.closed_period
  }

  const panneauOuvert = proprietes || partage || vue || choix || nouveau || corbeille

  function ouvrirDepuisArbre(s, id) {
    setFeuille(null)
    setRecherche(null)
    setSelection(null)
    if (s !== space) setSpace(s)
    setFolder(id)
  }

  const explorateur = (
    <div className="dx">
      <div className="dx-top">
        {recherche == null ? (
          <>
            <h2>Documents</h2>
            <button type="button" className="dx-ico" onClick={() => setRecherche('')} aria-label="Rechercher">
              <svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden="true">
                <circle cx="10.5" cy="10.5" r="6.5" />
                <path d="M15.5 15.5L20 20" />
              </svg>
            </button>
            <button type="button" className="dx-ico" onClick={() => setCorbeille(true)} aria-label="Corbeille">
              <svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M4 7h16" />
                <path d="M9 7V4.5h6V7" />
                <path d="M6 7l1 13h10l1-13" />
                <path d="M10 11v5M14 11v5" />
              </svg>
            </button>
          </>
        ) : (
          <>
            <input
              autoFocus
              className="dx-input dx-input--search"
              placeholder={`Rechercher dans ${libelleEspace}`}
              value={recherche}
              onChange={(e) => setRecherche(e.target.value)}
            />
            <button type="button" className="dx-ico" onClick={() => setRecherche(null)} aria-label="Fermer la recherche">✕</button>
          </>
        )}
      </div>

      <div className="dx-seg" role="tablist" aria-label="Espaces">
        {spaces.map((s) => (
          <button key={s.key} type="button" role="tab" aria-selected={s.key === space} className={s.key === space ? 'on' : ''} onClick={() => changerEspace(s.key)}>
            {s.label}
          </button>
        ))}
      </div>

      <div className="dx-ficons" role="group" aria-label="Filtres">
        {Object.entries(STATUSES).map(([cle, s]) => (
          boutonFiltre({
            cle,
            actif: filtreStatut === cle,
            titre: s.label,
            className: `dx-fi--${s.className}`,
            onClick: () => setFiltreStatut(filtreStatut === cle ? null : cle),
            children: <StatusIcon status={cle} />,
          })
        ))}
        <span className="dx-fsep" />
        {Object.entries(FAMILIES).map(([cle, f]) => (
          boutonFiltre({
            cle,
            actif: filtreFamille === cle,
            titre: f.label,
            onClick: () => setFiltreFamille(filtreFamille === cle ? null : cle),
            children: <FamilyDot family={cle} />,
          })
        ))}
      </div>
      {bulle && <div className="dx-tip" role="status">{bulle}</div>}

      {/* Le chemin sous les filtres (Seb, 15 octobre). */}
      {!resultats && (
        <nav className="dx-crumb" aria-label="Emplacement">
          <button type="button" className={`dx-crumb__part${survol === 'root' ? ' dx-crumb--drop' : ''}`} data-drop-folder="root" onClick={() => allerA(null)}>
            {data?.shared_with_me ? 'Partagés avec vous' : libelleEspace}
          </button>
          {(data?.breadcrumb ?? []).map((b, i, fil) => (
            <span key={b.id} className={survol === b.id ? 'dx-crumb--drop' : undefined}>
              {' › '}
              {i === fil.length - 1 ? (
                <b>{b.name}</b>
              ) : (
                <button type="button" className="dx-crumb__part" data-drop-folder={b.id} onClick={() => allerA(b.id)}>
                  {b.name}
                </button>
              )}
            </span>
          ))}
        </nav>
      )}

      <div
        ref={listeRef}
        className={`dx-list${survol === 'list' ? ' dx-list--drop' : ''}`}
        onDragOver={peutAjouter && !resultats ? (e) => dragOver(e, 'list') : undefined}
        onDragLeave={(e) => {
          if (!e.currentTarget.contains(e.relatedTarget)) setSurvol(null)
        }}
        onDrop={peutAjouter && !resultats ? (e) => drop(e, null) : undefined}
        onPointerDown={(e) => {
          if (e.target === e.currentTarget) setSelection(null)
        }}
      >
        {erreur && <p className="dx-error">{erreur}</p>}
        {data?.shared_with_me && !resultats && (
          <p className="dx-note dx-note--pad">Voici ce qu’on a partagé avec vous.</p>
        )}
        {dossiers.length > 0 && <div className="dx-grp">Dossiers</div>}
        {dossiers.length > 0 && (
          <div className="dx-dirs">
            {dossiers.map((x) => ligne(x))}
          </div>
        )}
        {lesFichiers.length > 0 && <div className="dx-grp">Fichiers</div>}
        {lesFichiers.map((x) => ligne(x))}
        {anciennesSaisons.length > 0 && <div className="dx-grp">Saisons précédentes</div>}
        {anciennesSaisons.length > 0 && (
          <div className="dx-dirs">
            {anciennesSaisons.map((x) => ligne(x))}
          </div>
        )}
        {data && dossiers.length === 0 && lesFichiers.length === 0 && anciennesSaisons.length === 0 && (
          <p className="dx-empty">
            {resultats
              ? 'Rien ne correspond à cette recherche.'
              : filtreStatut || filtreFamille
                ? 'Aucun élément ne correspond à ces filtres dans ce dossier.'
                : data.shared_with_me
                  ? 'Rien n’a encore été partagé avec vous.'
                  : peutAjouter
                    ? 'Ce dossier est vide. Touchez + pour ajouter, ou glissez des fichiers ici.'
                    : 'Ce dossier est vide.'}
          </p>
        )}
      </div>

      {pressePapier && !panneauOuvert && (
        <div className="dx-clip">
          <span>
            « {pressePapier.item.name} » {pressePapier.mode === 'cut' ? 'coupé' : 'copié'}
          </span>
          <button type="button" className="dx-btn dx-btn--small" disabled={!peutAjouter || Boolean(resultats)} onClick={coller}>
            Coller ici
          </button>
          <button type="button" className="dx-rm" aria-label="Vider le presse-papier" onClick={() => setPressePapier(null)}>
            ✕
          </button>
        </div>
      )}

      {!panneauOuvert && (
        <>
          {/* Bulle de l'assistant, juste au-dessus du + (spec documents.md
              §7.1 ter) : l'assistant arrive avec l'étape 5 bis du plan. */}
          <button
            type="button"
            className="dx-fab dx-fab--assistant"
            onClick={() => montrerToast('Bientôt : l’assistant arrive dans une prochaine version.')}
            aria-label="Assistant"
          >
            <BubbleIcon />
          </button>
          <button type="button" className="dx-fab" onClick={() => setNouveau(true)} aria-label="Nouveau">
            <PlusIcon />
          </button>
        </>
      )}

      <input
        ref={fichiers}
        type="file"
        multiple
        hidden
        onChange={(e) => {
          const liste = Array.from(e.target.files ?? [])
          e.target.value = ''
          importer(liste)
        }}
      />

      {feuille && (
        <>
          <div
            className="dx-scrim"
            onClick={() => {
              // Le « clic » qui suit le lâcher d'un appui long tombe sur le
              // menu tout juste ouvert (voile ou action) : on l'ignore.
              if (Date.now() - feuilleOuverteA.current < 450) return
              setFeuille(null)
              setPlus(false)
            }}
          />
          <div className="dx-sheet" role="dialog" aria-label={`Actions sur ${feuille.name}`}>
            <div className="dx-grab" />
            <div className="dx-sheet__title">
              <ItemIcon api={api} item={feuille} />
              <div className="dx-meta">
                <div className="dx-n">{feuille.name}</div>
                <div className="dx-s">{subtitle(feuille)}</div>
              </div>
            </div>
            {(plus ? actions(feuille).autres : actions(feuille).principales).map((a) => (
              <button
                key={a.libelle}
                type="button"
                className={`dx-act${a.hl ? ' dx-act--hl' : ''}${a.danger ? ' dx-act--danger' : ''}`}
                disabled={Boolean(a.off)}
                onClick={() => Date.now() - feuilleOuverteA.current > 450 && a.faire()}
              >
                <i>{a.icone}</i>
                <span>
                  {a.libelle}
                  {a.off && <span className="dx-act__why">{a.off}</span>}
                </span>
              </button>
            ))}
            {plus ? (
              <button type="button" className="dx-act" onClick={() => setPlus(false)}>
                <i>‹</i>
                <span>Retour</span>
              </button>
            ) : (
              <button type="button" className="dx-act" onClick={() => setPlus(true)}>
                <i>…</i>
                <span>Plus…</span>
              </button>
            )}
          </div>
        </>
      )}

      {vue && (
        <Viewer api={api} item={vue} onClose={() => setVue(null)} onMore={(x) => setFeuille(x)} onDownload={telecharger} />
      )}

      {proprietes && (
        <Properties
          key={proprietes.id}
          api={api}
          itemId={proprietes.id}
          initialTab={proprietes.tab}
          onClose={() => setProprietes(null)}
          onShare={(d) => setPartage(d)}
          onChanged={recharger}
          onDownload={telecharger}
          onToast={montrerToast}
        />
      )}

      {partage && (
        <Share
          api={api}
          item={partage}
          onClose={() => {
            setPartage(null)
            recharger()
          }}
          onToast={montrerToast}
        />
      )}

      {choix && (
        <FolderPicker
          api={api}
          spaces={spaces}
          item={choix.item}
          mode={choix.mode}
          startSpace={space}
          startFolder={folder}
          onClose={() => setChoix(null)}
          onPick={(versEspace, versDossier) => {
            const { item, mode } = choix
            setChoix(null)
            if (mode === 'copy') copier(item, versEspace, versDossier)
            else deplacer(item, versEspace, versDossier)
          }}
        />
      )}

      {nouveau && (
        <NewScreen
          canAdd={peutAjouter}
          onClose={() => setNouveau(false)}
          onNewFolder={() => {
            setNouveau(false)
            setNom({ mode: 'folder', value: '' })
          }}
          onImport={() => {
            setNouveau(false)
            fichiers.current?.click()
          }}
          onToast={montrerToast}
        />
      )}

      {corbeille && (
        <Trash
          api={api}
          space={space}
          spaceLabel={libelleEspace}
          onClose={() => setCorbeille(false)}
          onRestored={(x) => {
            recharger()
            montrerToast(`« ${x.name} » restauré`)
          }}
          // Plus rien à annuler : l'ancien « Annuler » viserait du vide.
          onEmptied={(n) => montrerToast(n > 1 ? `${n} éléments effacés pour de bon` : 'Effacé pour de bon')}
        />
      )}

      {nom && (
        <Modal
          title={nom.mode === 'folder' ? 'Nouveau dossier' : 'Renommer'}
          onClose={() => setNom(null)}
          footer={
            <button type="button" className="btn btn--primary btn--block" disabled={!nom.value.trim()} onClick={validerNom}>
              {nom.mode === 'folder' ? 'Créer' : 'Renommer'}
            </button>
          }
        >
          <input
            autoFocus
            className="dx-input"
            value={nom.value}
            placeholder={nom.mode === 'folder' ? 'Nom du dossier' : ''}
            onChange={(e) => setNom({ ...nom, value: e.target.value })}
            onKeyDown={(e) => e.key === 'Enter' && validerNom()}
          />
        </Modal>
      )}

      {glisse?.actif && (
        <div className="dx-ghost" style={{ left: glisse.x, top: glisse.y }} aria-hidden="true">
          <ItemIcon api={api} item={glisse.item} />
          <span>{glisse.item.name}</span>
        </div>
      )}
      {glisse && !glisse.actif && (
        <div className="dx-hint" role="status">Glissez sur un dossier pour déplacer, ou lâchez pour le menu</div>
      )}

      {toast && (
        <div className="dx-toast" role="status">
          <span>{toast.texte}</span>
          {toast.annuler && (
            <button
              type="button"
              onClick={async () => {
                const annuler = toast.annuler
                setToast(null)
                try {
                  await annuler()
                } catch (e) {
                  echec(e)
                }
              }}
            >
              Annuler
            </button>
          )}
        </div>
      )}
    </div>
  )

  if (!bureau) return explorateur
  return (
    <div className="dx-bureau">
      <Arbre
        api={api}
        spaces={spaces}
        space={space}
        folder={folder}
        breadcrumb={data?.breadcrumb}
        version={data}
        onOpen={ouvrirDepuisArbre}
      />
      {explorateur}
    </div>
  )
}
