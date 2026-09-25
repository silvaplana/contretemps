// Module "Docs" — PROTOTYPE, frontend seulement (demande utilisateur du
// 2026-09-25) : contenus d'exemple inventés, aucun appel au serveur. Un
// document = { id, titre, sousTitre, date, sections: [{ titre?, paragraphes?, liste? }] }.
// Les noms de personnes réelles sont volontairement évités dans les
// contenus inventés (fonctions : "la présidente", "le trésorier"...).

export const DOCUMENTS_PUBLICS = [
  {
    id: 'reglement-interieur',
    titre: 'Règlement intérieur',
    sousTitre: 'École de danse Contretemps',
    date: '2026-09-01',
    sections: [
      {
        titre: 'Article 1 — Adhésion',
        paragraphes: [
          "L'inscription à un cours vaut adhésion à l'association pour la saison en cours. Elle n'est définitive qu'une fois le dossier complet (fiche d'inscription, certificat médical, règlement de la cotisation).",
        ],
      },
      {
        titre: 'Article 2 — Cotisation',
        paragraphes: [
          "La cotisation est annuelle. Elle peut être réglée en une fois ou en trois fois (octobre, janvier, avril). Aucun remboursement n'est dû en cas d'abandon en cours d'année, sauf raison médicale justifiée.",
        ],
      },
      {
        titre: 'Article 3 — Assiduité et ponctualité',
        paragraphes: [
          'Les élèves arrivent 5 minutes avant le début du cours. Toute absence prévisible est signalée au professeur par la messagerie de l’application.',
          "Les parents des élèves mineurs s'assurent de la présence du professeur avant de laisser leur enfant.",
        ],
      },
      {
        titre: 'Article 4 — Tenue',
        liste: [
          'Tenue adaptée au cours (justaucorps, pantalon souple ou tenue de street selon la discipline).',
          'Cheveux attachés, bijoux retirés.',
          'Chaussures de ville interdites dans les salles.',
        ],
      },
      {
        titre: 'Article 5 — Respect des lieux et des personnes',
        paragraphes: [
          "Chacun respecte les professeurs, les autres élèves et le matériel. Les vestiaires sont laissés propres. L'association décline toute responsabilité en cas de perte ou de vol.",
        ],
      },
      {
        titre: 'Article 6 — Droit à l’image',
        paragraphes: [
          "Des photos et vidéos peuvent être prises pendant les cours et le spectacle, pour un usage interne à l'école. Tout refus est à signaler par écrit au bureau de l'association.",
        ],
      },
      {
        titre: 'Article 7 — Spectacle de fin d’année',
        paragraphes: [
          'La participation au spectacle est vivement encouragée. Les costumes sont fournis par l’école et rendus après la dernière représentation.',
        ],
      },
    ],
  },
]

export const DOCUMENTS_PRIVES = [
  {
    id: 'pv-ag-nov-2026',
    titre: 'PV AG nov 2026',
    sousTitre: 'Procès-verbal de l’assemblée générale ordinaire',
    date: '2026-11-21',
    sections: [
      {
        paragraphes: [
          "L'assemblée générale ordinaire de l'association Contretemps s'est tenue le samedi 21 novembre 2026 à 14 h, dans la grande salle de l'école. 58 membres étaient présents ou représentés sur 113 : le quorum étant atteint, l'assemblée a pu valablement délibérer.",
        ],
      },
      {
        titre: 'Ordre du jour',
        liste: [
          'Rapport moral de la présidente',
          'Rapport financier du trésorier',
          'Projets de la saison 2026-2027',
          'Élection du bureau',
          'Questions diverses',
        ],
      },
      {
        titre: '1. Rapport moral',
        paragraphes: [
          'La présidente rappelle la hausse des effectifs (113 élèves, +12 %), l’ouverture d’un cours de Contempo Adulte et la réussite du spectacle de juin. Le rapport moral est approuvé à l’unanimité.',
        ],
      },
      {
        titre: '2. Rapport financier',
        paragraphes: [
          'Le trésorier présente un exercice à l’équilibre : 41 200 € de recettes pour 40 650 € de dépenses. Le rapport financier est approuvé à l’unanimité moins 2 abstentions.',
        ],
      },
      {
        titre: '3. Projets',
        liste: [
          'Achat d’un nouveau parquet pour la salle 2.',
          'Stage de danse contemporaine pendant les vacances de février.',
          'Spectacle de fin d’année le 20 juin 2027.',
        ],
      },
      {
        titre: '4. Élection du bureau',
        paragraphes: ['Le bureau sortant est réélu à l’unanimité : présidente, trésorier, secrétaire.'],
      },
      {
        titre: '5. Questions diverses',
        paragraphes: [
          'Plusieurs familles demandent un créneau supplémentaire en Éveil ; le bureau étudiera la question. La séance est levée à 16 h 10.',
        ],
      },
    ],
  },
]

function dateDuJour() {
  return new Date().toISOString().slice(0, 10)
}

function nomComplet(user) {
  return [user?.prenom, user?.nom].filter(Boolean).join(' ') || '…………………………'
}

// Documents "Personnel" : propres à la personne connectée.
export function documentsPersonnels(user) {
  return [
    {
      id: 'inscription-association',
      titre: 'Inscription à l’association',
      sousTitre: `Saison 2026-2027 — ${nomComplet(user)}`,
      date: '2026-09-02',
      sections: [
        {
          paragraphes: [
            `${nomComplet(user)} est inscrit(e) comme membre de l'association Contretemps pour la saison 2026-2027.`,
          ],
        },
        {
          titre: 'Récapitulatif',
          liste: [
            'Adhésion à l’association : 20 €',
            'Cotisation annuelle des cours : réglée en 3 fois',
            'Certificat médical : fourni',
            'Autorisation de droit à l’image : accordée',
          ],
        },
        {
          paragraphes: [
            "En adhérant, le membre reconnaît avoir pris connaissance du règlement intérieur (onglet Public) et s'engage à le respecter.",
          ],
        },
      ],
    },
    {
      id: 'exemple-procuration',
      titre: 'Exemple de procuration',
      sousTitre: 'Modèle pour l’assemblée générale',
      date: '2026-10-15',
      sections: [
        {
          paragraphes: [
            'Je soussigné(e) Marie Exemple, membre de l’association Contretemps, donne pouvoir à Paul Modèle, membre de l’association, pour me représenter à l’assemblée générale du 21 novembre 2026 et prendre part en mon nom à toutes les délibérations et à tous les votes.',
            'Fait à …………………, le 15 octobre 2026.',
            'Signature précédée de la mention « Bon pour pouvoir ».',
          ],
        },
        {
          titre: 'Rappel',
          liste: [
            'Le mandataire doit être lui-même membre de l’association.',
            'Un même membre ne peut détenir plus de 2 procurations.',
          ],
        },
      ],
    },
  ]
}

// "Générer une procuration" (voir DocsScreen.jsx).
export function genererProcuration({ mandant, mandataire, dateAg, lieu }) {
  const dateAgLisible = new Date(`${dateAg}T12:00:00`).toLocaleDateString('fr-FR', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })
  const aujourdhui = dateDuJour()
  const aujourdhuiLisible = new Date(`${aujourdhui}T12:00:00`).toLocaleDateString('fr-FR', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })
  return {
    id: `procuration-${Date.now()}`,
    titre: `Procuration AG du ${dateAgLisible}`,
    sousTitre: `${mandant} → ${mandataire}`,
    date: aujourdhui,
    sections: [
      { titre: 'Procuration' },
      {
        paragraphes: [
          `Je soussigné(e) ${mandant}, membre de l'association Contretemps, donne pouvoir à ${mandataire}, membre de l'association, pour me représenter à l'assemblée générale du ${dateAgLisible} et prendre part en mon nom à toutes les délibérations et à tous les votes.`,
          `Fait à ${lieu}, le ${aujourdhuiLisible}.`,
          'Signature précédée de la mention « Bon pour pouvoir » :',
        ],
      },
    ],
    signature: true,
  }
}
