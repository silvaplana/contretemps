import { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Modal from '../../components/Modal.jsx'
import { documentsApi } from '../../api/documents.js'
import FolderPicker from './FolderPicker.jsx'
import NewScreen from './NewScreen.jsx'
import Properties from './Properties.jsx'
import Share from './Share.jsx'
import { accesAssistant, ajouterProduit } from '../../api/assistant.js'
import Arbre from './Arbre.jsx'
import { brancherDocs, prendreFichierAOuvrir } from './assistantGlobal.js'
import Editeur from './Editeur.jsx'
import Trash from './Trash.jsx'
import Viewer from './Viewer.jsx'

// Le fichier de base embarque BlockNote : chargé seulement quand on l'ouvre.
const AppFile = lazy(() => import('./app/AppFile.jsx'))
import { Cadenas, FamilyDot, FileIcon, FolderIcon, PlusIcon, StatusBadge, StatusIcon } from './icons.jsx'
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
// Notifications plus courtes (Seb, 15 octobre) : « Annuler » 5 s, message 2,5 s.
const TOAST_MS = 5000

function Thumb({ api, item }) {
  const [url, setUrl] = useState(null)
  useEffect(() => {
    let lien = null
    let annule = false
    api.blobUrl(item.id, { thumbnail: true, modifie: item.updated_at }).then(
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
  const icone = isImage(item) && item.has_thumbnail ? <Thumb api={api} item={item} /> : <FileIcon name={item.name} family={item.family} />
  if (!item.restricted) return icone
  // Fichier en accès restreint : le même cadenas que sur les dossiers.
  return (
    <span className="dx-verrouille">
      {icone}
      <Cadenas />
    </span>
  )
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
  // L'assistant est celui de toute l'appli (AssistantGlobal.jsx, bouton de
  // l'en-tête) ; Docs lui donne le dossier ouvert et fait ses cartes.
  const [assistant, setAssistant] = useState(false)
  const [coutSaison, setCoutSaison] = useState(null)
  // Éditeur OnlyOffice : encore en essai, le Super User seul.
  const [editeur, setEditeur] = useState(false)
  const [enEdition, setEnEdition] = useState(null)
  useEffect(() => {
    accesAssistant(orgId).then((x) => {
      setAssistant(x.autorise)
      setEditeur(Boolean(x.editeur))
      setCoutSaison(x.cout_saison_usd)
    }, () => {})
  }, [orgId])
  const api = useMemo(() => documentsApi(orgId), [orgId])
  const [spaces, setSpaces] = useState([])
  // Fichier créé par l'assistant depuis un autre onglet : Docs s'ouvre dessus.
  const [aOuvrir] = useState(prendreFichierAOuvrir)
  const [space, setSpace] = useState(() => aOuvrir?.space ?? lireEndroit(memoire).space)
  const [folder, setFolder] = useState(() => (aOuvrir ? aOuvrir.parent_id : lireEndroit(memoire).folder))
  const [data, setData] = useState(null)
  const [erreur, setErreur] = useState('')
  const [filtreStatut, setFiltreStatut] = useState(null)
  const [filtreFamille, setFiltreFamille] = useState(null)
  const [bulle, setBulle] = useState(null)
  const [recherche, setRecherche] = useState(null)
  const [trouves, setTrouves] = useState(null)
  // Sélection de plusieurs éléments (Seb, 16 octobre). Ordinateur : clic,
  // Ctrl+clic, Maj+clic, Ctrl+A, encadrement à la souris. Téléphone :
  // « Sélectionner plusieurs » dans le menu, puis toucher les éléments.
  const [selIds, setSelIds] = useState([])
  const [ancre, setAncre] = useState(null) // dernier élément cliqué (Maj+clic)
  const [modeChoix, setModeChoix] = useState(false)
  const [cadre, setCadre] = useState(null) // rectangle d'encadrement à l'écran
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
  // Fichier de l'appli ouvert (fichier de base, spec fichier-de-base.md).
  const [appli, setAppli] = useState(aOuvrir)
  const [choix, setChoix] = useState(null) // { items, mode: 'move' | 'copy' }
  const [nom, setNom] = useState(null) // { mode: 'folder' | 'rename', item?, value }
  const [corbeille, setCorbeille] = useState(false)
  const [pressePapier, setPressePapier] = useState(null) // { items, mode: 'copy' | 'cut' }
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
    // Annuler reste proposé 5 s ; un simple message, 2,5 s (voir TOAST_MS).
    minuteurToast.current = setTimeout(() => setToast(null), annuler ? TOAST_MS : 2500)
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
  // « Récents » (arborescence sur ordinateur) : les derniers fichiers
  // modifiés, tous espaces, affichés comme des résultats de recherche.
  // Rechargés à chaque changement (`data`).
  const [recentsActif, setRecentsActif] = useState(false)
  const [recents, setRecents] = useState(null)
  useEffect(() => {
    if (!recentsActif) return undefined
    let annule = false
    api.recent().then((r) => !annule && setRecents(r), (e) => !annule && setErreur(e.message))
    return () => {
      annule = true
    }
  }, [api, recentsActif, data])
  const resultats = rechercheActive && trouves ? trouves.r : recentsActif ? (recents ?? []) : null
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

  // Ce qui est affiché (recherche, Récents ou dossier), après les filtres.
  const items = resultats ?? data?.items ?? []
  const visible = (x) => (!filtreStatut || x.status === filtreStatut) && (!filtreFamille || x.family === filtreFamille)
  // Dossiers des saisons passées : en lecture seule, regroupés à part sous
  // « Saisons précédentes » (Seb, 15 octobre).
  const anciennesSaisons = items.filter((x) => x.system_kind === 'period' && !x.period_current && visible(x))
  const dossiers = items.filter((x) => x.kind === 'folder' && visible(x) && !anciennesSaisons.includes(x))
  const lesFichiers = items.filter((x) => (x.kind === 'file' || x.kind === 'app') && visible(x))
  // Dans l'ordre de l'écran (Maj+clic, Ctrl+A).
  const ordre = [...dossiers, ...lesFichiers, ...anciennesSaisons]
  const selectionnes = ordre.filter((x) => selIds.includes(x.id))
  const selection = selectionnes.length === 1 ? selectionnes[0] : null

  function ouvrir(item) {
    setFeuille(null)
    setPlus(false)
    if (item.kind === 'folder') {
      if (item.space !== space) setSpace(item.space)
      setFolder(item.id)
      setRecherche(null)
      setRecentsActif(false)
      setSelection(null)
    } else if (item.kind === 'app') {
      setAppli(item)
    } else {
      setVue(item)
    }
  }

  function allerA(id) {
    setFolder(id)
    setSelection(null)
    setRecentsActif(false)
  }

  function changerEspace(cle) {
    setSpace(cle)
    setFolder(null)
    setSelection(null)
    setRecherche(null)
    setRecentsActif(false)
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

  function setSelection(item) {
    setSelIds(item ? [item.id] : [])
    setAncre(item?.id ?? null)
    if (!item) setModeChoix(false)
  }

  function basculer(item) {
    setAncre(item.id)
    const suivant = selIds.includes(item.id) ? selIds.filter((id) => id !== item.id) : [...selIds, item.id]
    setSelIds(suivant)
    if (suivant.length === 0) setModeChoix(false)
  }

  // Clic à la souris : Ctrl ajoute ou retire, Maj prend toute la plage
  // depuis le dernier élément cliqué (comme l'explorateur Windows).
  function cliquer(item, e) {
    const ctrl = e.ctrlKey || e.metaKey
    if (e.shiftKey && ancre != null) {
      const i = ordre.findIndex((x) => x.id === ancre)
      const j = ordre.findIndex((x) => x.id === item.id)
      if (i >= 0 && j >= 0) {
        const plage = ordre.slice(Math.min(i, j), Math.max(i, j) + 1).map((x) => x.id)
        setSelIds(ctrl ? [...new Set([...selIds, ...plage])] : plage)
        return
      }
    }
    if (ctrl) basculer(item)
    else setSelection(item)
  }

  // Ce qu'on prend en glissant un élément : toute la sélection s'il en fait partie.
  const groupeDe = (item) => (selIds.includes(item.id) && selectionnes.length > 1 ? selectionnes : [item])
  const enListe = (x) => (Array.isArray(x) ? x : [x])
  const nommer = (liste) => (liste.length > 1 ? `${liste.length} éléments` : `« ${liste[0].name} »`)
  const accord = (liste) => (liste.length > 1 ? 's' : '')

  async function supprimer(x) {
    const liste = enListe(x)
    setFeuille(null)
    const faits = []
    for (const item of liste) {
      try {
        await api.remove(item.id)
        faits.push(item)
      } catch (e) {
        echec(e)
      }
    }
    setSelection(null)
    await recharger()
    if (faits.length) {
      montrerToast(`${nommer(faits)} mis à la corbeille`, async () => {
        for (const item of faits) await api.restore(item.id)
        await recharger()
      })
    }
  }

  async function deplacer(x, versEspace, versDossier) {
    const liste = enListe(x).filter((item) => item.id !== versDossier)
    const avant = folder
    const faits = []
    for (const item of liste) {
      try {
        await api.move(item.id, versEspace, versDossier)
        faits.push(item)
      } catch (e) {
        echec(e)
      }
    }
    await recharger()
    if (faits.length) {
      montrerToast(`${nommer(faits)} déplacé${accord(faits)}`, async () => {
        for (const item of faits) await api.move(item.id, item.space, avant)
        await recharger()
      })
    }
  }

  async function copier(x, versEspace, versDossier) {
    const copies = []
    for (const item of enListe(x)) {
      try {
        copies.push(await api.copy(item.id, versEspace, versDossier))
      } catch (e) {
        echec(e)
      }
    }
    await recharger()
    if (copies.length) {
      montrerToast(`${nommer(copies)} collé${accord(copies)}`, async () => {
        for (const copie of copies) await api.remove(copie.id)
        await recharger()
      })
    }
  }

  async function coller() {
    if (!pressePapier) return
    const { items: liste, mode } = pressePapier
    if (mode === 'cut') {
      setPressePapier(null)
      await deplacer(liste, space, folder)
    } else {
      await copier(liste, space, folder)
    }
  }

  async function telecharger(item, version) {
    try {
      const url = await api.blobUrl(item.id, { version: version?.id, modifie: item.updated_at })
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
      const choisis = selectionnes
      if (ctrl && e.key.toLowerCase() === 'a') {
        e.preventDefault()
        setSelIds(ordre.map((x) => x.id))
      } else if (ctrl && e.key === 'c' && choisis.length) {
        setPressePapier({ items: choisis, mode: 'copy' })
        montrerToast(`${nommer(choisis)} copié${accord(choisis)} : ouvrez un dossier puis Ctrl+V`)
      } else if (ctrl && e.key === 'x' && choisis.length && choisis.every((x) => x.can_restructure !== false)) {
        setPressePapier({ items: choisis, mode: 'cut' })
        montrerToast(`${nommer(choisis)} coupé${accord(choisis)} : ouvrez un dossier puis Ctrl+V`)
      } else if (ctrl && e.key === 'v' && pressePapier && peutAjouter) {
        e.preventDefault()
        coller()
      } else if ((e.key === 'Delete' || e.key === 'Backspace') && choisis.length) {
        e.preventDefault()
        supprimer(choisis)
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
    if (id === 'assistant') return id
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
        if (cible === 'assistant') {
          // Lâché sur l'assistant : joint à la question suivante.
          window.dispatchEvent(
            new CustomEvent('dx-joindre', { detail: groupeDe(item).map((x) => ({ id: x.id, nom: x.name })) }),
          )
        } else if (cible === 'root') {
          if (folder != null) deplacer(groupeDe(item), space, null)
        } else if (cible != null && cible !== folder) {
          deplacer(groupeDe(item), space, cible)
        }
      } else {
        setFeuille(item)
      }
      return
    }
    if (a.souris) cliquer(item, e)
    else if (modeChoix) basculer(item)
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
    const groupe = groupeDe(item)
    e.dataTransfer.setData('application/x-dx-node', groupe.map((x) => x.id).join(','))
    // Pour l'assistant : on peut aussi lâcher ces éléments dans la conversation.
    e.dataTransfer.setData('application/x-dx-noms', JSON.stringify(groupe.map((x) => ({ id: x.id, nom: x.name }))))
    e.dataTransfer.effectAllowed = 'move'
    if (!selIds.includes(item.id)) setSelection(item)
  }

  function dragOver(e, cible) {
    const interne = Array.from(e.dataTransfer.types).includes('application/x-dx-node')
    if (!interne && !hasFiles(e)) return
    if (cible !== 'list' && interne && selIds.includes(cible)) return
    e.preventDefault()
    e.stopPropagation()
    e.dataTransfer.dropEffect = interne ? 'move' : 'copy'
    setSurvol(cible)
  }

  function drop(e, cibleDossier) {
    e.preventDefault()
    e.stopPropagation()
    setSurvol(null)
    const ids = e.dataTransfer.getData('application/x-dx-node')
    if (ids) {
      const liste = ids.split(',').map((id) => items.find((x) => String(x.id) === id)).filter(Boolean)
      if (liste.length && cibleDossier) deplacer(liste, space, cibleDossier)
      return
    }
    if (e.dataTransfer.files?.length) importer(e.dataTransfer.files, cibleDossier ?? folder)
  }

  // Encadrement à la souris, en partant d'un endroit vide de la liste
  // (Ctrl ou Maj : ajoute à la sélection). Défile près des bords.
  function commencerCadre(e) {
    const liste = listeRef.current
    if (!liste) return
    e.preventDefault()
    const ajout = e.ctrlKey || e.metaKey || e.shiftKey
    const base = ajout ? selIds : []
    const departX = e.clientX
    const departY = e.clientY + liste.scrollTop
    let dernier = { x: e.clientX, y: e.clientY }
    let bouge = false
    const maj = () => {
      const y0 = departY - liste.scrollTop
      const r = {
        left: Math.min(departX, dernier.x),
        right: Math.max(departX, dernier.x),
        top: Math.min(y0, dernier.y),
        bottom: Math.max(y0, dernier.y),
      }
      setCadre(r)
      const dans = [...liste.querySelectorAll('[data-id]')]
        .filter((el) => {
          const b = el.getBoundingClientRect()
          return b.right > r.left && b.left < r.right && b.bottom > r.top && b.top < r.bottom
        })
        .map((el) => Number(el.dataset.id))
      setSelIds([...new Set([...base, ...dans])])
    }
    const bouger = (ev) => {
      dernier = { x: ev.clientX, y: ev.clientY }
      if (!bouge && Math.hypot(ev.clientX - departX, ev.clientY - e.clientY) < 5) return
      bouge = true
      const b = liste.getBoundingClientRect()
      if (ev.clientY < b.top + 30) liste.scrollTop -= 16
      else if (ev.clientY > b.bottom - 30) liste.scrollTop += 16
      maj()
    }
    const defiler = () => bouge && maj()
    const lacher = () => {
      window.removeEventListener('pointermove', bouger)
      window.removeEventListener('pointerup', lacher)
      liste.removeEventListener('scroll', defiler)
      setCadre(null)
      if (!bouge && !ajout) setSelection(null)
    }
    window.addEventListener('pointermove', bouger)
    window.addEventListener('pointerup', lacher)
    liste.addEventListener('scroll', defiler)
  }

  // --- Affichage ---
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
    const chemin = item.path?.map((p) => p.name).join(' › ') || spaces.find((s) => s.key === item.space)?.label || libelleEspace
    // Récents : où est le fichier, puis quand et par qui il a été modifié.
    const espaceDe = spaces.find((s) => s.key === item.space)?.label
    const sousTitre =
      recentsActif && !rechercheActive
        ? `${[espaceDe, ...(item.path ?? []).map((p) => p.name)].filter(Boolean).join(' › ')} · ${subtitle(item)}`
        : resultats && item.path
          ? chemin
          : subtitle(item)
    const choisi = selIds.includes(item.id)
    return (
      <div
        key={item.id}
        role="button"
        tabIndex={0}
        className={`dx-row${estDossier ? ' dx-row--dir' : ''}${choisi ? ' dx-row--sel' : ''}${survol === item.id ? ' dx-row--drop' : ''}${glisse?.item.id === item.id ? ' dx-row--lift' : ''}${pressePapier?.mode === 'cut' && pressePapier.items.some((x) => x.id === item.id) ? ' dx-row--cut' : ''}`}
        data-id={item.id}
        aria-pressed={modeChoix ? choisi : undefined}
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
          if (!selIds.includes(item.id)) setSelection(item)
          setFeuille(item)
        }}
        onKeyDown={(e) => {
          if (e.key === ' ') {
            e.preventDefault()
            setFeuille(item)
          }
        }}
      >
        {modeChoix && (
          <span className={`dx-coche${choisi ? ' dx-coche--on' : ''}`} aria-hidden="true">
            {choisi ? '✓' : ''}
          </span>
        )}
        <ItemIcon api={api} item={item} />
        <div className="dx-meta">
          <div className="dx-n">
            {item.name}
            {item.system_kind === 'period' && item.period_current && <span className="dx-current">en cours</span>}
            {item.system_kind === 'reserved' && <span className="dx-current">trésoriers seulement</span>}
          </div>
          <div className="dx-s">
            {item.status && <StatusBadge status={item.status} compact />}
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
      { icone: '➜', libelle: 'Déplacer…', faire: () => (setFeuille(null), setChoix({ items: [item], mode: 'move' })), off: !restructurer && raison },
      { icone: '☰', libelle: 'Propriétés', faire: () => (setFeuille(null), setProprietes({ id: item.id, tab: 'Infos' })), hl: true },
      { icone: '🗑', libelle: 'Supprimer', faire: () => supprimer(item), off: !restructurer && raison, danger: true },
    ]
    const autres = [
      {
        icone: '☑',
        libelle: 'Sélectionner plusieurs',
        faire: () => {
          setFeuille(null)
          setPlus(false)
          setSelection(item)
          setModeChoix(true)
        },
      },
      { icone: '⧉', libelle: 'Copier', faire: () => (setFeuille(null), setPressePapier({ items: [item], mode: 'copy' }), montrerToast(`« ${item.name} » copié : ouvrez un dossier puis « Coller ici »`)), off: systeme && 'Copiez plutôt son contenu' },
      { icone: '⧉', libelle: 'Copier vers…', faire: () => (setFeuille(null), setChoix({ items: [item], mode: 'copy' })), off: systeme && 'Copiez plutôt son contenu' },
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
  const multiRestructurable = selectionnes.every((x) => x.system_kind == null && !x.frozen && peutAjouterDans(x))

  function ouvrirDepuisArbre(s, id) {
    setFeuille(null)
    setRecherche(null)
    setSelection(null)
    setRecentsActif(false)
    if (s !== space) setSpace(s)
    setFolder(id)
  }

  // Carte « Faire » de l'assistant : l'action passe par les mêmes routes
  // que l'explorateur, avec les droits de la personne.
  async function faireAction(carte) {
    if (carte.kind === 'creer_dossier') await api.createFolder(carte.espace, carte.dossier_parent_id, carte.nom)
    else if (carte.kind === 'creer_fichier_texte') {
      const fichier = new File([carte.contenu], carte.nom, { type: 'text/plain' })
      await api.upload(carte.espace, carte.dossier_parent_id, fichier)
    } else if (carte.kind === 'deplacer') await api.move(carte.element_id, carte.espace, carte.dossier_destination_id)
    else if (carte.kind === 'renommer') await api.rename(carte.element_id, carte.nouveau_nom)
    else if (carte.kind === 'ajouter_fichier') await ajouterProduit(orgId, carte.jeton, carte.espace, carte.dossier_parent_id)
    else if (carte.kind === 'creer_fichier_appli') {
      // Comme + > Créer un fichier : le fichier s'ouvre aussitôt, en Brouillon.
      const f = await api.createApp(carte.espace, carte.dossier_parent_id, carte.nature, carte.nom)
      await recharger()
      setAppli({ id: f.id, name: f.name, kind: 'app', family: carte.nature })
      montrerToast(`Fait : ${carte.libelle}`)
      return
    }
    await recharger()
    montrerToast(`Fait : ${carte.libelle}`)
  }

  // OnlyOffice renvoie le fichier quelques secondes après la fermeture de
  // l'éditeur : on surveille le fichier (toutes les 2 s, 30 s au plus) et
  // on met la liste à jour dès que la nouvelle version est là.
  async function attendreNouvelleVersion(fichier) {
    for (let essai = 0; essai < 15; essai += 1) {
      await new Promise((r) => setTimeout(r, 2000))
      try {
        const detail = await api.detail(fichier.id)
        if (detail.updated_at !== fichier.updated_at) {
          await recharger()
          montrerToast(`« ${fichier.name} » enregistré`)
          return
        }
      } catch {
        // fichier devenu inaccessible : on arrête
        return
      }
    }
    await recharger()
  }

  // Branchement sur l'assistant de l'appli : ce que Docs montre, lu au
  // moment d'envoyer, et ses cartes « Faire ».
  const branche = useRef(null)
  useEffect(() => {
    branche.current = {
      contexte: () => ({ space, folder_id: folder, selection_id: selection?.id ?? null, selection_ids: selIds.slice(0, 50), recents: recentsActif }),
      faire: faireAction,
    }
  })
  useEffect(() => brancherDocs({ contexte: () => branche.current.contexte(), faire: (carte) => branche.current.faire(carte) }), [])


  function voirRecents() {
    setFeuille(null)
    setRecherche(null)
    setSelection(null)
    setRecents(null)
    setRecentsActif(true)
  }

  const explorateur = (
    <div className="dx">
      <div className="dx-top">
        {recherche == null ? (
          <>
            {/* Le titre « Documents » est déjà dans la barre du haut (Seb). */}
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
        {/* Loupe, corbeille et filtres sur une seule ligne, en haut à gauche
            (Seb, 16 octobre) ; elle passe à la ligne si la place manque. */}
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
      </div>

      <div className="dx-seg" role="tablist" aria-label="Espaces">
        {spaces.map((s) => (
          <button key={s.key} type="button" role="tab" aria-selected={s.key === space} className={s.key === space ? 'on' : ''} onClick={() => changerEspace(s.key)}>
            {s.label}
          </button>
        ))}
      </div>

      {bulle && <div className="dx-tip" role="status">{bulle}</div>}

      {/* Le chemin sous les filtres (Seb, 15 octobre). */}
      {recentsActif && !rechercheActive && (
        <nav className="dx-crumb" aria-label="Emplacement">
          <b>Récents</b>
        </nav>
      )}
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

      {(selectionnes.length > 1 || modeChoix) && !panneauOuvert && (
        <div className="dx-multi" role="toolbar" aria-label="Sélection">
          <span className="dx-multi__n">
            {selectionnes.length} sélectionné{accord(selectionnes)}
          </span>
          <button type="button" className="dx-btn dx-btn--small dx-btn--ghost" onClick={() => setSelIds(ordre.map((x) => x.id))}>
            Tout
          </button>
          <button
            type="button"
            className="dx-btn dx-btn--small dx-btn--ghost"
            disabled={!selectionnes.length || !multiRestructurable}
            onClick={() => setChoix({ items: selectionnes, mode: 'move' })}
          >
            Déplacer…
          </button>
          <button
            type="button"
            className="dx-btn dx-btn--small dx-btn--ghost"
            disabled={!selectionnes.length || selectionnes.some((x) => x.system_kind != null)}
            onClick={() => {
              setPressePapier({ items: selectionnes, mode: 'copy' })
              montrerToast(`${nommer(selectionnes)} copié${accord(selectionnes)} : ouvrez un dossier puis « Coller ici »`)
            }}
          >
            Copier
          </button>
          <button
            type="button"
            className="dx-btn dx-btn--small dx-btn--ghost dx-multi__suppr"
            disabled={!selectionnes.length || !multiRestructurable}
            onClick={() => supprimer(selectionnes)}
          >
            Supprimer
          </button>
          <button type="button" className="dx-rm" aria-label="Tout désélectionner" onClick={() => setSelection(null)}>
            ✕
          </button>
        </div>
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
          if (e.target.closest('.dx-row, button, input, a, p')) return
          if (e.button === 0 && e.pointerType === 'mouse') commencerCadre(e)
          else if (e.target === e.currentTarget) setSelection(null)
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
            {recentsActif && !rechercheActive
              ? recents === null
                ? ''
                : 'Aucun fichier pour l’instant.'
              : resultats
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
            {nommer(pressePapier.items)} {pressePapier.mode === 'cut' ? 'coupé' : 'copié'}
            {accord(pressePapier.items)}
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
        <button type="button" className="dx-fab" onClick={() => setNouveau(true)} aria-label="Nouveau">
          <PlusIcon />
        </button>
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
        <Viewer
          api={api}
          item={vue}
          onClose={() => setVue(null)}
          onMore={(x) => setFeuille(x)}
          onDownload={telecharger}
          onSaved={(x) => {
            recharger()
            montrerToast(`« ${x.name} » enregistré`)
          }}
          onEditer={editeur ? (x) => setEnEdition(x) : undefined}
        />
      )}

      {appli && (
        <Suspense fallback={<div className="dx-panel" aria-busy="true" />}>
        <AppFile
          key={appli.id}
          api={api}
          item={appli}
          onClose={() => setAppli(null)}
          onToast={montrerToast}
          onShare={(x) => setPartage(x)}
          onProperties={(id) => setProprietes({ id, tab: 'Infos' })}
          onDelete={(x) => {
            setAppli(null)
            supprimer(x)
          }}
          onChanged={recharger}
          chat={{ autorise: assistant, orgId, coutSaison, bureau, onFaire: faireAction }}
        />
        </Suspense>
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
          items={choix.items}
          mode={choix.mode}
          startSpace={space}
          startFolder={folder}
          onClose={() => setChoix(null)}
          onPick={(versEspace, versDossier) => {
            const { items: liste, mode } = choix
            setChoix(null)
            if (mode === 'copy') copier(liste, versEspace, versDossier)
            else deplacer(liste, versEspace, versDossier)
          }}
        />
      )}

      {nouveau && (
        <NewScreen
          api={api}
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
          onUseTemplate={async (modele) => {
            try {
              const f = await api.useTemplate(modele.id, space, folder)
              setNouveau(false)
              await recharger()
              setAppli({ id: f.id, name: f.name, kind: 'app', family: modele.family })
            } catch (e) {
              echec(e)
            }
          }}
          onNewApp={async (famille) => {
            try {
              const f = await api.createApp(space, folder, famille)
              setNouveau(false)
              await recharger()
              setAppli({ id: f.id, name: f.name, kind: 'app', family: famille })
            } catch (e) {
              echec(e)
            }
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
          <span>
            {glisse.item.name}
            {groupeDe(glisse.item).length > 1 && ` et ${groupeDe(glisse.item).length - 1} autre${groupeDe(glisse.item).length > 2 ? 's' : ''}`}
          </span>
        </div>
      )}
      {cadre && (
        <div
          className="dx-cadre"
          style={{ left: cadre.left, top: cadre.top, width: cadre.right - cadre.left, height: cadre.bottom - cadre.top }}
          aria-hidden="true"
        />
      )}
      {glisse && !glisse.actif && (
        <div className="dx-hint" role="status">Glissez sur un dossier pour déplacer, ou lâchez pour le menu</div>
      )}


      {enEdition && (
        <Editeur
          orgId={orgId}
          item={enEdition}
          onClose={() => {
            const fichier = enEdition
            setEnEdition(null)
            setVue(null)
            montrerToast('Enregistrement des modifications…')
            attendreNouvelleVersion(fichier)
          }}
        />
      )}

      {toast && (
        <div className={`dx-toast${pressePapier ? ' dx-toast--haut' : ''}`} role="status">
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
        recentsActif={recentsActif}
        onRecents={voirRecents}
        onAccueil={() => ouvrirDepuisArbre('private', null)}
        onNouveau={() => setNouveau(true)}
      />
      {explorateur}
    </div>
  )
}
