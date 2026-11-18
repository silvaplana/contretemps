import { useEffect, useRef, useState } from 'react'
import Icon from '../../components/Icon.jsx'
import * as sessionApi from '../../api/session.js'
import * as modulesApi from '../../api/modules.js'
import { MODULES } from '../../app/modules.js'
import { ouvrirOnglet } from '../../app/connexions.js'
import { isOwner, isSuperuser, isTresorier } from '../../data/roles.js'
import * as financesApi from '../../modules/finances/api.js'
import { demanderBanque } from '../../modules/finances/navigation.js'

// Admin › École › Connexions (spec/core.md, « Connexions », Seb 18/11/2026,
// maquette https://claude.ai/artifact/KcVhuSbXUJwP1C6FaPQK7p) : toutes les
// connexions à identifiants des modules allumés, une ligne chacune (l'écran
// du module, `connection` dans son module.js). Super User et Administrateur
// principal seulement ; les comptes en banque, seulement avec l'Accès au
// Financier en plus. La pastille compte ce qui reste à connecter.

// Comptes en banque : l'écran reste dans Financier › Comptes (le trésorier
// y connecte aussi la banque) ; « Voir » / « Connecter » l'y ouvre.
const BANQUE = {
  key: 'finances',
  label: 'Comptes en banque',
  connecte: () => financesApi.banque().then((s) => Boolean(s.connected)),
}

function LigneBanque() {
  const [statut, setStatut] = useState(null)
  useEffect(() => {
    financesApi.banque().then(setStatut, () => setStatut(null))
  }, [])
  // Refusé (pas trésorier pour le serveur) ou hors ligne : pas de ligne.
  if (!statut) return null
  const petit = !statut.configured
    ? 'Pas configuré sur le serveur'
    : !statut.bank
      ? 'Pas encore connecté'
      : statut.connected
        ? `Connecté : ${statut.bank}`
        : `${statut.bank} : accès expiré`
  return (
    <div className="connexions__ligne fonctionnalites__nom">
      <span>{BANQUE.label}</span>
      <small className="helloasso__etat">{petit}</small>
      {statut.configured && (
        <button
          type="button"
          className="helloasso__lien"
          onClick={() => {
            sessionApi.sauvegarderEcran('financier', 'comptes')
            demanderBanque()
            ouvrirOnglet('financier')
          }}
        >
          {statut.connected ? 'Voir' : 'Connecter'}
        </button>
      )}
    </div>
  )
}

export default function ConnexionsSection({ ecole, activeUser, modules, onModulesChange }) {
  const [ouvert, setOuvert] = useState(() => sessionApi.lireEcran('connexions') === 'ouvrir')
  const [aConnecter, setAConnecter] = useState(0)
  const peutVoir = isOwner(activeUser) || isSuperuser(activeUser)
  const allume = (key) => modules.some((m) => m.key === key && m.enabled)
  // Une ligne déjà montrée reste jusqu'à la sortie de l'écran : « Déconnecter »
  // de HelloAsso éteint le module, et son « Annuler » doit rester à portée.
  const montrees = useRef(new Set())
  const lignes = MODULES.filter((m) => m.connection && (allume(m.key) || montrees.current.has(m.key)))
  lignes.forEach((m) => montrees.current.add(m.key))
  const banque = allume('finances') && isTresorier(activeUser)

  useEffect(() => {
    sessionApi.sauvegarderEcran('connexions', '')
  }, [])

  // Recompté à l'ouverture et à la fermeture du volet.
  const cles = lignes.map((m) => m.key).join(',')
  useEffect(() => {
    if (!peutVoir) return
    let annule = false
    const etats = [...lignes.map((m) => m.connection), ...(banque ? [BANQUE] : [])].map((c) =>
      c.connecte(ecole.id).catch(() => true),
    )
    Promise.all(etats).then((oks) => {
      if (!annule) setAConnecter(oks.filter((ok) => !ok).length)
    })
    return () => {
      annule = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ecole.id, cles, banque, ouvert, peutVoir])

  if (!peutVoir) return null

  async function allumer(key, enabled) {
    onModulesChange(await modulesApi.changer(ecole.id, key, enabled))
  }

  return (
    <section className="connexions">
      <h3 className="section-label">
        <button
          type="button"
          className="section-label__depliant"
          aria-expanded={ouvert}
          onClick={() => setOuvert((o) => !o)}
        >
          <Icon name={ouvert ? 'chevronDown' : 'chevronRight'} size={14} />
          Connexions
          {aConnecter > 0 && <span className="connexions__pastille">{aConnecter}</span>}
        </button>
      </h3>
      {ouvert && (
        <div className="connexions__liste">
          <p className="muted connexions__aide">Les identifiants des services que l’école utilise.</p>
          {lignes.map((m) => {
            const { label, Reglages } = m.connection
            return (
              <div key={m.key} className="connexions__ligne fonctionnalites__nom">
                <span>{label}</span>
                <Reglages ecole={ecole} enabled={allume(m.key)} onEnabledChange={(on) => allumer(m.key, on)} />
              </div>
            )
          })}
          {banque && <LigneBanque />}
          {lignes.length === 0 && !banque && (
            <p className="muted connexions__aide">Aucun module allumé ne demande de connexion.</p>
          )}
        </div>
      )}
    </section>
  )
}
