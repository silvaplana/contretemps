"""Textes par défaut de la page d'essai (spec/modules/essai.md §5), repris de
Sambo Admin sans ce qui était propre à ASC (horaires, salles, contacts) :
chaque école les change dans Admin > Essais > ⋮ > Page d'essai.

[élève], [parent] et [club] sont remplacés par les vrais noms.
"""

TITLE = "S'inscrire à un cours d'essai gratuit"

INTRO = (
    "Venez essayer un cours ! Inscrivez-vous ci-dessous : vous recevrez par e-mail un QR code "
    "à présenter au prof au début de votre cours d'essai."
)

RULES = [
    "Le cours d'essai est gratuit et sans engagement.",
    "Vous pouvez inscrire jusqu'à 3 personnes d'une même famille (même adresse e-mail) dans la même demande.",
    "Présentez votre QR code au prof au début du cours (sur votre téléphone ou imprimé).",
    "Un certificat médical est requis (à joindre à l'inscription).",
    "Arrivez 10 minutes avant le début du cours.",
]

MIN_AGE = 6

CERTIFICATE_HINT = "Certificat médical de non contre-indication, obligatoire (photo ou PDF)."

WAIVER = (
    "Je reconnais que la pratique sportive comporte des risques de blessure, et que le cours d'essai "
    "se fait dans le respect des consignes des encadrants. Je renonce à tout recours contre [club] et "
    "ses encadrants en cas d'accident survenu à [élève] pendant le cours d'essai, sauf faute de leur "
    "part. Je déclare être couvert(e) par une assurance responsabilité civile."
)

PARENTAL_CONSENT = (
    "En signant, je soussigné(e), [parent], représentant légal de [élève], donne mon autorisation "
    "pour le cours d'essai organisé par [club], et autorise les encadrants à prendre toute mesure "
    "d'urgence nécessaire (appel des secours) en cas d'accident."
)

PRIVACY = (
    "Vos informations servent uniquement à organiser votre cours d'essai. Elles sont supprimées "
    "automatiquement au bout d'un an. Le certificat médical n'est pas gardé : il est seulement joint "
    "au mail de confirmation. Pour les faire supprimer plus tôt, répondez au mail de confirmation."
)


def fill(text: str, student: str = "", parent: str = "", club: str = "") -> str:
    return text.replace("[élève]", student or "l'élève").replace("[parent]", parent).replace("[club]", club)
