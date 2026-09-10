import { useEffect, useState } from 'react'
import * as videosApi from '../../api/videos.js'
import Badge from '../../components/Badge.jsx'
import Icon from '../../components/Icon.jsx'
import Modal from '../../components/Modal.jsx'

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

// Panneau "Usage vidéo" (Admin > École, voir spec/SPEC.md §5.1.1) : Go
// utilisés et minutes de vidéo pour toute l'école, tous cours confondus,
// puis les 10 plus grosses vidéos. Chargé à l'ouverture (pas de cache —
// en mode réel, la taille est lue sur le disque à la demande côté
// backend, voir videos.py : usage_ecole).
export default function UsageVideoModal({ ecoleId, onClose }) {
  const [usage, setUsage] = useState(null)

  useEffect(() => {
    let annule = false
    videosApi.usage(ecoleId).then((u) => {
      if (!annule) setUsage(u)
    })
    return () => {
      annule = true
    }
  }, [ecoleId])

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
      topVideos: u.topVideos.filter((v) => v.id !== video.id),
    }))
  }

  return (
    <Modal title="Usage vidéo" onClose={onClose}>
      {usage === null ? (
        <p className="muted">Calcul en cours…</p>
      ) : (
        <>
          <div className="heures-cards">
            <div className="heures-card">
              <span className="muted">Espace utilisé</span>
              <strong>{formatTaille(usage.totalOctets)}</strong>
            </div>
            <div className="heures-card">
              <span className="muted">Durée totale</span>
              <strong>{formatDureeTotale(usage.totalSecondes)}</strong>
            </div>
          </div>

          <h3 className="usage-video__titre-liste">Les plus grosses vidéos</h3>
          {usage.topVideos.length === 0 ? (
            <p className="muted">Aucune vidéo avec un fichier pour l’instant.</p>
          ) : (
            <div className="usage-video__liste">
              {usage.topVideos.map((v) => (
                <div key={v.id} className="usage-video__ligne">
                  <div className="usage-video__titre">
                    <div className="usage-video__titre-ligne">
                      <strong>{v.titre}</strong>
                      <span className="muted"> — {v.cours}</span>
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
        </>
      )}
    </Modal>
  )
}
