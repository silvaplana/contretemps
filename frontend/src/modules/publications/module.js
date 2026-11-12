import Blogs from './Blogs.jsx'

// Déclaration du module Publications (spec/core.md §9 bis et §11.1,
// spec/modules/actualites.md §12) : un onglet par blog de l'école (Actus,
// Techniques…), à la suite d'Admin, calculés une fois les blogs lus
// (App.jsx) ; leur clé commence par `tabPrefix`. Sous la case de
// Fonctionnalités, la liste des blogs (`settings`).
export default {
  key: 'publications',
  tabPrefix: 'blog-',
  tabs: (blogs = []) =>
    blogs
      .filter((b) => b.peutLire)
      .map((b) => ({ key: `blog-${b.id}`, label: b.nom, icon: b.icone, roles: ['admin', 'professeur', 'eleve'], blog: b })),
  settings: Blogs,
}
