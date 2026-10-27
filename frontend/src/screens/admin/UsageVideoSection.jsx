import { useEffect, useState } from 'react'
import * as ressourcesApi from '../../api/ressources.js'
import * as videosApi from '../../api/videos.js'
import Badge from '../../components/Badge.jsx'
import Icon from '../../components/Icon.jsx'
import { formaterCout } from '../../utils/inscriptionEleve.js'

// Mo tant que ça reste sous 1 Go (demande : une vidéo ou même le total
// dépasse rarement 1 Go en démo, "0.01 Go" ne distinguait pas deux
// tailles différentes) — Go seulement au-delà, avec l'unité toujours
// écrite en toutes lettres (jamais un nombre nu).
function formatTaille(octets) {
  if (octets < 1e9) return `${(octets / 1e6).toFixed(1)} Mo`
  return `${(octets / 1e9).toFixed(2)} Go`
}

// Pareil pour la durée totale : secondes tant que ça reste sous la
// minute, minutes au-delà — l'unité toujours écrite (demande : "1.0"
// seul ne dit pas si c'est des secondes ou des minutes).
function formatDureeTotale(secondes) {
  if (secondes < 60) return `${Math.round(secondes)} s`
  return `${(secondes / 60).toFixed(1)} min`
}

// 'mm:ss', même convention que Présence/Chorégraphie pour une durée.
function formatDuree(secondes) {
  if (secondes == null) return '–'
  const mm = String(Math.floor(secondes / 60)).padStart(2, '0')
  const ss = String(secondes % 60).padStart(2, '0')
  return `${mm}:${ss}`
}

// Section « Usage ressources et IA de la saison » (Admin > École, voir
// spec/SPEC.md §5.1.1 ; « Usage vidéo » jusqu'au 2026-10-15) : mémoire et IA
// (voir api/ressources.js), puis les vidéos : Go
// utilisés et minutes de vidéo pour toute l'école, tous cours confondus,
// puis les 10 plus grosses vidéos. Affichée directement, au même niveau et
// sous le même format de titre que la section "Administrateurs" (demande
// du 2026-09-21 — c'était avant une fenêtre ouverte par un bouton).
// Dépliable, FERMÉE par défaut (demande du 2026-09-21) : un clic sur le
// titre l'ouvre. Chargée seulement à la première ouverture — la taille est
// lue sur le disque à la demande côté backend (voir videos.py :
// usage_ecole), inutile de la calculer si personne ne regarde.
// `choregraphies`/`cours` : pour dire où se trouve chaque vidéo. Le module
// vidéo, générique, ne le sait pas (voir api/videos.js) ; c'est ici, dans
// l'appli, qu'on fait le rapprochement.
export default function UsageVideoSection({ ecoleId, choregraphies = [], cours = [], setChoregraphies }) {
  const [ouvert, setOuvert] = useState(false)
  const [usage, setUsage] = useState(null)
  // Mémoire et IA (voir api/ressources.js) : chargés tout de suite, le
  // titre porte le nom de la saison affichée.
  const [ressources, setRessources] = useState(null)
  const [memoireOuverte, setMemoireOuverte] = useState(false)
  const [iaOuverte, setIaOuverte] = useState(false)

  useEffect(() => {
    let annule = false
    ressourcesApi
      .usage(ecoleId)
      .then((r) => !annule && setRessources(r))
      .catch(() => {})
    return () => {
      annule = true
    }
  }, [ecoleId])

  useEffect(() => {
    if (!ouvert || usage !== null) return
    let annule = false
    videosApi.usage(ecoleId).then((u) => {
      if (!annule) setUsage(u)
    })
    return () => {
      annule = true
    }
  }, [ecoleId, ouvert, usage])

  async function supprimer(video) {
    if (!window.confirm(`Supprimer « ${video.titre} » ? Le fichier sera aussi effacé.`)) return
    await videosApi.supprimerParId(video.id)
    // Retire la ligne et déduit sa taille/durée des totaux — évite un
    // aller-retour réseau pour tout recalculer (mais un top 10 tronqué à
    // 9 lignes ne "remonte" pas une 11e vidéo restée hors liste ; rare
    // en pratique, acceptable pour ce panneau de consultation).
    setUsage((u) => ({
      totalOctets: u.totalOctets - video.tailleOctets,
      totalSecondes: u.totalSecondes - (video.dureeSecondes || 0),
      totalToutesSaisonsOctets: u.totalToutesSaisonsOctets - video.tailleOctets,
      totalToutesSaisonsSecondes: u.totalToutesSaisonsSecondes - (video.dureeSecondes || 0),
      topVideos: u.topVideos.filter((v) => v.id !== video.id),
    }))
    // Sans ça, l'écran Chorégraphie garderait la vidéo supprimée en
    // mémoire (image cassée : le fichier est réellement effacé).
    setChoregraphies?.((liste) =>
      liste.map((ch) =>
        ch.videos.some((v) => v.id === video.id)
          ? { ...ch, videos: ch.videos.filter((v) => v.id !== video.id) }
          : ch,
      ),
    )
  }

  function emplacement(videoId) {
    const choregraphie = choregraphies.find((ch) => ch.videos.some((v) => v.id === videoId))
    return {
      choregraphie: choregraphie?.nom ?? null,
      cours: cours.find((c) => c.id === choregraphie?.coursId)?.nom ?? null,
    }
  }

  return (
    <section className="admin-usage-video">
      <h3 className="section-label">
        <button
          type="button"
          className="section-label__depliant"
          aria-expanded={ouvert}
          onClick={() => setOuvert((o) => !o)}
        >
          <Icon name={ouvert ? 'chevronDown' : 'chevronRight'} size={14} />
          Usage des ressources &amp; IA{ressources?.saison ? ` (${ressources.saison} sélectionnée)` : ''}
        </button>
      </h3>
      {!ouvert ? null : usage === null ? (
        <p className="muted">Calcul en cours…</p>
      ) : (
        <>
          {/* Deux sous-catégories dépliables, en retrait sous le titre
              (demandes du 2026-10-15) : « Mémoire » (place sur le disque,
              puis le détail des vidéos) et « IA » (coût par poste). */}
          <Rubrique titre="Mémoire" ouvert={memoireOuverte} onBascule={() => setMemoireOuverte((o) => !o)}>
            {ressources && (
              <>
                <div className="usage-ressources__lignes">
                  {ressources.memoire.map((r) => (
                    <div key={r.cle} className="usage-ressources__ligne">
                      <span>{r.libelle}</span>
                      <span>{formatTaille(r.octets)}</span>
                    </div>
                  ))}
                  <div className="usage-ressources__ligne usage-ressources__ligne--total">
                    <span>Total sur le disque</span>
                    <span>{formatTaille(ressources.memoireTotalOctets)}</span>
                  </div>
                </div>
              </>
            )}
            <h5 className="usage-ressources__sous-titre">Détail des vidéos</h5>
            {/* Par module (Chorégraphies, Sparring…), saison affichée (Seb, 27 octobre). */}
            {usage.rubriques.length > 0 && (
              <div className="usage-ressources__lignes">
                {usage.rubriques.map((r) => (
                  <div key={r.libelle} className="usage-ressources__ligne">
                    <span>{r.libelle}</span>
                    <span>{formatTaille(r.octets)}</span>
                  </div>
                ))}
              </div>
            )}
            {/* Saisons (spec §2.6) : la saison affichée, puis le cumul de
                toutes les saisons (seul chiffre qui sort de la saison
                affichée). */}
            <div className="heures-cards">
              <div className="heures-card">
                <span className="muted">{`Mémoire utilisée (${ressources?.saison ?? 'saison sélectionnée'})`}</span>
                <strong>{formatTaille(usage.totalOctets)}</strong>
              </div>
              <div className="heures-card">
                <span className="muted">{`Durée vidéo (${ressources?.saison ?? 'saison sélectionnée'})`}</span>
                <strong>{formatDureeTotale(usage.totalSecondes)}</strong>
              </div>
            </div>
            <div className="heures-cards">
              <div className="heures-card">
                <span className="muted">Mémoire utilisée (toutes saisons)</span>
                <strong>{formatTaille(usage.totalToutesSaisonsOctets)}</strong>
              </div>
              <div className="heures-card">
                <span className="muted">Durée des vidéos, toutes saisons</span>
                <strong>{formatDureeTotale(usage.totalToutesSaisonsSecondes)}</strong>
              </div>
            </div>

            <h3 className="usage-video__titre-liste">Les plus grosses vidéos</h3>
            {usage.topVideos.length === 0 ? (
              <p className="muted">Aucune vidéo avec un fichier pour l’instant.</p>
            ) : (
              <div className="usage-video__liste">
                {usage.topVideos.map((video) => ({ ...video, ...emplacement(video.id) })).map((v) => (
                  <div key={v.id} className="usage-video__ligne">
                    <div className="usage-video__titre">
                      <div className="usage-video__titre-ligne">
                        <strong>{v.titre}</strong>
                        {v.cours && <span className="muted"> — {v.cours}</span>}
                      </div>
                      {v.choregraphie && (
                        <Badge className="usage-video__choregraphie">
                          <Icon name="music" size={12} /> {v.choregraphie}
                        </Badge>
                      )}
                    </div>
                    <div className="usage-video__meta">
                      <span>{formatTaille(v.tailleOctets)}</span>
                      <span className="muted">{formatDuree(v.dureeSecondes)}</span>
                    </div>
                    <button
                      type="button"
                      className="icon-btn icon-btn--sm"
                      onClick={() => supprimer(v)}
                      aria-label={`Supprimer ${v.titre}`}
                    >
                      <Icon name="trash" size={16} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </Rubrique>
          <Rubrique titre="IA" ouvert={iaOuverte} onBascule={() => setIaOuverte((o) => !o)}>
            {ressources && (
              <>
                <div className="usage-ressources__lignes">
                  {ressources.ia.length === 0 && <p className="muted">Aucune opération d’IA cette saison.</p>}
                  {ressources.ia.map((p) => (
                    <div key={p.categorie} className="usage-ressources__ligne">
                      <span>
                        {p.libelle} <span className="muted">({p.nombre})</span>
                      </span>
                      <span>{formaterCout(p.coutUsd)}</span>
                    </div>
                  ))}
                  <div className="usage-ressources__ligne usage-ressources__ligne--total">
                    <span>Total de la saison</span>
                    <span>{formaterCout(ressources.iaTotalUsd)}</span>
                  </div>
                  <div className="usage-ressources__ligne">
                    <span className="muted">Toutes saisons</span>
                    <span className="muted">{formaterCout(ressources.iaTotalToutesSaisonsUsd)}</span>
                  </div>
                </div>
                <PlafondAssistant ecoleId={ecoleId} ressources={ressources} setRessources={setRessources} />
              </>
            )}
          </Rubrique>
        </>
      )}
    </section>
  )
}

// Plafond mensuel de l'assistant (Seb, 16 octobre) : ce que l'assistant a
// coûté depuis le 1er du mois, sur le plafond. Au-delà, il ne répond plus
// aux admins et aux profs jusqu'au mois suivant (jamais bloqué pour le
// Super User). Le plafond, en dollars comme la facture d'Anthropic, ne se
// règle que par le Super User.
function PlafondAssistant({ ecoleId, ressources, setRessources }) {
  const [saisie, setSaisie] = useState(null)
  const [erreur, setErreur] = useState(null)
  const plafond = ressources.assistantPlafondUsd
  const depasse = ressources.assistantCoutDuMoisUsd >= plafond

  async function enregistrer() {
    const valeur = Number(String(saisie).replace(',', '.'))
    if (!Number.isFinite(valeur) || valeur < 0) {
      setErreur('Montant invalide.')
      return
    }
    setErreur(null)
    try {
      const nouveau = await ressourcesApi.definirPlafondAssistant(ecoleId, valeur)
      setRessources((r) => ({ ...r, assistantPlafondUsd: nouveau }))
      setSaisie(null)
    } catch (err) {
      setErreur(err.message)
    }
  }

  return (
    <div className="usage-ressources__lignes">
      <div className="usage-ressources__ligne usage-ressources__ligne--total">
        <span>Assistant ce mois-ci</span>
        <span className={depasse ? 'usage-ressources__depasse' : undefined}>
          {formaterCout(ressources.assistantCoutDuMoisUsd)} / {formaterCout(plafond)}{' '}
          <span className="muted">({plafond.toLocaleString('fr-FR')} $)</span>
        </span>
      </div>
      {depasse && <p className="muted">Plafond atteint : l’assistant reviendra le 1er du mois.</p>}
      {ressources.assistantPlafondModifiable &&
        (saisie === null ? (
          <button type="button" className="btn btn--secondary" onClick={() => setSaisie(String(plafond))}>
            Changer le plafond mensuel
          </button>
        ) : (
          <div className="usage-ressources__plafond">
            <label htmlFor="plafond-assistant">Plafond mensuel (en dollars)</label>
            <input
              id="plafond-assistant"
              className="field-input"
              inputMode="decimal"
              value={saisie}
              onChange={(e) => setSaisie(e.target.value)}
            />
            <button type="button" className="btn btn--primary" onClick={enregistrer}>
              Enregistrer
            </button>
            <button type="button" className="btn btn--secondary" onClick={() => setSaisie(null)}>
              Annuler
            </button>
          </div>
        ))}
      {erreur && <p className="admin-panel__erreur">{erreur}</p>}
    </div>
  )
}

// Sous-catégorie dépliable, en retrait sous le titre de la section.
function Rubrique({ titre, ouvert, onBascule, children }) {
  return (
    <div className="usage-ressources__rubrique-bloc">
      <h4 className="usage-ressources__rubrique">
        <button type="button" className="section-label__depliant" aria-expanded={ouvert} onClick={onBascule}>
          <Icon name={ouvert ? 'chevronDown' : 'chevronRight'} size={13} />
          {titre}
        </button>
      </h4>
      {ouvert && <div className="usage-ressources__corps">{children}</div>}
    </div>
  )
}
