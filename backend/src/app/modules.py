"""Les modules de l'appli Contretemps, une ligne par module, dans l'ordre où
ils sont montés (spec/core.md §9 bis.2). Un module se place sous ceux dont
il a besoin (`requires`) ; sinon le serveur refuse de démarrer."""

from assistant.module import MODULE as assistant
from choregraphies.module import MODULE as choregraphies
from documents_contretemps.module import MODULE as documents
from finances_contretemps.module import MODULE as finances
from inscriptions.module import MODULE as registration
from messagerie.module import MODULE as messaging
from notes_frais_contretemps.module import MODULE as expense_notes
from presence.module import MODULE as presence
from saisons.module import MODULE as seasons
from session_clips_contretemps.module import MODULE as session_clips
from videos.module import MODULE as videos

MODULES = [
    seasons,
    videos,
    choregraphies,
    presence,
    messaging,
    registration,
    documents,
    assistant,
    expense_notes,
    finances,
    session_clips,
]
