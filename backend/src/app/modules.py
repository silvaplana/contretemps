"""Les modules de l'appli Contretemps, une ligne par module, dans l'ordre où
ils sont montés (spec/core.md §9 bis.2). Un module se place sous ceux dont
il a besoin (`requires`) ; sinon le serveur refuse de démarrer."""

from assistant.module import MODULE as assistant
from auto_import.module import MODULE as auto_import
from choregraphies.module import MODULE as choregraphies
from documents_contretemps.module import MODULE as documents
from drives.module import MODULE as drives
from helloasso_contretemps.module import MODULE as helloasso
from finances_contretemps.module import MODULE as finances
from ffst.module import MODULE as ffst
from inscriptions.module import MODULE as registration
from mail.module import MODULE as mail
from messagerie.module import MODULE as messaging
from notes_frais_contretemps.module import MODULE as expense_notes
from presence.module import MODULE as presence
from publications.module import MODULE as publications
from saisons.module import MODULE as seasons
from session_clips_contretemps.module import MODULE as session_clips
from trials.module import MODULE as trials
from videos.module import MODULE as videos

MODULES = [
    seasons,
    drives,
    videos,
    choregraphies,
    presence,
    messaging,
    mail,
    registration,
    documents,
    assistant,
    expense_notes,
    auto_import,
    finances,
    session_clips,
    helloasso,
    ffst,
    publications,
    trials,
]
