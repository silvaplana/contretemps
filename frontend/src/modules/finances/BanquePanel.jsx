// Volet « Se connecter aux comptes en banque » de Comptes (spec/modules/financier.md §3.5) :
// connecter la banque de l'école (choix de la banque et de l'espace), lire
// la banque, choisir les comptes suivis, nommer chaque compte. La connexion
// passe par la banque elle-même ; on revient ensuite sur l'appli
// (?banque=ok, voir Comptes.jsx).
import { useEffect, useState } from 'react'
import * as api from './api.js'

const { dateFr } = api

function heure(iso) {
  const d = new Date(iso)
  return `${dateFr(iso.slice(0, 10))} à ${d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}`
}

function ChoixBanque({ onAnnuler }) {
  const [texte, setTexte] = useState('')
  const [liste, setListe] = useState([])
  const [banque, setBanque] = useState(null)
  const [espace, setEspace] = useState('business')
  const [erreur, setErreur] = useState(null)
  const [enCours, setEnCours] = useState(false)

  useEffect(() => {
    let actif = true
    const t = setTimeout(() => {
      api.banques(texte).then((r) => actif && setListe(r.banks), (e) => actif && setErreur(e.message))
    }, 250)
    return () => {
      actif = false
      clearTimeout(t)
    }
  }, [texte])

  const espaces = banque?.psu_types ?? []

  async function aller() {
    setEnCours(true)
    setErreur(null)
    try {
      const { url } = await api.connecterBanque(banque.name, espaces.includes(espace) ? espace : espaces[0] ?? 'personal')
      // La banque, puis le retour sur l'appli (?banque=ok).
      window.location.assign(url)
    } catch (e) {
      setErreur(e.message)
      setEnCours(false)
    }
  }

  return (
    <div className="fin-banque__choix">
      <label className="fin-banque__label" htmlFor="fin-banque-recherche">Banque de l’école</label>
      <input
        id="fin-banque-recherche"
        className="fin-banque__input"
        placeholder="Nom de la banque (ex. CIC)"
        value={banque ? banque.name : texte}
        onChange={(e) => {
          setBanque(null)
          setTexte(e.target.value)
        }}
      />
      {!banque && (
        <div className="fin-banque__liste">
          {liste.map((b) => (
            <button key={b.name} type="button" onClick={() => setBanque(b)}>
              {b.name}
            </button>
          ))}
        </div>
      )}
      {banque && espaces.length > 1 && (
        <div className="filter-chips" role="group" aria-label="Espace à la banque">
          {[
            ['business', 'Professionnels et associations'],
            ['personal', 'Particuliers'],
          ].map(([cle, libelle]) => (
            <button key={cle} type="button" className={espace === cle ? 'filter-chip filter-chip-active' : 'filter-chip'} aria-pressed={espace === cle} onClick={() => setEspace(cle)}>
              {libelle}
            </button>
          ))}
        </div>
      )}
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
      <div className="fin-banque__boutons">
        <button type="button" className="btn btn--primary" disabled={!banque || enCours} onClick={aller}>
          {enCours ? 'Un instant…' : 'Aller à ma banque'}
        </button>
        {onAnnuler && (
          <button type="button" className="btn btn--link" onClick={onAnnuler}>
            Annuler
          </button>
        )}
      </div>
      <p className="fin-banque__aide">
        Vous vous identifiez chez votre banque (et validez sur votre téléphone), puis vous revenez ici. L’accès dure six mois.
      </p>
    </div>
  )
}

export default function BanquePanel({ accounts, onChanged, onClose }) {
  const [statut, setStatut] = useState(null)
  const [erreur, setErreur] = useState(null)
  const [changer, setChanger] = useState(false)
  const [lecture, setLecture] = useState(false)
  const [message, setMessage] = useState(null)

  useEffect(() => {
    api.banque().then(setStatut, (e) => setErreur(e.message))
  }, [])

  async function actualiser() {
    setLecture(true)
    setMessage(null)
    try {
      const r = await api.actualiserBanque()
      setMessage(r.added ? `${r.added} opération${r.added > 1 ? 's' : ''} nouvelle${r.added > 1 ? 's' : ''}` : 'Rien de nouveau')
      setStatut(await api.banque())
      onChanged()
    } catch (e) {
      setMessage(e.message)
    } finally {
      setLecture(false)
    }
  }

  async function suivre(uid, oui) {
    const uids = statut.accounts.filter((a) => (a.uid === uid ? oui : a.followed)).map((a) => a.uid)
    try {
      setStatut(await api.suivreComptes(uids))
    } catch (e) {
      setMessage(e.message)
    }
  }

  async function renommer(compte, nom) {
    if (!nom.trim() || nom.trim() === compte.name) return
    try {
      await api.renommerCompte(compte.id, nom.trim())
      onChanged()
    } catch (e) {
      setMessage(e.message)
    }
  }

  return (
    <section className="fin-banque account-card" aria-label="Se connecter aux comptes en banque">
      <div className="fin-banque__haut">
        <h3>Se connecter aux comptes en banque</h3>
        <button type="button" className="btn btn--link" onClick={onClose}>
          Fermer
        </button>
      </div>
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
      {statut && !statut.configured && <p>La connexion bancaire n’est pas configurée sur le serveur.</p>}
      {statut?.configured && (!statut.bank || changer) && <ChoixBanque onAnnuler={statut.bank ? () => setChanger(false) : null} />}
      {statut?.configured && statut.bank && !changer && (
        <>
          <p className="fin-banque__etat">
            {statut.connected
              ? `${statut.bank} · accès jusqu’au ${dateFr(statut.validUntil)}`
              : `${statut.bank} · accès expiré : reconnectez la banque`}
            {statut.lastSyncAt && ` · lue le ${heure(statut.lastSyncAt)}`}
          </p>
          {statut.lastError && <p className="login-screen__erreur">{statut.lastError}</p>}
          <div className="fin-banque__boutons">
            {statut.connected && (
              <button type="button" className="btn btn--primary" disabled={lecture} onClick={actualiser}>
                {lecture ? 'Lecture de la banque…' : 'Actualiser'}
              </button>
            )}
            <button type="button" className="btn btn--secondary" onClick={() => setChanger(true)}>
              {statut.connected ? 'Reconnecter ou changer de banque' : 'Reconnecter la banque'}
            </button>
          </div>
          {message && <p className="history-report">{message}</p>}
          {statut.accounts.length > 0 && (
            <>
              <h4>Comptes lus à la banque</h4>
              {statut.accounts.map((a) => (
                <label key={a.uid} className="fin-banque__compte">
                  <input type="checkbox" checked={a.followed} onChange={(e) => suivre(a.uid, e.target.checked)} />
                  <span>
                    {a.name} <span className="account-iban">{a.iban}</span>
                  </span>
                </label>
              ))}
            </>
          )}
        </>
      )}
      {accounts.length > 0 && (
        <>
          <h4>Noms des comptes</h4>
          {accounts.map((c) => (
            <input
              key={`${c.id}-${c.name}`}
              className="fin-banque__input"
              aria-label={`Nom du compte ${c.name}`}
              defaultValue={c.name}
              maxLength={80}
              onBlur={(e) => renommer(c, e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && e.currentTarget.blur()}
            />
          ))}
        </>
      )}
    </section>
  )
}
