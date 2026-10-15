"""Traitement des images de personnalisation (spec §5.1.1) : logo et nom
de l'école en image. Recadrage des marges vides, réduction, détourage
optionnel, et fabrication des icônes de l'appli installée (logo posé sur la
couleur de fond, Android et iPhone affichant mal une icône transparente).
"""

from __future__ import annotations

import io
from collections import Counter

from PIL import Image, ImageOps

COTE_MAX_LOGO = 512
LARGEUR_MAX_NOM = 1200
TAILLE_MAX_OCTETS = 5_000_000
TYPES_ACCEPTES = {"image/png", "image/jpeg", "image/webp", "image/svg+xml"}

# Détourage « Simple » : écart de couleur toléré avec le fond (0-255 par canal).
TOLERANCE_FOND = 40


class ImageRefusee(ValueError):
    """Le message est montrable."""


def ouvrir(contenu: bytes, type_mime: str) -> Image.Image:
    if len(contenu) > TAILLE_MAX_OCTETS:
        raise ImageRefusee("Image trop lourde : 5 Mo au plus.")
    if type_mime not in TYPES_ACCEPTES:
        raise ImageRefusee("Formats acceptés : PNG, JPG, WebP ou SVG.")
    if type_mime == "image/svg+xml":
        return _svg_en_image(contenu)
    try:
        image = Image.open(io.BytesIO(contenu))
        image.load()
    except Exception as erreur:
        raise ImageRefusee("Cette image n'a pas pu être lue.") from erreur
    return ImageOps.exif_transpose(image).convert("RGBA")


def _svg_en_image(contenu: bytes) -> Image.Image:
    try:
        import cairosvg
    except ImportError as erreur:
        raise ImageRefusee("Les images SVG ne sont pas encore acceptées : envoyez un PNG.") from erreur
    png = cairosvg.svg2png(bytestring=contenu, output_width=COTE_MAX_LOGO * 2)
    return Image.open(io.BytesIO(png)).convert("RGBA")


def a_de_la_transparence(image: Image.Image) -> bool:
    return image.getchannel("A").getextrema()[0] < 250


def couleur_des_coins(image: Image.Image) -> tuple[int, int, int]:
    """La couleur la plus fréquente sur le pourtour de l'image : son fond."""
    rgb = image.convert("RGB")
    largeur, hauteur = rgb.size
    pas = max(1, min(largeur, hauteur) // 50)
    bord = [rgb.getpixel((x, y)) for x in range(0, largeur, pas) for y in (0, hauteur - 1)]
    bord += [rgb.getpixel((x, y)) for y in range(0, hauteur, pas) for x in (0, largeur - 1)]
    # Regroupées par paliers de 8, pour qu'un léger dégradé compte comme une seule couleur.
    paliers = Counter(tuple(c // 8 for c in pixel) for pixel in bord)
    palier = paliers.most_common(1)[0][0]
    voisins = [pixel for pixel in bord if tuple(c // 8 for c in pixel) == palier]
    return tuple(sum(p[i] for p in voisins) // len(voisins) for i in range(3))


def couleur_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def couleur_de_fond_proposee(image: Image.Image) -> str | None:
    """Couleur de fond de l'appli proposée d'après le logo (demande du
    2026-10-15) : le fond de l'image, s'il en a un (pas transparent)."""
    if a_de_la_transparence(image):
        return None
    return couleur_hex(couleur_des_coins(image))


def detourage_simple(image: Image.Image) -> Image.Image:
    """Retire le fond uni autour du dessin : la couleur des coins, et les
    pixels proches de cette couleur reliés au bord (remplissage depuis les
    bords). Ne touche pas l'intérieur du dessin s'il n'est pas relié au bord."""
    rgba = image.convert("RGBA")
    largeur, hauteur = rgba.size
    fond = couleur_des_coins(rgba)
    pixels = rgba.load()

    def proche(x: int, y: int) -> bool:
        r, g, b, a = pixels[x, y]
        return a > 0 and max(abs(r - fond[0]), abs(g - fond[1]), abs(b - fond[2])) <= TOLERANCE_FOND

    a_voir = [(x, y) for x in range(largeur) for y in (0, hauteur - 1)]
    a_voir += [(x, y) for y in range(hauteur) for x in (0, largeur - 1)]
    vus = set()
    while a_voir:
        x, y = a_voir.pop()
        if (x, y) in vus or not (0 <= x < largeur and 0 <= y < hauteur):
            continue
        vus.add((x, y))
        if not proche(x, y):
            continue
        r, g, b, _ = pixels[x, y]
        pixels[x, y] = (r, g, b, 0)
        a_voir.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
    return rgba


def recadrer(image: Image.Image) -> Image.Image:
    """Retire les marges vides (transparentes)."""
    boite = image.getchannel("A").getbbox()
    return image.crop(boite) if boite else image


def reduire(image: Image.Image, cote_max: int) -> Image.Image:
    copie = image.copy()
    copie.thumbnail((cote_max, cote_max), Image.LANCZOS)
    return copie


def en_png(image: Image.Image) -> bytes:
    sortie = io.BytesIO()
    image.save(sortie, format="PNG", optimize=True)
    return sortie.getvalue()


def icone(logo: Image.Image, couleur_fond: str | None, taille: int, maskable: bool = False) -> bytes:
    """Le logo centré, sur un carré de la couleur de fond, ou sur un fond
    transparent si `couleur_fond` vaut None (ordinateur : raccourci, barre
    des tâches, onglet, qui affichent l'icône telle quelle). « maskable » :
    marge plus large, Android pouvant rogner l'icône en cercle."""
    fond = Image.new("RGBA", (taille, taille), couleur_fond or (0, 0, 0, 0))
    marge = 0.2 if maskable else 0.08
    cote = int(taille * (1 - 2 * marge))
    dessin = reduire(logo, cote)
    fond.alpha_composite(dessin, ((taille - dessin.width) // 2, (taille - dessin.height) // 2))
    return en_png(fond if couleur_fond is None else fond.convert("RGB"))
