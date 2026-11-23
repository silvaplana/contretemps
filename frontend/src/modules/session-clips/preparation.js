import { texteReste } from '../../components/Avancement.jsx'

// La préparation d'un combat au serveur (incrustation), d'après ClipOut :
// sa place dans la file, puis son avancement réel et le temps qui reste
// (Seb, 23/11). Le même texte dans le Timer et dans Combats.
export function textePreparation(clip) {
  if (clip?.preparing_queue > 0) return clip.preparing_queue === 1 ? 'En attente, 1 vidéo avant' : `En attente, ${clip.preparing_queue} vidéos avant`
  if (!clip?.preparing_progress) return 'Préparation…'
  const reste = texteReste(clip.preparing_left)
  return `Préparation ${Math.round(clip.preparing_progress * 100)} %${reste ? ` · ${reste}` : ''}`
}
