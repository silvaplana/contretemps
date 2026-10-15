import Explorer from '../modules/documents/Explorer.jsx'

// Onglet Docs : dossiers et fichiers (Public, Privé, Personnel), avec leurs
// droits. Tout le code est dans modules/documents/ (futur module d'AppBase,
// voir backend/src/documents/), branché ici sur l'école affichée.
export default function DocsScreen({ ecoleId }) {
  return <Explorer key={ecoleId} orgId={ecoleId} />
}
