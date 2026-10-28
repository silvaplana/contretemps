import './exemple.css'

// Bande « Exemple » des écrans de la spec §8 montrés avant d'être codés
// (exemple/donnees.js) : rien n'est enregistré.
export default function BandeExemple({ children }) {
  return (
    <p className="fin-ex-bande">
      <strong>Exemple</strong>
      <span>{children ?? 'Écran à venir, avec les chiffres de 2024-25. Rien n’est enregistré.'}</span>
    </p>
  )
}
