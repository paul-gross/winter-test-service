"""Domain-level persistence errors. Callers depend on these, never on SQLAlchemy's."""

from __future__ import annotations


class RepositoryError(Exception):
    """Raised by repositories when a persistence operation fails.

    Wraps the underlying library exception at the repository boundary so no
    SQLAlchemy exception type escapes into the service or transport layers.
    """
