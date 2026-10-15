import { useEffect, useRef, useState } from 'react'
import { mettreAJour, POLICES, urlFichier, urlLogo, urlNomImage } from '../../api/apparence.js'
import * as personnalisationApi from '../../api/personnalisation.js'
import Icon from '../../components/Icon.jsx'
import Modal from '../../components/Modal.jsx'
import { isOwner, isSuperuser } from '../../data/roles.js'
import { DOMAINE_ECOLES, normaliserAdresse } from '../../utils/adresseEcole.js'

const NOM_CONSEILLE = 12
const LIBELLE_DETOURAGE = { aucun: 'Aucun', simple: 'Simple', ia: 'Par IA' }

// Volet « Personnalisation de l'application » (Admin > École, spec §2.7 et
// §5.1.1 ; maquette validée : spec/maquettes/personnalisation-ecole.html).
// Deux aperçus en direct (page de connexion, écran d'accueil du téléphone),
// puis les champs. Tout admin peut tout modifier, sauf l'adresse web
// (Owners). Rien n'est appliqué à l'appli avant « Enregistrer », sauf les
// images, validées dans leur propre fenêtre.
export default function PersonnalisationSection({ ecole, activeUser }) {
  const [ouvert, setOuvert] = useState(false)
  const [enPlace, setEnPlace] = useState(null) // ce qui est enregistré
  const [champs, setChamps] = useState(null) // ce qui est en cours de saisie
  const [adresse, setAdresse] = useState('')
  const [dispo, setDispo] = useState(null)
  const [brouillon, setBrouillon] = useState(null) // image en attente de validation
  const [confirmerDefaut, setConfirmerDefaut] = useState(false)
  const [message, setMessage] = useState('')
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)
  const choixLogo = useRef(null)
  const choixNom = useRef(null)
  const peutChangerAdresse = isOwner(activeUser) || isSuperuser(activeUser)

  function reprendre(vue) {
    setEnPlace(vue)
    setChamps({
      nomAppli: vue.nomAppli,
      nomMode: vue.nomMode,
      slogan: vue.slogan,
      couleurFond: vue.couleurFond,
      couleurTexte: vue.couleurTexte,
      couleurAccent: vue.couleurAccent,
      police: vue.police ?? '',
    })
    setAdresse(vue.sousDomaine)
  }

  useEffect(() => {
    if (!ouvert || enPlace) return undefined
    let annule = false
    personnalisationApi
      .obtenir(ecole.id)
      .then((vue) => !annule && reprendre(vue))
      .catch((err) => !annule && setErreur(err.message))
    return () => {
      annule = true
    }
  }, [ouvert, enPlace, ecole.id])

  // Disponibilité de l'adresse pendant la frappe (spec §2.7).
  useEffect(() => {
    if (!enPlace || adresse === enPlace.sousDomaine) {
      setDispo(null)
      return undefined
    }
    const minuteur = setTimeout(() => {
      personnalisationApi
        .disponibilite(adresse || '-', ecole.id)
        .then(setDispo)
        .catch(() => setDispo(null))
    }, 300)
    return () => clearTimeout(minuteur)
  }, [adresse, enPlace, ecole.id])

  useEffect(() => {
    if (!message) return undefined
    const minuteur = setTimeout(() => setMessage(''), 5000)
    return () => clearTimeout(minuteur)
  }, [message])

  function changer(champ, valeur) {
    setChamps((c) => ({ ...c, [champ]: valeur }))
  }

  async function tenter(action) {
    setErreur('')
    setEnCours(true)
    try {
      await action()
    } catch (err) {
      setErreur(err.message)
    } finally {
      setEnCours(false)
    }
  }

  function appliquer(vue) {
    reprendre(vue)
    mettreAJour(vue)
  }

  const adresseChangee = enPlace && adresse !== enPlace.sousDomaine

  function enregistrer() {
    if (adresseChangee && dispo && !dispo.disponible) {
      setErreur('Choisissez une adresse disponible.')
      return
    }
    if (
      adresseChangee &&
      !window.confirm(
        'Changer l’adresse oblige les élèves à réinstaller l’appli. L’ancienne adresse redirigera vers la nouvelle pendant 6 mois. Continuer ?',
      )
    ) {
      return
    }
    tenter(async () => {
      let vue = await personnalisationApi.modifier(ecole.id, champs)
      if (adresseChangee) vue = await personnalisationApi.changerAdresse(ecole.id, adresse)
      appliquer(vue)
      setMessage('Personnalisation enregistrée.')
    })
  }

  function revenirAuDefaut() {
    tenter(async () => {
      appliquer(await personnalisationApi.revenirAuDefaut(ecole.id))
      setConfirmerDefaut(false)
      setMessage('Apparence par défaut remise.')
    })
  }

  function envoyer(type, fichier) {
    if (!fichier) return
    tenter(async () => setBrouillon(await personnalisationApi.envoyerImage(ecole.id, type, fichier)))
  }

  function redetourer(type, detourage) {
    tenter(async () => setBrouillon(await personnalisationApi.choisirDetourage(ecole.id, type, detourage)))
  }

  function validerImage(prendreLaCouleur) {
    tenter(async () => {
      const type = brouillon.type
      const couleur = brouillon.couleurFondProposee
      let vue = await personnalisationApi.validerImage(ecole.id, type)
      if (prendreLaCouleur && couleur) {
        vue = await personnalisationApi.modifier(ecole.id, { ...champs, nomMode: vue.nomMode, couleurFond: couleur })
      }
      // Les champs en cours de saisie restent, sauf ce que la validation change.
      setEnPlace(vue)
      setChamps((c) => ({ ...c, nomMode: vue.nomMode, couleurFond: vue.couleurFond }))
      mettreAJour(vue)
      setBrouillon(null)
      setMessage(type === 'logo' ? 'Nouveau logo enregistré.' : 'Nom en image enregistré.')
    })
  }

  function annulerImage() {
    personnalisationApi.annulerImage(ecole.id, brouillon.type)
    setBrouillon(null)
  }

  // L'aperçu suit les champs en cours de saisie, sur les images enregistrées.
  const apercu = enPlace && champs ? { ...enPlace, ...champs, police: champs.police || null } : null
  const famille = (POLICES.find((p) => p.cle === (champs?.police ?? '')) ?? POLICES[0]).famille
  const contrasteFaible = champs && contraste(champs.couleurTexte, champs.couleurFond) < 4.5

  return (
    <section className="admin-personnalisation">
      <h3 className="section-label">
        <button
          type="button"
          className="section-label__depliant"
          aria-expanded={ouvert}
          onClick={() => setOuvert((o) => !o)}
        >
          <Icon name={ouvert ? 'chevronDown' : 'chevronRight'} size={14} />
          Personnalisation de l’application
        </button>
      </h3>

      {ouvert && !apercu && <p className="muted">{erreur || 'Chargement…'}</p>}

      {ouvert && apercu && (
        <div className="perso">
          <p className="perso__legende">
            <strong>Aperçu de la page de connexion</strong> (se met à jour en direct)
          </p>
          <div
            className="perso__connexion"
            style={{ background: apercu.couleurFond, color: apercu.couleurTexte, fontFamily: famille }}
          >
            <img src={urlLogo(apercu)} alt="" className="perso__connexion-logo" />
            {apercu.nomMode === 'image' && urlNomImage(apercu) ? (
              <img src={urlNomImage(apercu)} alt={apercu.nom} className="perso__connexion-nom-image" />
            ) : (
              <strong className="perso__connexion-nom">{apercu.nom}</strong>
            )}
            <span>{apercu.slogan}</span>
            <span className="perso__connexion-bouton" style={{ background: apercu.couleurAccent }}>
              Se connecter
            </span>
          </div>

          <p className="perso__legende">
            <strong>Aperçu de l’écran d’accueil du téléphone</strong> : une fois l’appli installée,
            l’icône est le logo de l’école et le nom est celui de l’école.
          </p>
          <div className="perso__accueil">
            {['Météo', null, 'Photos', 'Messages'].map((nom, i) =>
              nom === null ? (
                <div key={i} className="perso__appli">
                  <span className="perso__icone" style={{ background: apercu.couleurFond }}>
                    <img src={urlLogo(apercu)} alt="" />
                  </span>
                  <small>{apercu.nomAppli}</small>
                </div>
              ) : (
                <div key={i} className="perso__appli perso__appli--autre">
                  <span className="perso__icone" />
                  <small>{nom}</small>
                </div>
              ),
            )}
          </div>

          <label htmlFor="perso-adresse" className="perso__label">
            Adresse web de l’appli
          </label>
          <div className={`perso__adresse ${peutChangerAdresse ? '' : 'perso__adresse--fixe'}`}>
            <span>https://</span>
            <input
              id="perso-adresse"
              value={adresse}
              disabled={!peutChangerAdresse}
              onChange={(e) => setAdresse(normaliserAdresse(e.target.value))}
            />
            <span>.{DOMAINE_ECOLES}</span>
          </div>
          {adresseChangee && dispo && (
            <p className={dispo.disponible ? 'perso__statut perso__statut--ok' : 'perso__statut perso__statut--ko'}>
              {dispo.disponible
                ? '✓ Disponible'
                : dispo.raison === 'reserve'
                  ? 'Ce nom est réservé.'
                  : dispo.raison === 'pris'
                    ? 'Déjà prise par une autre école.'
                    : 'Lettres minuscules, chiffres et tirets, 3 caractères au moins.'}
              {dispo.proposition && (
                <>
                  {' '}
                  <button type="button" className="btn--link" onClick={() => setAdresse(dispo.proposition)}>
                    Prendre « {dispo.proposition} »
                  </button>
                </>
              )}
            </p>
          )}
          {adresseChangee && (
            <p className="perso__avertissement">
              Changer l’adresse oblige les élèves à réinstaller l’appli. L’ancienne redirigera vers la
              nouvelle pendant 6 mois.
            </p>
          )}
          <p className="muted perso__aide">
            {peutChangerAdresse
              ? 'Lettres minuscules, chiffres et tirets. C’est l’adresse mise dans les mails d’invitation.'
              : 'Seul un administrateur principal peut changer l’adresse.'}
          </p>

          <label htmlFor="perso-nom-appli" className="perso__label">
            Nom sous l’icône du téléphone
          </label>
          <input
            id="perso-nom-appli"
            className="field-input"
            maxLength={30}
            value={champs.nomAppli}
            onChange={(e) => changer('nomAppli', e.target.value)}
          />
          <p className={`perso__compteur ${champs.nomAppli.length > NOM_CONSEILLE ? 'perso__compteur--trop' : ''}`}>
            {champs.nomAppli.length} / {NOM_CONSEILLE} conseillés
            {champs.nomAppli.length > NOM_CONSEILLE && ' : risque d’être coupé sur le téléphone'}
          </p>

          <span className="perso__label">Logo</span>
          <div className="perso__logo">
            <span className="perso__damier">
              <img src={urlLogo(enPlace)} alt="Logo actuel" />
            </span>
            <button type="button" className="btn btn--secondary" disabled={enCours} onClick={() => choixLogo.current?.click()}>
              Changer le logo
            </button>
            <input
              ref={choixLogo}
              type="file"
              accept="image/png,image/jpeg,image/webp,image/svg+xml"
              hidden
              onChange={(e) => {
                envoyer('logo', e.target.files?.[0])
                e.target.value = ''
              }}
            />
          </div>
          {enPlace.logoPersonnalise && (
            <>
              <label htmlFor="perso-detourage" className="perso__sous-label">
                Détourage
              </label>
              <select
                id="perso-detourage"
                className="field-input"
                value=""
                disabled={enCours}
                onChange={(e) => e.target.value && redetourer('logo', e.target.value)}
              >
                <option value="">Refaire le détourage…</option>
                {(enPlace.detouragesDisponibles ?? []).map((d) => (
                  <option key={d} value={d}>
                    {LIBELLE_DETOURAGE[d]}
                  </option>
                ))}
              </select>
            </>
          )}
          <Historique
            ecoleId={ecole.id}
            type="logo"
            version={enPlace.version}
            desactive={enCours}
            onReprendre={(fichier) =>
              tenter(async () => {
                const vue = await personnalisationApi.reprendreImage(ecole.id, 'logo', fichier)
                setEnPlace(vue)
                mettreAJour(vue)
              })
            }
          />
          <p className="muted perso__aide">
            {enPlace.logoPersonnalise
              ? 'Sert aussi d’icône de l’appli installée, posé sur la couleur de fond.'
              : 'Par défaut : le logo actuel de Contretemps. Il sert aussi d’icône de l’appli installée, posé sur la couleur de fond.'}
          </p>

          <span className="perso__label">Nom de l’école</span>
          <div className="segmented perso__segmente">
            {['texte', 'image'].map((mode) => (
              <button
                key={mode}
                type="button"
                className={`segmented__option ${champs.nomMode === mode ? 'is-active' : ''}`}
                onClick={() => {
                  if (mode === 'image' && !enPlace.nomImage) choixNom.current?.click()
                  else changer('nomMode', mode)
                }}
              >
                {mode === 'texte' ? 'Texte' : 'Image'}
              </button>
            ))}
          </div>
          {champs.nomMode === 'image' && enPlace.nomImage && (
            <button type="button" className="btn--link" onClick={() => choixNom.current?.click()}>
              Changer l’image du nom
            </button>
          )}
          <Historique
            ecoleId={ecole.id}
            type="nom"
            version={enPlace.version}
            desactive={enCours}
            onReprendre={(fichier) =>
              tenter(async () => {
                const vue = await personnalisationApi.reprendreImage(ecole.id, 'nom', fichier)
                setEnPlace(vue)
                setChamps((c) => ({ ...c, nomMode: vue.nomMode }))
                mettreAJour(vue)
              })
            }
          />
          <input
            ref={choixNom}
            type="file"
            accept="image/png,image/jpeg,image/webp,image/svg+xml"
            hidden
            onChange={(e) => {
              envoyer('nom', e.target.files?.[0])
              e.target.value = ''
            }}
          />

          <label htmlFor="perso-slogan" className="perso__label">
            Slogan
          </label>
          <input
            id="perso-slogan"
            className="field-input"
            maxLength={80}
            value={champs.slogan}
            onChange={(e) => changer('slogan', e.target.value)}
          />

          <span className="perso__label">Couleurs</span>
          <div className="perso__couleurs">
            {[
              ['couleurFond', 'Fond'],
              ['couleurTexte', 'Texte'],
              ['couleurAccent', 'Accent'],
            ].map(([champ, libelle]) => (
              <label key={champ}>
                {libelle}
                <input type="color" value={champs[champ]} onChange={(e) => changer(champ, e.target.value.toUpperCase())} />
              </label>
            ))}
          </div>
          {contrasteFaible && <p className="perso__avertissement">Le texte est peu lisible sur ce fond.</p>}

          <span className="perso__label">Police</span>
          <div className="perso__polices" role="radiogroup" aria-label="Police">
            {POLICES.map((p) => (
              <button
                key={p.cle || 'systeme'}
                type="button"
                role="radio"
                aria-checked={(champs.police ?? '') === p.cle}
                className={`perso__police ${(champs.police ?? '') === p.cle ? 'is-active' : ''}`}
                onClick={() => changer('police', p.cle)}
              >
                <span style={{ fontFamily: p.famille }}>{apercu.nom}</span>
                <small>{p.nom}</small>
              </button>
            ))}
          </div>

          {erreur && <p className="login-screen__erreur">{erreur}</p>}
          <div className="perso__actions">
            <button type="button" className="btn btn--primary" disabled={enCours} onClick={enregistrer}>
              Enregistrer
            </button>
            <button type="button" className="btn btn--secondary" disabled={enCours} onClick={() => setConfirmerDefaut(true)}>
              Revenir à l’apparence par défaut
            </button>
          </div>
          {confirmerDefaut && (
            <div className="perso__avertissement">
              Remettre le logo, les couleurs et la police d’origine ? L’adresse ne change pas.
              <div className="perso__actions">
                <button type="button" className="btn btn--primary" disabled={enCours} onClick={revenirAuDefaut}>
                  Oui, remettre
                </button>
                <button type="button" className="btn btn--secondary" onClick={() => setConfirmerDefaut(false)}>
                  Annuler
                </button>
              </div>
            </div>
          )}
          <p className="muted perso__aide">Sur iPhone, un nouveau logo ne s’affiche qu’après réinstallation de l’appli.</p>
        </div>
      )}

      {brouillon && (
        <ImageEnAttente
          ecoleId={ecole.id}
          brouillon={brouillon}
          couleurFond={champs?.couleurFond}
          enCours={enCours}
          erreur={erreur}
          onDetourage={(d) => redetourer(brouillon.type, d)}
          onValider={validerImage}
          onAnnuler={annulerImage}
        />
      )}
      {message && (
        <button type="button" className="acces-message" role="status" onClick={() => setMessage('')}>
          {message}
        </button>
      )}
    </section>
  )
}

// Images déjà validées (demande du 2026-10-15) : un clic remet l'une en
// place ; la poubelle supprime celles dont on ne veut plus (jamais celle en
// place). Rien d'affiché tant qu'il n'y a qu'une image ou aucune.
function Historique({ ecoleId, type, version, desactive, onReprendre }) {
  const [images, setImages] = useState([])
  const [erreur, setErreur] = useState('')

  useEffect(() => {
    let annule = false
    personnalisationApi
      .historique(ecoleId, type)
      .then((liste) => !annule && setImages(liste))
      .catch(() => {})
    return () => {
      annule = true
    }
  }, [ecoleId, type, version])

  async function supprimer(fichier) {
    if (!window.confirm('Supprimer définitivement cette image ?')) return
    setErreur('')
    try {
      await personnalisationApi.supprimerImage(ecoleId, type, fichier)
      setImages((liste) => liste.filter((i) => i.fichier !== fichier))
    } catch (err) {
      setErreur(err.message)
    }
  }

  if (images.length < 2 && !images.some((i) => !i.actuelle)) return null
  return (
    <div className="perso__historique">
      <span className="perso__sous-label">{type === 'logo' ? 'Logos précédents' : 'Noms en image précédents'}</span>
      <div className="perso__vignettes">
        {images.map((image) => (
          <div key={image.fichier} className={`perso__vignette ${image.actuelle ? 'is-active' : ''}`}>
            <button
              type="button"
              className="perso__damier"
              disabled={desactive || image.actuelle}
              onClick={() => onReprendre(image.fichier)}
              title={image.actuelle ? 'En place' : 'Remettre cette image'}
              aria-label={image.actuelle ? 'Image en place' : 'Remettre cette image'}
            >
              <img src={urlFichier(ecoleId, image.fichier)} alt="" />
            </button>
            {image.actuelle ? (
              <small>En place</small>
            ) : (
              <button
                type="button"
                className="icon-btn icon-btn--sm icon-btn--danger"
                disabled={desactive}
                onClick={() => supprimer(image.fichier)}
                aria-label="Supprimer cette image"
              >
                <Icon name="trash" size={14} />
              </button>
            )}
          </div>
        ))}
      </div>
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
    </div>
  )
}

// Avant/après sur damier, choix du détourage, puis validation (spec §5.1.1).
function ImageEnAttente({ ecoleId, brouillon, couleurFond, enCours, erreur, onDetourage, onValider, onAnnuler }) {
  const proposee = brouillon.couleurFondProposee
  return (
    <Modal
      title={brouillon.type === 'logo' ? 'Nouveau logo' : 'Nom de l’école en image'}
      onClose={onAnnuler}
      footer={
        <div className="perso__actions">
          <button type="button" className="btn btn--primary" disabled={enCours} onClick={() => onValider(false)}>
            Utiliser cette image
          </button>
          <button type="button" className="btn btn--secondary" disabled={enCours} onClick={onAnnuler}>
            Annuler
          </button>
        </div>
      }
    >
      <div className="perso__avant-apres">
        <figure>
          <span className="perso__damier perso__damier--grand">
            <img src={urlFichier(ecoleId, brouillon.original)} alt="Image envoyée" />
          </span>
          <figcaption>Avant</figcaption>
        </figure>
        <figure>
          <span className="perso__damier perso__damier--grand">
            <img src={urlFichier(ecoleId, brouillon.traite)} alt="Image traitée" />
          </span>
          <figcaption>Après</figcaption>
        </figure>
      </div>
      <label htmlFor="perso-brouillon-detourage">Détourage</label>
      <select
        id="perso-brouillon-detourage"
        className="field-input"
        value={brouillon.detourage}
        disabled={enCours}
        onChange={(e) => onDetourage(e.target.value)}
      >
        {['aucun', 'simple', 'ia'].map((d) => (
          <option key={d} value={d} disabled={!brouillon.detouragesDisponibles.includes(d)}>
            {LIBELLE_DETOURAGE[d]}
          </option>
        ))}
      </select>
      <p className="muted">
        {brouillon.detourage === 'ia'
          ? `Détouré par IA sur le serveur, sans service payant : ${brouillon.coutUsd.toFixed(2)} $.`
          : brouillon.detourage === 'simple'
            ? 'Retire le fond uni autour du dessin. Ne convient pas à une photo : essayez alors « Par IA ».'
            : 'Image gardée telle quelle.'}
        {enCours && ' Traitement en cours…'}
      </p>
      {brouillon.type === 'logo' && proposee && proposee !== couleurFond && (
        <p className="perso__proposition">
          <span className="perso__pastille" style={{ background: proposee }} /> Le fond du logo est {proposee}.{' '}
          <button type="button" className="btn--link" disabled={enCours} onClick={() => onValider(true)}>
            Utiliser cette image et cette couleur de fond
          </button>
        </p>
      )}
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
    </Modal>
  )
}

// Rapport de contraste WCAG entre deux couleurs #RRGGBB.
function contraste(a, b) {
  const lum = (hex) => {
    const [r, g, bl] = [1, 3, 5].map((i) => {
      const c = parseInt(hex.slice(i, i + 2), 16) / 255
      return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
    })
    return 0.2126 * r + 0.7152 * g + 0.0722 * bl
  }
  const [clair, sombre] = [lum(a), lum(b)].sort((x, y) => y - x)
  return (clair + 0.05) / (sombre + 0.05)
}
