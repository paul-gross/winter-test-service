"""Shared persistence layer for winter-test-service.

A flat top-level package imported by both services (the api runs with
`PYTHONPATH=.`; the worker runs as a module from the repo root). It owns the
domain model, the read/write repository Protocol seams, and the SQLAlchemy
adapters behind them — so the api and worker share one schema and one I/O
boundary instead of each hand-rolling SQL.
"""
