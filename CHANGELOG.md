# Changelog

## Unreleased

- Remap numeric reply links when importing export envelopes, including forward links and existing destinations. Drop links to messages outside the batch and return revisions after link updates.

## 1.1.0 — 2026-10-25

- Add SQLite message-base support and an optional network extra for packet, nodelist and node commands. Operational failures use closed codes, including legacy commands; broken stdout exits 141. Base operations remain available without network dependencies.
