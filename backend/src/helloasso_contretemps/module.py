"""Declaration of the HelloAsso module for Contretemps (spec/core.md §9 bis,
spec/modules/helloasso.md): the `helloasso` module, whose statistics (§7.8)
read the Financier's accounts and the FFST licences here."""

from dataclasses import replace

from helloasso.module import MODULE as HELLOASSO

from . import adapter


def mount(app, core) -> None:
    HELLOASSO.mount(app, core)
    finances = getattr(core, "finances_client", None)
    core.helloasso_stats.ledger = adapter.ledger(finances) if finances is not None else None
    core.helloasso_stats.licences = adapter.licences


MODULE = replace(HELLOASSO, mount=mount)
