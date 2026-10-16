"""Admin-side errors.

Small, named errors let the service layer say *what* went wrong
("not found", "duplicate") without knowing anything about web pages.
app.py later turns each one into the right HTTP status code.
"""


class AdminError(Exception):
    """Base class for every admin error."""


class NotFoundError(AdminError):
    """The record the admin asked for does not exist."""


class DuplicateError(AdminError):
    """The record would duplicate one that already exists."""


class InvalidStateError(AdminError):
    """The action is not allowed in the record's current state
    (for example: cancelling an appointment that is already cancelled)."""