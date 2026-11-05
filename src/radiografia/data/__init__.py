"""Data access: per-source adapters and a repository that reads normalised local snapshots.

Rule: nothing in this package is called while a user is analysing a portfolio over the
network; ingestion runs offline from `scripts/`.
"""
