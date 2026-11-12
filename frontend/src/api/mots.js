// Les mots du Vocabulaire (Admin > École > Personnalisation) dans les phrases
// de l'appli : « l’école » devient « le club » si l'école a choisi « Club »,
// « élève » devient « adhérent ». Avec les mots par défaut, les phrases sont
// celles d'avant, à la lettre (Alliance Sambo, 12 novembre).
import { apparenceActuelle, useApparence } from './apparence.js'

// Mots masculins qu'une école peut choisir à la place de « École » ; tout
// autre mot est traité au féminin, comme « école » et « association ».
const MASCULINS = ['club', 'studio', 'dojo', 'centre', 'cercle', 'collectif', 'gymnase', 'groupe', 'atelier']

const voyelle = (mot) => /^[aeiouyhâàéèêëîïôöûü]/i.test(mot)
const minuscule = (mot) => mot.charAt(0).toLowerCase() + mot.slice(1)
const majuscule = (mot) => mot.charAt(0).toUpperCase() + mot.slice(1)

export function formes(apparence) {
  const ecole = minuscule((apparence.motEcole || 'École').trim())
  const masculin = MASCULINS.includes(ecole.toLowerCase())
  const lEcole = voyelle(ecole) ? `l’${ecole}` : `${masculin ? 'le' : 'la'} ${ecole}`
  const deLEcole = voyelle(ecole) ? `de l’${ecole}` : masculin ? `du ${ecole}` : `de la ${ecole}`
  const eleves = minuscule((apparence.motEleves || 'Élèves').trim())
  const eleve = eleves.endsWith('s') ? eleves.slice(0, -1) : eleves
  return {
    ecole,
    Ecole: majuscule(ecole),
    lEcole,
    LEcole: majuscule(lEcole),
    deLEcole,
    uneEcole: `${masculin ? 'un' : 'une'} ${ecole}`,
    // « Changer d’école », « Changer de club »
    dEcole: voyelle(ecole) ? `d’${ecole}` : `de ${ecole}`,
    // « créée » ou « créé »
    eEcole: masculin ? '' : 'e',
    cetteEcole: masculin ? (voyelle(ecole) ? `cet ${ecole}` : `ce ${ecole}`) : `cette ${ecole}`,
    eleve,
    Eleve: majuscule(eleve),
    eleves,
    Eleves: majuscule(eleves),
    lEleve: voyelle(eleve) ? `l’${eleve}` : `le ${eleve}`,
    cetEleve: voyelle(eleve) ? `cet ${eleve}` : `ce ${eleve}`,
    unEleve: `un ${eleve}`,
    // « 3 élèves », « 1 élève »
    nEleves: (n) => `${n} ${n > 1 ? eleves : eleve}`,
  }
}

export function useMots() {
  return formes(useApparence())
}

export function mots() {
  return formes(apparenceActuelle())
}
