// Adresse web d'une école : https://<adresse>.contretemps.silvaplana.cloud
// (spec §2.7). Même règle que le serveur (backend/src/personnalisation/
// adresse.py) : la saisie est normalisée en direct, le serveur revérifie.
export const DOMAINE_ECOLES = 'contretemps.silvaplana.cloud'

export function normaliserAdresse(texte) {
  return (texte ?? '')
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+/, '')
    .slice(0, 40)
}
