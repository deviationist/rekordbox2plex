"""Artist-image sourcing for the `artist-images` subcommand.

A **driver-based** design: each external source (TheAudioDB, fanart.tv, …) is a
small provider exposing a uniform `find(artist_name, mbid)` method. The action
tries providers in the configured order and uploads the first hit to Plex.

This is the one place the tool writes *artwork* to Plex — a deliberate,
documented exception to the "no metadata/artwork via the Plex API" rule, scoped
**strictly to artist posters** (artist images cannot come from audio file tags,
unlike titles/album art). See CLAUDE.md → Scope.
"""
