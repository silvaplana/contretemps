// Données d'exemple (en dur) pour la maquette front-end du rôle Admin.
// Pas d'appel réseau ici : tout vient de ce fichier, en attendant le backend
// (voir spec/SPEC.md section 6 pour le schéma de base visé).

export const currentUser = {
  id: 'admin1',
  type: 'admin',
  nom: 'Petit',
  prenom: 'Valérie',
  email: 'v.petit@contretemps.fr',
  initiales: 'VP',
}

export const professeurs = [
  {
    id: 'p1',
    nom: 'Chevalier',
    prenom: 'Isabelle',
    email: 'i.chevalier@mail.com',
    coursIds: ['c1', 'c2'],
  },
  {
    id: 'p2',
    nom: 'Renard',
    prenom: 'Julien',
    email: 'j.renard@mail.com',
    coursIds: ['c3'],
  },
  {
    id: 'p3',
    nom: 'Moreau',
    prenom: 'Camille',
    email: 'c.moreau@mail.com',
    coursIds: ['c4'],
  },
]

export const cours = [
  {
    id: 'c1',
    nom: 'Jazz niveau moyen',
    jour: 'Mercredi',
    heureDebut: '17h00',
    heureFin: '18h30',
    salle: 'Salle 2',
    professeurId: 'p1',
  },
  {
    id: 'c2',
    nom: 'Jazz niveau avancé',
    jour: 'Mercredi',
    heureDebut: '18h30',
    heureFin: '20h00',
    salle: 'Salle 2',
    professeurId: 'p1',
  },
  {
    id: 'c3',
    nom: 'Eveil 5-7 ans',
    jour: 'Samedi',
    heureDebut: '10h00',
    heureFin: '11h00',
    salle: 'Salle 1',
    professeurId: 'p2',
  },
  {
    id: 'c4',
    nom: 'Contemporain',
    jour: 'Jeudi',
    heureDebut: '19h00',
    heureFin: '20h30',
    salle: 'Salle 1',
    professeurId: 'p3',
  },
]

export const eleves = [
  {
    id: 'e1',
    nom: 'Dubois',
    prenom: 'Marianne',
    coursIds: ['c1'],
    statutPaiement: 'a_jour',
    commentaire: 'Allergie fruits à coque.',
    dateNaissance: '2014-03-12',
    parent: 'Sophie Dubois',
    telephone: '06 12 34 56 78',
    email: 's.dubois@mail.com',
    adresse: '4 rue des Lilas, Le Beausset',
    certificatMedical: true,
  },
  {
    id: 'e2',
    nom: 'Martin',
    prenom: 'Coco',
    coursIds: ['c1'],
    statutPaiement: 'en_attente',
    commentaire: 'Relancer paiement.',
    dateNaissance: '2013-11-02',
    parent: 'Nadia Martin',
    telephone: '06 22 11 09 87',
    email: 'n.martin@mail.com',
    adresse: '12 avenue du Château, Le Beausset',
    certificatMedical: true,
  },
  {
    id: 'e3',
    nom: 'Petit',
    prenom: 'Jojo',
    coursIds: ['c3'],
    statutPaiement: 'a_jour',
    commentaire: '',
    dateNaissance: '2018-06-20',
    parent: 'Karim Petit',
    telephone: '06 45 67 89 10',
    email: 'k.petit@mail.com',
    adresse: '3 chemin des Vignes, Le Beausset',
    certificatMedical: false,
  },
  {
    id: 'e4',
    nom: 'Roux',
    prenom: 'Thomas',
    coursIds: ['c1', 'c2'],
    statutPaiement: 'a_jour',
    commentaire: '',
    dateNaissance: '2011-01-30',
    parent: 'Alice Roux',
    telephone: '06 33 44 55 66',
    email: 'a.roux@mail.com',
    adresse: '8 rue de la Gare, Le Beausset',
    certificatMedical: true,
  },
  {
    id: 'e5',
    nom: 'Blanc',
    prenom: 'Léa',
    coursIds: ['c2'],
    statutPaiement: 'retard',
    commentaire: 'Rappel envoyé le 02/08.',
    dateNaissance: '2010-09-14',
    parent: 'Julie Blanc',
    telephone: '06 55 44 33 22',
    email: 'j.blanc@mail.com',
    adresse: '21 impasse des Oliviers, Le Beausset',
    certificatMedical: true,
  },
  {
    id: 'e6',
    nom: 'Fabre',
    prenom: 'Noa',
    coursIds: ['c3'],
    statutPaiement: 'a_jour',
    commentaire: '',
    dateNaissance: '2017-12-05',
    parent: 'Karim Petit',
    telephone: '06 45 67 89 10',
    email: 'k.petit@mail.com',
    adresse: '3 chemin des Vignes, Le Beausset',
    certificatMedical: true,
  },
  {
    id: 'e7',
    nom: 'Simon',
    prenom: 'Inès',
    coursIds: ['c4'],
    statutPaiement: 'a_jour',
    commentaire: '',
    dateNaissance: '2009-04-18',
    parent: 'Marc Simon',
    telephone: '06 66 77 88 99',
    email: 'm.simon@mail.com',
    adresse: '15 rue Jean Jaurès, Le Beausset',
    certificatMedical: true,
  },
  {
    id: 'e8',
    nom: 'Girard',
    prenom: 'Maël',
    coursIds: ['c4'],
    statutPaiement: 'en_attente',
    commentaire: '',
    dateNaissance: '2008-07-22',
    parent: 'Elodie Girard',
    telephone: '06 77 88 99 00',
    email: 'e.girard@mail.com',
    adresse: '6 place du Marché, Le Beausset',
    certificatMedical: false,
  },
]

export const groupes = [
  {
    id: 'g1',
    nom: 'Jazz niveau moyen',
    membres: [
      { type: 'professeur', id: 'p1' },
      { type: 'cours', id: 'c1' },
    ],
  },
  {
    id: 'g2',
    nom: 'Equipe pédagogique',
    membres: [
      { type: 'admin', id: 'admin1', label: 'Direction' },
      { type: 'professeur', id: 'p1' },
      { type: 'professeur', id: 'p2' },
    ],
  },
  {
    id: 'g3',
    nom: 'Spectacle fin d’année',
    membres: [
      { type: 'admin', id: 'admin1', label: 'Direction' },
      { type: 'cours', id: 'c2' },
      { type: 'cours', id: 'c4' },
    ],
  },
]

// Présences : par cours, une liste de dates et le statut de chaque élève à
// chaque date ('present' | 'absent' | 'retard').
export const presencesParCours = {
  c1: {
    dates: ['03/08', '05/08', '07/08', '10/08', '12/08'],
    parEleve: {
      e1: ['present', 'present', 'absent', 'present', 'retard'],
      e2: ['present', 'present', 'present', 'present', 'present'],
      e4: ['absent', 'present', 'present', 'absent', 'present'],
    },
  },
  c2: {
    dates: ['03/08', '05/08', '07/08', '10/08', '12/08'],
    parEleve: {
      e4: ['present', 'present', 'present', 'retard', 'present'],
      e5: ['present', 'absent', 'present', 'present', 'present'],
    },
  },
  c3: {
    dates: ['02/08', '09/08', '16/08'],
    parEleve: {
      e3: ['present', 'absent', 'present'],
      e6: ['present', 'present', 'retard'],
    },
  },
  c4: {
    dates: ['06/08', '13/08', '20/08'],
    parEleve: {
      e7: ['present', 'present', 'present'],
      e8: ['retard', 'present', 'absent'],
    },
  },
}

export const choregraphiesParCours = {
  c1: [
    {
      id: 'ch1',
      nom: 'Comme un garçon',
      eleveIds: ['e1', 'e2', 'e4'],
      costume: 'Justaucorps noir, legging pailleté argent',
      horaireRepetition: 'Mercredi 17h00 - 18h30, salle 2',
      videos: [
        { titre: 'Version complète', url: '#' },
        { titre: 'Ralenti 16 premiers temps', url: '#' },
      ],
    },
    {
      id: 'ch2',
      nom: 'Bang bang',
      eleveIds: ['e1', 'e2'],
      costume: 'Combinaison rouge',
      horaireRepetition: 'Vendredi 18h00 - 19h00, salle 1',
      videos: [{ titre: 'Version complète', url: '#' }],
    },
  ],
  c2: [
    {
      id: 'ch3',
      nom: 'Naxos',
      eleveIds: ['e4', 'e5'],
      costume: 'Robe bleu nuit',
      horaireRepetition: 'Mercredi 20h00 - 20h30, salle 2',
      videos: [{ titre: 'Version complète', url: '#' }],
    },
  ],
  c3: [],
  c4: [
    {
      id: 'ch4',
      nom: 'Silhouettes',
      eleveIds: ['e7', 'e8'],
      costume: 'Body noir uni',
      horaireRepetition: 'Jeudi 20h30 - 21h00, salle 1',
      videos: [],
    },
  ],
}

// `choregraphieId` (nullable) tague la vidéo pour une chorégraphie du même
// cours (voir choregraphiesParCours ci-dessus) — utile pour retrouver toutes
// les vidéos d'une chorégraphie donnée.
export const videosParCours = {
  c1: [
    {
      id: 'v1',
      titre: 'Comme un garçon',
      datePublication: '05/08',
      duree: '03:42',
      description: '',
      choregraphieId: 'ch1',
    },
    {
      id: 'v2',
      titre: 'Bang bang',
      datePublication: '08/08',
      duree: '04:10',
      description: 'Passage à retravailler : le déplacement diagonal.',
      choregraphieId: 'ch2',
    },
  ],
  c2: [
    {
      id: 'v3',
      titre: 'Naxos — répétition',
      datePublication: '11/08',
      duree: '02:58',
      description: '',
      choregraphieId: 'ch3',
    },
  ],
  c3: [],
  c4: [
    {
      id: 'v4',
      titre: 'Silhouettes — filage',
      datePublication: '14/08',
      duree: '05:20',
      description: '',
      choregraphieId: 'ch4',
    },
  ],
}

export const conversations = [
  {
    id: 'conv1',
    type: 'groupe',
    nom: 'Jazz niveau moyen',
    messages: [
      {
        id: 'm1',
        auteur: 'Isabelle Chevalier',
        estMoi: false,
        contenu: 'Répét avancée à 17h30 mercredi prochain.',
        heure: '09:02',
        statut: 'vu',
        envoyeParMail: false,
      },
      {
        id: 'm2',
        auteur: 'Marianne',
        estMoi: false,
        contenu: 'Confirmez par mail ?',
        heure: '09:05',
        statut: 'vu',
        envoyeParMail: false,
      },
    ],
  },
  {
    id: 'conv2',
    type: 'individuelle',
    nom: 'Marianne (élève)',
    messages: [
      {
        id: 'm3',
        auteur: 'Marianne',
        estMoi: false,
        contenu: 'A quelle heure la répét de mercredi ?',
        heure: '09:02',
        statut: 'vu',
        envoyeParMail: false,
      },
      {
        id: 'm4',
        auteur: 'Valérie Petit',
        estMoi: true,
        contenu: '17h00 - 18h30, salle 2',
        heure: '09:15',
        statut: 'vu',
        envoyeParMail: true,
      },
    ],
  },
  {
    id: 'conv3',
    type: 'groupe',
    nom: 'Equipe pédagogique',
    messages: [
      {
        id: 'm5',
        auteur: 'Julien Renard',
        estMoi: false,
        contenu: 'Réunion planning la semaine prochaine ?',
        heure: 'Hier',
        statut: 'recu',
        envoyeParMail: false,
      },
    ],
  },
]

export const paiementLabels = {
  a_jour: 'À jour',
  en_attente: 'En attente',
  retard: 'Retard',
}
