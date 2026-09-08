// Monogramme "Ct" (voir spec/SPEC.md 5.1 et images/login.png) : un fin arc
// clair dépasse derrière le cercle plein orange, en haut à gauche, qui
// contient un "t" italique. L'arc doit être d'une couleur DISTINCTE du fond
// de page (--bg) pour rester visible dessus — c'est --card-bg (un ivoire
// légèrement plus clair) qui joue ce rôle, pas --bg lui-même.

// ⚠️ Essai en cours (voir data/logo contretemps.jpg, fourni par
// l'utilisateur) : bascule vers un vrai logo photo à la place du "Ct" —
// grand sur Login, petit dans les en-têtes. Passer à `false` pour revenir
// au "Ct" ci-dessous, gardé intact exprès (rien n'est décidé encore).
const AFFICHER_LOGO_PHOTO = true
const BASE_URL = import.meta.env.BASE_URL

export default function Logo({ size = 40 }) {
  if (AFFICHER_LOGO_PHOTO) {
    return (
      <img
        src={`${BASE_URL}images/logo-contretemps.jpg`}
        width={size}
        height={size}
        alt="Logo Contretemps"
        style={{ borderRadius: 8, objectFit: 'cover' }}
      />
    )
  }

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
