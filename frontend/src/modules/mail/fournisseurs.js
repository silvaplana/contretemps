// Les boîtes qu'on sait connecter (spec/modules/mail.md §4 ; Seb, 18 novembre) :
// page où créer le code et consignes de l'écran guidé (Connexion.jsx).

// Adresses Infomaniak gratuites (my kSuite) : mot de passe créé dans l'appli
// Mail ; les autres (nom de domaine du club) : dans le Manager.
const KSUITE = /@(ik\.me|etik\.com|ikmail\.com)$/i

export const FOURNISSEURS = {
  gmail: {
    nom: 'Gmail',
    // Le compte doit avoir la validation en deux étapes ; Google interdit de
    // créer le code à notre place.
    url: () => 'https://myaccount.google.com/apppasswords',
    etapes: () => ['Google s’ouvre : appuyez sur Créer.', 'Copiez le code de 16 lettres.', 'Revenez ici et collez-le.'],
    code: 'Code Google',
    consigne: 'Collez le code de 16 lettres donné par Google.',
    exemple: 'xxxx xxxx xxxx xxxx',
    note: 'Si Google demande d’abord d’activer la validation en deux étapes, suivez ses indications : il faut un téléphone pour recevoir un code.',
  },
  infomaniak: {
    nom: 'Infomaniak',
    url: (adresse) => (KSUITE.test(adresse) ? 'https://ksuite.infomaniak.com/mail' : 'https://manager.infomaniak.com'),
    etapes: (adresse) =>
      KSUITE.test(adresse)
        ? [
            'Infomaniak s’ouvre : touchez ⋮ à côté de l’adresse, puis Paramètres, Gérer le mot de passe, Ajouter un appareil.',
            'Choisissez IMAP / SMTP et copiez le mot de passe donné.',
            'Revenez ici et collez-le.',
          ]
        : [
            'Infomaniak s’ouvre : Service Mail, le nom de domaine, l’adresse, Appareils, Ajouter un appareil.',
            'Copiez le mot de passe donné.',
            'Revenez ici et collez-le.',
          ],
    code: 'Mot de passe Infomaniak',
    consigne: 'Collez le mot de passe donné par Infomaniak.',
    exemple: '',
    note: 'Infomaniak ne montre ce mot de passe qu’une fois : s’il est perdu, créez-en un autre.',
  },
}
