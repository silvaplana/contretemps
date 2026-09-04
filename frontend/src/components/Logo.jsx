// Monogramme "Ct" (voir spec/SPEC.md 5.1 et images/login.png) : un grand
// arc (le "C") entoure un cercle plein orange contenant un "t" italique.
export default function Logo({ size = 40 }) {
  return (
    <svg viewBox="0 0 100 100" width={size} height={size} aria-hidden="true">
      <path
        d="M78 22a34 34 0 1 0 8 21"
        fill="none"
        stroke="var(--bg)"
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
        fill="var(--bg)"
      >
        t
      </text>
    </svg>
  )
}
