"""How a step ends the run: Refused = exit 1 (nothing was changed, or it was undone), CannotRun = exit 2."""


class Refused(Exception):
    """A rule stopped the update. The message says why and what to do."""


class CannotRun(Exception):
    """The updater could not do its job (git or the network failed, ...)."""
