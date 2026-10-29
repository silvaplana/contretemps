import QuiPaie from '../notes-frais/QuiPaie.jsx'
import NiveauComptable from './compta/NiveauComptable.jsx'

// Réglages de la ligne Financier de Fonctionnalités : le niveau des
// documents comptables (§8.1) et « Qui paie » (§8.3 bis).
export default function ReglagesFinancier(props) {
  return (
    <>
      <NiveauComptable {...props} />
      <QuiPaie {...props} />
    </>
  )
}
