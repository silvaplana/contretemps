// Pastille colorée (statut paiement, présence, badge cours...).
// `tone` choisit la couleur : 'neutral' (défaut), 'success', 'warning', 'danger'.
export default function Badge({ children, tone = 'neutral', className = '' }) {
  return <span className={`badge badge--${tone} ${className}`}>{children}</span>
}
