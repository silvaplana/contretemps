// Monogramme "Ct" (voir spec/SPEC.md 5.1 et images/login.png) : un fin arc
// clair dépasse derrière le cercle plein orange, en haut à gauche, qui
// contient un "t" italique. L'arc doit être d'une couleur DISTINCTE du fond
// de page (--bg) pour rester visible dessus — c'est --card-bg (un ivoire
// légèrement plus clair) qui joue ce rôle, pas --bg lui-même.
export default function Logo({ size = 40 }) {
  return (
    <svg viewBox="0 0 100 100" width={size} height={size} aria-hidden="true">
      <path
        d="M78 22a34 34 0 1 0 8 21"
        fill="none"
        stroke="var(--card-bg)"
        strokeWidth="6"
        strokeLinecap="round"
      />
      <circle cx="58" cy="55" r="30" fill="var(--accent)" />
      <text
        x="58"
        y="68"
        textAnchor="middle"
        fontStyle="italic"
        fontFamily="Georgia, 'Times New Roman', serif"
        fontSize="34"
        fill="var(--card-bg)"
      >
        t
      </text>
    </svg>
  )
}
