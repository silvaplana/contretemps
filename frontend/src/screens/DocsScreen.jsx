import { compteEnCours } from '../api/session.js'
import Explorer from '../modules/documents/Explorer.jsx'

// Onglet Docs : dossiers et fichiers (Public, Privé, Personnel), avec leurs
// droits. Tout le code est dans modules/documents/ (futur module d'AppBase,
// voir backend/src/documents/), branché ici sur l'école affichée.
// `memoire` : où ranger, sur cet appareil, le dernier endroit ouvert, pour
// y revenir la fois suivante (un par école et par profil).
// `assistant` : l'assistant (prototype) n'est ouvert qu'au Super User.
export default function DocsScreen({ ecoleId, assistant = false }) {
  const memoire = `contretemps.docs.endroit.${ecoleId}.${compteEnCours() ?? ''}`
  return <Explorer key={memoire} orgId={ecoleId} memoire={memoire} assistant={assistant} />
}
