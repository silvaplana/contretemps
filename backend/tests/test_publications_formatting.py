"""Texte mis en forme (Seb, 19 novembre 2026 ; actualites.md §12.15)."""

from publications import formatting


def test_sans_balises_pour_les_notifications_et_le_sujet():
    assert formatting.plain("[grand]Stage de Noël[/grand]\nSamedi [g]20 décembre[/g]") == "Stage de Noël\nSamedi 20 décembre"


def test_html_du_mail_echappe_et_mis_en_forme():
    html = formatting.to_html("Samedi [g]20 <décembre>[/g]\n[s]Inscription[/s] [petit]eau[/petit]")
    assert html == (
        "Samedi <strong>20 &lt;décembre&gt;</strong><br><u>Inscription</u> "
        '<span style="font-size:15px">eau</span>'
    )


def test_balises_mal_fermees():
    # Fermée sans être ouverte : ignorée ; restée ouverte : fermée à la fin.
    assert formatting.to_html("a[/g] [g]b") == "a <strong>b</strong>"
    # Croisées : jamais de HTML croisé.
    assert formatting.to_html("[g]a[s]b[/g]c[/s]") == "<strong>a<u>b</u></strong><u>c</u>"
