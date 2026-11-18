"""Declaration of the FFST module (spec/core.md §9 bis, spec/modules/ffst.md).
Off in existing schools (migration of 18 November 2026); needs HelloAsso,
which brings the members and their form answers."""

from registry import Module, guide_file

from .club import Club
from .receiver import FfstReceiver


def mount(app, core) -> None:
    core.ffst_club = Club()
    core.ffst_receiver = FfstReceiver(club=core.ffst_club, app=app)


MODULE = Module(key="ffst", label="FFST", requires=("helloasso",), mount=mount, guide=guide_file(__file__))
