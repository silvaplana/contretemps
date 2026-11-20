import './finances.css'

// Financier › ⋯ › « Aide en ligne comptabilité » (Seb, 20/11/2026 ; maquette
// https://claude.ai/artifact/CZxrkQGxWLxEwepgf8jkSW) : une page fixe, courte,
// pour un public qui connaît la compta. ← revient au sous-onglet d'où l'on vient.

// Une case d'un schéma d'états : `etat` = 'afaire' (orange), 'encours' ou 'fini' (vert).
function Etat({ x, y, w, etat, children }) {
  return (
    <g className={`fin-aide__etat fin-aide__etat--${etat}`}>
      <rect x={x} y={y} width={w} height="40" rx="8" />
      <text x={x + w / 2} y={y + 25} textAnchor="middle">
        {children}
      </text>
    </g>
  )
}

function Fleche({ d }) {
  return <path className="fin-aide__fleche" d={d} markerEnd="url(#fin-aide-fleche)" />
}

function Mot({ x, y, children, centre = false }) {
  return (
    <text className="fin-aide__mot" x={x} y={y} textAnchor={centre ? 'middle' : 'start'}>
      {children}
    </text>
  )
}

const pointe = (
  <defs>
    <marker id="fin-aide-fleche" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M0 0L10 5L0 10z" />
    </marker>
  </defs>
)

function SchemaTransaction() {
  return (
    <svg className="fin-aide__schema" viewBox="0 0 350 235" role="img" aria-label="États d'une transaction">
      {pointe}
      <Fleche d="M140 48 L110 94" />
      <Fleche d="M230 48 V182" />
      <Fleche d="M105 136 L140 182" />
      <Etat x={100} y={8} w={150} etat="afaire">À catégoriser</Etat>
      <Etat x={10} y={96} w={190} etat="encours">Justificatif manquant</Etat>
      <Etat x={100} y={184} w={150} etat="fini">Justifiée</Etat>
      <Mot x={130} y={76}>compte posé</Mot>
      <Mot x={236} y={110}>pièce rattachée</Mot>
      <Mot x={10} y={160}>pièce ou</Mot>
      <Mot x={10} y={176}>sans facture</Mot>
    </svg>
  )
}

function SchemaPiece() {
  return (
    <svg className="fin-aide__schema" viewBox="0 0 350 320" role="img" aria-label="États d'une pièce">
      {pointe}
      <Fleche d="M140 48 L120 94" />
      <Fleche d="M100 136 L100 182" />
      <Fleche d="M100 28 H20 V182" />
      <Fleche d="M250 28 H270 V182" />
      <Fleche d="M97 224 L140 270" />
      <Fleche d="M270 224 L210 270" />
      <Etat x={100} y={8} w={150} etat="afaire">À valider</Etat>
      <Etat x={40} y={96} w={140} etat="afaire">À catégoriser</Etat>
      <Etat x={10} y={184} w={175} etat="encours">À payer / À encaisser</Etat>
      <Etat x={200} y={184} w={140} etat="encours">À rapprocher</Etat>
      <Etat x={95} y={272} w={160} etat="fini">Payée / Encaissée</Etat>
      <Mot x={136} y={76}>sans compte</Mot>
      <Mot x={106} y={166}>compte choisi</Mot>
      <Mot x={24} y={66}>validée</Mot>
      <Mot x={278} y={100}>payée</Mot>
      <Mot x={278} y={116}>hors appli</Mot>
      <Mot x={175} y={254} centre>rattachée</Mot>
    </svg>
  )
}

export default function AideComptabilite({ onClose }) {
  return (
    <div className="fin-aide">
      <button type="button" className="btn btn--link fin-releves__retour" onClick={onClose}>
        ← Financier
      </button>
      <h2>Aide en ligne comptabilité</h2>
      <p>
        Les transactions arrivent par les relevés bancaires ; les pièces (factures, notes de frais, notes
        d'honoraires…) sont photographiées ou déposées par les membres, ou importées automatiquement (drive, boîte
        mail, HelloAsso) ; chaque pièce est rattachée à sa transaction et lui impose son compte ; les comptes
        additionnés font la Balance, d'où sortent tous les documents du bilan.
      </p>

      <h3>Définitions</h3>
      <p>
        <b>Pièce</b> : justificatif d'une dépense ou d'une recette.
      </p>
      <ul className="fin-aide__exemples">
        <li>Achat : ex. facture Amazon</li>
        <li>Honoraires : ex. note d'un professeur</li>
        <li>Note de frais : ex. ticket avancé par un membre</li>
        <li>Vente : ex. remise de chèques des cotisations</li>
        <li>Bulletin de salaire : ex. paie d'un salarié</li>
      </ul>
      <p>
        <b>Transaction</b> : ligne du relevé bancaire ; elle fait foi pour le montant.
      </p>
      <p>
        <b>Compte</b> : compte du plan comptable des associations, ex. « 613 Location de salle ». Plan de base
        fourni à la création : extrait simplifié du plan comptable des associations (règlement ANC 2018-06), 25
        comptes de dépenses, recettes et tiers, à compléter. Quand aucun compte ne convient, l'appli en propose un
        à la lecture d'une pièce (« Créer ce compte ») ; rien n'est créé sans votre accord.
      </p>
      <p>
        <b>Classe</b> : premier chiffre du numéro de compte. 1 Capitaux · 2 Immobilisations · 3 Stocks · 4 Tiers
        · 5 Banques et caisse · 6 Charges · 7 Produits · 8 Contributions volontaires en nature. Les classes 6 et 7
        font le compte de résultat, les classes 1 à 5 le bilan.
      </p>

      <h3>Processus</h3>
      <ul>
        <li>
          <b>Rattacher</b> : mettre une pièce en face de la transaction qui l'a payée. Ce n'est pas du un pour un :
          plusieurs pièces pour une transaction (un virement qui paie trois factures), ou une pièce pour plusieurs
          transactions (paiement en plusieurs fois, via « Reste dû »).
        </li>
        <li>
          <b>Rapprocher</b> : l'écran Pièces › Rapprocher, qui propose d'un coup tous les rattachements en attente
          de la saison.
        </li>
        <li>Le compte de la pièce est imposé à la transaction.</li>
        <li>
          La Balance prend les transactions : le compte de chacune est celui de ses pièces rattachées, sinon celui
          posé sur la transaction.
        </li>
        <li>Écart de compte pièce / transaction : réglé dans Bilan › Préparer, étape 3.</li>
        <li>Une transaction peut être classée sans pièce (« Justifier sans facture »).</li>
      </ul>

      <h3>Documents du bilan</h3>
      <p className="fin-aide__groupe">Minimum</p>
      <ul>
        <li>
          <b>Compte de résultat</b> : recettes et dépenses de la saison par compte, et le résultat.
        </li>
        <li>
          <b>Bilan</b> : ce que l'association possède et doit au dernier jour de la saison.
        </li>
        <li>
          <b>Rapport financier</b> : le commentaire des comptes lu à l'AG.
        </li>
        <li>
          <b>Budget prévisionnel</b> : les charges et produits prévus pour la saison suivante, par compte, votés
          par l'AG. À remplir au bilan (réalisé de l'année en face) ; l'onglet Prévisionnel, lui, prévoit le solde
          des comptes en banque jusqu'à la fin de la saison.
        </li>
      </ul>
      <p className="fin-aide__groupe">En appui</p>
      <ul>
        <li>
          <b>Balance</b> : total et solde de chaque compte.
        </li>
        <li>
          <b>Grand-livre</b> : toutes les écritures, compte par compte.
        </li>
        <li>
          <b>Annexe</b> : les explications qui éclairent les chiffres.
        </li>
        <li>
          <b>FEC</b> : fichier des écritures au format de l'administration fiscale.
        </li>
      </ul>
      <p>
        À tout moment : la Balance, le Grand-livre et le Compte de résultat (puces de Comptes, le Compte de
        résultat comparé à l'an dernier) ; les autres se produisent au bilan, dans Bilan › Préparer, étape 6.
      </p>

      <h3>Point de départ</h3>
      <p>
        Chaque saison repart des soldes de fin de la saison précédente pour les comptes de bilan (classes 1 à 5) ;
        les comptes de charges et de produits (6 et 7) repartent à zéro. Ces soldes viennent de la clôture faite
        dans l'appli, sinon de la Balance de l'an dernier (le PDF dans Docs › Financier de la saison précédente) ;
        les comptes en banque sont vérifiés avec les relevés (Bilan › Préparer, étape 2 « Reprendre les soldes de
        départ »).
      </p>

      <h3>États d'une transaction</h3>
      <p>Une transaction arrive par le relevé « À catégoriser » ; elle reçoit un compte, puis une pièce ou une justification.</p>
      <SchemaTransaction />
      <p>« Justifiée » seulement si les pièces font le montant de la transaction ; sinon « Justificatif manquant · reste X € ».</p>
      <p>Seul « À catégoriser » bloque la clôture.</p>
      <p>
        La catégorisation peut être automatique (règle ou habitude) : le compte posé est marqué « auto »,
        modifiable, et se valide en lot dans Bilan › Préparer, étape 3.
      </p>

      <h3>États d'une pièce</h3>
      <p>Une pièce arrive « À valider » et se termine « Payée » ou « Encaissée » quand elle est rattachée à sa transaction.</p>
      <SchemaPiece />
    </div>
  )
}
