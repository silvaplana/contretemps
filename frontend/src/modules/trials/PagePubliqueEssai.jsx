import { useEffect, useRef, useState } from 'react'
import { mettreAJour, urlLogo, useApparence, versEcran } from '../../api/apparence.js'
import * as api from './api.js'
import '../../pagePublique/pagePublique.css'
import './essais.css'

// La page d'essai de l'école, sans compte (spec/modules/essai.md §2) :
// `<adresse de l'école>/essai`, aux couleurs de l'école. Reprise de la page
// publique de Sambo Admin (frontend/src/essai/EssaiPage.jsx).

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
const MAX_PERSONNES = 3

const remplir = (texte, eleve, club, parent = '') =>
  texte.replaceAll('[élève]', eleve || "l'élève").replaceAll('[club]', club).replaceAll('[parent]', parent)
const joindre = (noms) => (noms.length <= 1 ? (noms[0] ?? '') : `${noms.slice(0, -1).join(', ')} et ${noms.at(-1)}`)
const normaliser = (t) => t.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim()

let prochaine = 0
function nouvellePersonne(nom = '') {
  prochaine += 1
  return { cle: prochaine, prenom: '', nom, mineur: false, parentAutre: false, parentPrenom: '', parentNom: '', age: '', certificat: null, decharge: false }
}

export default function PagePubliqueEssai() {
  const apparence = useApparence()
  const [ecoleId, setEcoleId] = useState(null)
  const [page, setPage] = useState(null)
  const [erreur, setErreur] = useState('')
  const [resultat, setResultat] = useState(null)

  useEffect(() => {
    ;(async () => {
      try {
        const r = await fetch(`${BASE_URL}/par-host/personnalisation?host=${encodeURIComponent(window.location.host)}`)
        const vue = versEcran(await r.json())
        if (!vue.ecoleId) throw new Error('Cette adresse ne correspond à aucune école.')
        mettreAJour(vue)
        setEcoleId(vue.ecoleId)
        const p = await api.pagePublique(vue.ecoleId)
        setPage(p)
        document.title = `${p.title} · ${p.club}`
      } catch (e) {
        setErreur(e.message === 'Page introuvable' ? "Cette page n'existe pas." : e.message)
      }
    })()
  }, [])

  return (
    <div className="pp essai-pub">
      <header className="pp-haut">
        <img src={urlLogo(apparence)} alt="" />
        <span>{page?.club ?? apparence.nom}</span>
      </header>
      <main className="pp-corps">
        {erreur && <p className="pp-erreur">{erreur}</p>}
        {page && (
          <>
            <section className="essai-pub__titre">
              <h1>{page.title}</h1>
              {page.subtitle && <p>{page.subtitle}</p>}
            </section>
            {resultat ? (
              <Resultat resultat={resultat} />
            ) : (
              <>
                {page.intro && <p>{page.intro}</p>}
                <section>
                  <h2>Modalités</h2>
                  <ul>
                    {page.rules.map((r) => (
                      <li key={r}>{r}</li>
                    ))}
                    <li>Les mineurs sont accueillis à partir de {page.min_age} ans et inscrits par un parent ou représentant légal.</li>
                  </ul>
                </section>
                {page.schedule.length > 0 && (
                  <section>
                    <h2>Horaires d'entraînement</h2>
                    {page.schedule.map((h, i) => (
                      <div key={i} className="essai-pub__horaire">
                        <strong>{h.day}</strong>
                        <span>{h.course}</span>
                        <span className="muted">{h.time}</span>
                        <span className="muted">{h.place}</span>
                      </div>
                    ))}
                    {page.places.map((p) => (
                      <div key={p.name} className="essai-pub__salle">
                        <h3>{p.name}</h3>
                        <p className="muted">{p.address}</p>
                        <a
                          className="btn btn--secondary"
                          href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(p.address)}`}
                          target="_blank"
                          rel="noreferrer"
                        >
                          Voir sur la carte
                        </a>
                      </div>
                    ))}
                  </section>
                )}
                <section>
                  <h2>Inscription</h2>
                  <Formulaire page={page} ecoleId={ecoleId} onFini={setResultat} />
                </section>
              </>
            )}
            {page.contacts.length > 0 && (
              <section>
                <h2>Contact téléphone</h2>
                <div className="essai-pub__contacts">
                  {page.contacts.map((c) => (
                    <a key={c.phone} className="btn btn--secondary" href={`tel:${c.phone.replaceAll(' ', '')}`}>
                      {c.name} : {c.phone}
                    </a>
                  ))}
                </div>
              </section>
            )}
            <p className="muted essai-pub__confidentialite">{page.privacy}</p>
          </>
        )}
      </main>
    </div>
  )
}

function Formulaire({ page, ecoleId, onFini }) {
  const [personnes, setPersonnes] = useState(() => [nouvellePersonne()])
  const [email, setEmail] = useState('')
  const [erreur, setErreur] = useState('')
  const [envoi, setEnvoi] = useState(false)
  const pads = useRef({})

  const nomDe = (p) => `${p.prenom} ${p.nom}`.trim()
  const premier = nomDe(personnes[0]) || 'la 1re personne'
  const parentEstPremier = (p, i) => i > 0 && !p.parentAutre
  // Qui signe (même calcul que le serveur, trials.py : expected_signers).
  const signataires = []
  const ajouter = (nom, enfant) => {
    const existant = signataires.find((s) => normaliser(s.nom) === normaliser(nom))
    if (existant) {
      if (enfant) existant.enfants.push(enfant)
    } else signataires.push({ nom, enfants: enfant ? [enfant] : [] })
  }
  if (!personnes[0].mineur) ajouter(nomDe(personnes[0]), null)
  personnes.forEach((p, i) => {
    if (p.mineur && parentEstPremier(p, i)) ajouter(nomDe(personnes[0]), nomDe(p))
    else if (p.mineur) ajouter(`${p.parentPrenom} ${p.parentNom}`.trim(), nomDe(p))
    else if (i > 0 && personnes[0].mineur) ajouter(nomDe(p), null)
  })

  const maj = (i, cle, valeur) => setPersonnes((l) => l.map((p, j) => (j === i ? { ...p, [cle]: valeur } : p)))

  async function valider(e) {
    e.preventDefault()
    setErreur('')
    const sansCertificat = personnes.find((p) => !p.certificat)
    if (sansCertificat) return setErreur(`Merci de joindre le certificat médical de ${nomDe(sansCertificat) || 'chaque personne'}`)
    const nonSigne = signataires.findIndex((_, k) => pads.current[k]?.vide())
    if (nonSigne !== -1) return setErreur(`Merci de faire signer ${signataires[nonSigne].nom || 'le parent'}`)
    const f = new FormData()
    f.append('email', email)
    f.append('terms_id', page.terms_id)
    personnes.forEach((p, i) => {
      f.append(`first_name_${i}`, p.prenom)
      f.append(`last_name_${i}`, p.nom)
      f.append(`minor_${i}`, p.mineur)
      f.append(`age_${i}`, p.mineur ? p.age : '')
      f.append(`parent_is_first_${i}`, p.mineur && parentEstPremier(p, i))
      f.append(`parent_first_name_${i}`, p.mineur && !parentEstPremier(p, i) ? p.parentPrenom : '')
      f.append(`parent_last_name_${i}`, p.mineur && !parentEstPremier(p, i) ? p.parentNom : '')
      f.append(`waiver_${i}`, p.decharge)
      f.append(`certificate_${i}`, p.certificat)
    })
    for (const [k, s] of signataires.entries()) {
      f.append(`signature_name_${k}`, s.nom)
      f.append(`signature_${k}`, await pads.current[k].image(), `signature-${k}.png`)
    }
    setEnvoi(true)
    try {
      onFini({ ...(await api.inscrire(ecoleId, f)), email })
      window.scrollTo({ top: 0, behavior: 'smooth' })
    } catch (e2) {
      setErreur(e2.message === 'Failed to fetch' ? 'Connexion impossible, réessayez' : e2.message)
    }
    setEnvoi(false)
  }

  return (
    <form className="essai-pub__formulaire" onSubmit={valider}>
      {personnes.map((p, i) => (
        <fieldset key={p.cle}>
          <legend>{i === 0 ? 'La personne à inscrire' : `Personne ${i + 1} (même famille)`}</legend>
          <label htmlFor={`prenom-${p.cle}`}>Prénom</label>
          <input id={`prenom-${p.cle}`} className="essais__champ" required value={p.prenom} onChange={(e) => maj(i, 'prenom', e.target.value)} />
          <label htmlFor={`nom-${p.cle}`}>Nom</label>
          <input id={`nom-${p.cle}`} className="essais__champ" required value={p.nom} onChange={(e) => maj(i, 'nom', e.target.value)} />
          <label className="essai-pub__case">
            <input type="checkbox" checked={p.mineur} onChange={(e) => maj(i, 'mineur', e.target.checked)} />
            <span>Cette personne est mineure</span>
          </label>
          {p.mineur && (
            <div className="essai-pub__parent">
              <strong>Parent ou représentant légal</strong>
              {i > 0 && (
                <label className="essai-pub__case">
                  <input type="checkbox" checked={p.parentAutre} onChange={(e) => maj(i, 'parentAutre', e.target.checked)} />
                  <span>Le parent n'est pas {premier}</span>
                </label>
              )}
              {parentEstPremier(p, i) ? (
                <p className="muted">{premier}</p>
              ) : (
                <>
                  <label htmlFor={`pprenom-${p.cle}`}>Prénom du parent</label>
                  <input id={`pprenom-${p.cle}`} className="essais__champ" required value={p.parentPrenom} onChange={(e) => maj(i, 'parentPrenom', e.target.value)} />
                  <label htmlFor={`pnom-${p.cle}`}>Nom du parent</label>
                  <input id={`pnom-${p.cle}`} className="essais__champ" required value={p.parentNom} onChange={(e) => maj(i, 'parentNom', e.target.value)} />
                </>
              )}
              <label htmlFor={`age-${p.cle}`}>Âge</label>
              <input
                id={`age-${p.cle}`}
                className="essais__champ essais__champ--court"
                type="number"
                inputMode="numeric"
                min={page.min_age}
                max="17"
                required
                value={p.age}
                onChange={(e) => maj(i, 'age', e.target.value)}
              />
            </div>
          )}
          {i === 0 && (
            <>
              <label htmlFor="essai-email">E-mail</label>
              <input id="essai-email" className="essais__champ" type="email" inputMode="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
              <p className="muted">Le QR code vous sera envoyé à cette adresse.</p>
            </>
          )}
          <span className="essai-pub__etiquette">Certificat médical</span>
          <p className="muted">{page.certificate_hint}</p>
          <label className={`essai-pub__fichier${p.certificat ? ' essai-pub__fichier--ok' : ''}`}>
            <input type="file" accept="image/*,application/pdf,.heic,.heif" onChange={(e) => maj(i, 'certificat', e.target.files[0] ?? null)} />
            {p.certificat ? `✓ ${p.certificat.name}` : '📷 Joindre le certificat médical'}
          </label>
          <label className="essai-pub__case">
            <input type="checkbox" required checked={p.decharge} onChange={(e) => maj(i, 'decharge', e.target.checked)} />
            <span>
              <strong>Décharge de responsabilité : </strong>
              {remplir(page.waiver, nomDe(p), page.club)}
            </span>
          </label>
          {i > 0 && (
            <button type="button" className="btn btn--secondary" onClick={() => setPersonnes((l) => l.filter((_, j) => j !== i))}>
              Retirer cette personne
            </button>
          )}
        </fieldset>
      ))}
      {personnes.length < MAX_PERSONNES && (
        <button type="button" className="essai-pub__ajouter" onClick={() => setPersonnes((l) => [...l, nouvellePersonne(l[0].nom)])}>
          + Ajouter une personne de la même famille
          <small>(même adresse e-mail ; sinon, faire une autre demande)</small>
        </button>
      )}
      <fieldset>
        <legend>{signataires.length > 1 ? 'Signatures' : 'Signature'}</legend>
        {signataires.map((s, k) => (
          <div key={k} className="essai-pub__signataire">
            <strong>{s.nom ? `Signature de ${s.nom}` : 'Signature'}</strong>
            {s.enfants.length > 0 && <p className="essai-pub__accord">{remplir(page.parental_consent, joindre(s.enfants), page.club, s.nom)}</p>}
            <Signature pads={pads} index={k} />
          </div>
        ))}
      </fieldset>
      {erreur && <p className="pp-erreur">{erreur}</p>}
      <button type="submit" className="btn btn--primary btn--block essai-pub__valider" disabled={envoi}>
        {envoi ? 'Envoi…' : "Valider l'inscription"}
      </button>
    </form>
  )
}

// Signature au doigt (ou à la souris), sans bibliothèque : un canvas blanc
// à la taille de l'écran ; « Effacer » recommence.
function Signature({ pads, index }) {
  const canvas = useRef(null)
  const [vide, setVide] = useState(true)

  useEffect(() => {
    const c = canvas.current
    const ratio = Math.max(window.devicePixelRatio || 1, 1)
    c.width = c.offsetWidth * ratio
    c.height = c.offsetHeight * ratio
    const g = c.getContext('2d')
    g.scale(ratio, ratio)
    g.fillStyle = '#fff'
    g.fillRect(0, 0, c.width, c.height)
    g.lineWidth = 2.5
    g.lineCap = 'round'
    g.lineJoin = 'round'
    g.strokeStyle = '#111'
    let trace = false
    const point = (e) => {
      const b = c.getBoundingClientRect()
      return [e.clientX - b.left, e.clientY - b.top]
    }
    const debut = (e) => {
      trace = true
      c.setPointerCapture(e.pointerId)
      g.beginPath()
      g.moveTo(...point(e))
    }
    const suite = (e) => {
      if (!trace) return
      g.lineTo(...point(e))
      g.stroke()
      setVide(false)
    }
    const fin = () => {
      trace = false
    }
    c.addEventListener('pointerdown', debut)
    c.addEventListener('pointermove', suite)
    c.addEventListener('pointerup', fin)
    c.addEventListener('pointercancel', fin)
    const registre = pads.current
    registre[index] = {
      vide: () => c.dataset.vide !== 'non',
      image: () => new Promise((ok) => c.toBlob(ok, 'image/png')),
      effacer: () => {
        g.fillRect(0, 0, c.width, c.height)
        setVide(true)
      },
    }
    return () => {
      c.removeEventListener('pointerdown', debut)
      c.removeEventListener('pointermove', suite)
      c.removeEventListener('pointerup', fin)
      c.removeEventListener('pointercancel', fin)
      delete registre[index]
    }
  }, [pads, index])

  return (
    <div className="essai-pub__signature">
      <canvas ref={canvas} data-vide={vide ? 'oui' : 'non'} aria-label="Zone de signature" />
      {vide ? (
        <span className="essai-pub__signez">Signez ici avec le doigt</span>
      ) : (
        <button type="button" className="btn btn--link" onClick={() => pads.current[index].effacer()}>
          Effacer
        </button>
      )}
    </div>
  )
}

function Resultat({ resultat }) {
  const crees = resultat.people.filter((p) => p.status === 'created')
  const deja = resultat.people.filter((p) => p.status === 'existing')
  const nom = (p) => `${p.first_name} ${p.last_name}`
  return (
    <section className="essai-pub__resultat">
      <h2>Inscription confirmée</h2>
      <p>
        Présentez {resultat.people.length > 1 ? 'le QR code de chaque personne' : 'ce QR code'} au prof <strong>au début du cours d'essai</strong>.
      </p>
      {resultat.people.map((p) => (
        <figure key={nom(p)} className="essai-pub__qr">
          <img src={p.qr} alt={`QR code de ${nom(p)}`} />
          <figcaption>{nom(p)}</figcaption>
        </figure>
      ))}
      {deja.length > 0 && (
        <p>
          <strong>{joindre(deja.map(nom))}</strong> {deja.length > 1 ? 'étaient déjà inscrits' : 'était déjà inscrit(e)'} : c'est le même QR code.
        </p>
      )}
      {crees.length + deja.length > 0 && (
        <p className="muted">
          Un e-mail avec {resultat.people.length > 1 ? 'les QR codes' : 'le QR code'} a été envoyé à {resultat.email} (pensez à regarder dans les
          courriers indésirables).
        </p>
      )}
    </section>
  )
}
