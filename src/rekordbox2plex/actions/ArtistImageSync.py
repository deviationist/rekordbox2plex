import os
import shutil
import tempfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, List, Optional, Tuple

from rich.table import Table

from ._ActionBase import ActionBase
from ..artwork.collab import split_ambiguous, split_collab
from ..artwork.collage import compose_strips
from ..artwork.mbid import PlexMbidResolver
from ..artwork.musicbrainz import MusicBrainzResolver
from ..artwork.placeholder import is_unusable_url
from ..artwork.providers import ArtistImage
from ..artwork.registry import build_providers
from ..config import (
    get_artist_image_limit,
    get_artist_image_providers,
    get_artist_image_threads,
    get_collab_ambiguous_separators,
    get_collab_min_score,
    get_collab_min_segment_len,
    get_collab_mode,
    get_collab_primary_separators,
    get_musicbrainz_user_agent,
    get_only_rating_keys,
    get_verbosity,
    should_overwrite_posters,
    should_write,
)
from ..plex.resolvers.library import get_music_library
from ..utils.confirm import confirm_destructive
from ..utils.logger import console, logger


def _fmt(value: Optional[str]) -> str:
    return value if value else "[dim]—[/dim]"


# (provider-or-"mbid", status, detail) — one per resolution step, for observability
Attempt = Tuple[str, str, str]
# (artist, chosen image or None, the per-step attempts that led there)
Resolved = Tuple[Any, Optional[ArtistImage], List[Attempt]]


def _bucket(attempts: List[Attempt]) -> str:
    """Collapse a no-match artist's attempts into one human reason, prioritising
    recoverable causes (rate-limit/error) over a genuine miss."""
    statuses = {status for who, status, _ in attempts if who != "mbid"}
    if "rate_limited" in statuses:
        return "rate_limited"
    if "error" in statuses:
        return "error"
    mbid_hit = any(who == "mbid" and status == "hit" for who, status, _ in attempts)
    if not mbid_hit and statuses and statuses <= {"skipped"}:
        return "no_mbid"
    return "miss"


class ArtistImageSync(ActionBase):
    """Set Plex **artist posters** from external sources, for a library on the
    local-metadata agent that otherwise has no artist art.

    Mimics Plex's own sources without depending on the Plex-agent library, so a
    local-metadata library stays rebuildable from scratch. Each artist's **MBID**
    is taken from Plex's own agent match (``Artist.matches`` → top ``mbid://``
    GUID, no metadata rebind), falling back to a MusicBrainz text search; the
    poster is then fetched from the configured providers in order — curated
    MBID-keyed portraits first (**fanart.tv**, **TheAudioDB**), then **Discogs**
    by name as the broad coverage fallback (Discogs' community images are often
    release covers, not portraits). Each provider reports a status so failures are
    explained, not swallowed. Read-only by default (shows a table); ``--write``
    uploads behind the ``WRITE-IMAGES`` token.

    Scope: **artist posters only** — a sanctioned exception to the no-artwork-via-
    API rule; it never touches track/album art or any other metadata."""

    def __init__(self) -> None:
        super().__init__("artist images")
        self.providers = build_providers(get_artist_image_providers())
        self.overwrite = should_overwrite_posters()
        self.limit = get_artist_image_limit()
        self.threads = get_artist_image_threads()
        self.verbose = get_verbosity() > 0
        self.collab_mode = get_collab_mode()
        # Configurable separators: primary (always-on) + opt-in ambiguous (& + x).
        self.primary_seps = get_collab_primary_separators()
        self.ambiguous_seps = get_collab_ambiguous_separators()
        self.collab_min_score = get_collab_min_score()
        self.collab_min_seg_len = get_collab_min_segment_len()
        self.plex_mbid = PlexMbidResolver()
        # MusicBrainz text search is the fallback MBID source — needed when a
        # provider can't work without an MBID (fanart.tv) or to resolve collab
        # members by name (they have no Plex artist object to match).
        self._mb: Optional[MusicBrainzResolver] = None
        if any(p.requires_mbid for p in self.providers) or self.collab_mode != "skip":
            self._mb = MusicBrainzResolver(get_musicbrainz_user_agent())

    def run(self) -> None:
        if not self.providers:
            logger.error(
                "[red]No artist-image providers available — check "
                "PLEX_ARTIST_IMAGE_PROVIDERS / API keys."
            )
            return
        order = ", ".join(p.name for p in self.providers)
        console.print(
            f"[dim]Art providers (in order): {order}  |  MBID: Plex match"
            f"{' → MusicBrainz' if self._mb else ''}  |  collab: {self.collab_mode}[/dim]"
        )
        if should_write():
            self.apply()
        else:
            self.preview()

    # --- enumeration + resolution -----------------------------------------

    def _artists(self) -> List[Any]:
        section, _ = get_music_library()
        artists = section.searchArtists()
        only = get_only_rating_keys()
        if only:
            artists = [a for a in artists if int(a.ratingKey) in only]
        if not self.overwrite:
            artists = [a for a in artists if not a.thumb]  # only those missing art
        if self.limit:
            artists = artists[: self.limit]
        return artists

    def _resolve(self, artist: Any) -> Tuple[Optional[ArtistImage], List[Attempt]]:
        name = artist.title
        attempts: List[Attempt] = []
        # Align with Plex: take its confident match's canonical name + MBID.
        match = self.plex_mbid.match(artist)
        mbid = match.mbid if match else None
        canonical = match.name if match else None
        source = "plex" if mbid else ""
        if not mbid and self._mb:
            mbid = self._mb.mbid_for(name)
            source = "musicbrainz" if mbid else ""
        # A name-based hit must match the local tag OR Plex's canonical name.
        accept = [name] + ([canonical] if canonical else [])
        attempts.append(
            ("mbid", "hit" if mbid else "miss", f"{source}:{mbid}" if mbid else "")
        )
        for p in self.providers:
            r = p.find(name, mbid=mbid, accept_names=accept)
            # Central usability gate: reject blank/single-color images (any
            # source) and this provider's known placeholders. Real portraits are
            # size-gated so they're not downloaded.
            if r.image and is_unusable_url(r.image.url, source=p.name):
                attempts.append((p.name, "unusable", r.image.url[:48]))
                continue
            attempts.append((p.name, r.status, r.detail))
            if r.image:
                return r.image, attempts
        # LAST RESORT — only now that the full string missed EVERY source: if it's
        # a multi-artist collab string, split and resolve the pieces.
        if self.collab_mode != "skip":
            has_top = bool(split_collab(name, self.primary_seps))
            has_amb = bool(self.ambiguous_seps) and bool(
                split_ambiguous(name, self.ambiguous_seps)
            )
            if has_top or has_amb:
                img = self._resolve_collab(name, attempts)
                if img:
                    return img, attempts
        return None, attempts

    def _resolve_member(
        self, name: str, min_score: Optional[int] = None
    ) -> Optional[ArtistImage]:
        """Resolve one collab member by name (no Plex artist object → MBID via
        MusicBrainz at ``min_score``, then the same providers, name-verified)."""
        mbid = self._mb.mbid_for(name, min_score=min_score) if self._mb else None
        for p in self.providers:
            r = p.find(name, mbid=mbid, accept_names=[name])
            if r.image and not is_unusable_url(r.image.url, source=p.name):
                return r.image
        return None

    def _resolve_collab(
        self, name: str, attempts: List[Attempt]
    ) -> Optional[ArtistImage]:
        """Two-level, whole-first resolution. Split on comma/feat; resolve each
        component WHOLE first (so genuine '&'-artists like 'Above & Beyond' stay
        intact); only a component that *also* misses every source is split again on
        the opt-in ambiguous separators (& +). Pieces use a stricter MB score."""
        components = split_collab(name, self.primary_seps) or [name.strip()]
        members: List[Tuple[str, ArtistImage]] = []
        for c in components:
            if len(c) >= self.collab_min_seg_len:
                im = self._resolve_member(c, min_score=self.collab_min_score)
                if im:
                    members.append((c, im))
                    continue
            if self.ambiguous_seps:
                for s in split_ambiguous(c, self.ambiguous_seps):
                    # skip too-short fragments from an over-eager split (e.g. "Bz")
                    if len(s) < self.collab_min_seg_len:
                        continue
                    sim = self._resolve_member(s, min_score=self.collab_min_score)
                    if sim:
                        members.append((s, sim))
        attempts.append(
            ("collab", "hit" if members else "miss", f"{len(members)} member(s)")
        )
        if not members:
            return None
        if self.collab_mode == "primary":
            # First member (in tag order) that resolved = the primary.
            label, img = members[0]
            return ArtistImage(
                url=img.url, source=f"{img.source} (primary)", matched_name=label
            )
        # collage: composite all resolved members (built at upload time).
        return ArtistImage(
            url="",
            source="collage",
            matched_name=" + ".join(label for label, _ in members),
            members=[im.url for _, im in members],
        )

    def compute(self) -> List[Resolved]:
        artists = self._artists()
        total = len(artists)
        results: List[Resolved] = []
        if total == 0:
            return results
        console.print(
            f"[cyan]Matching {total} artist(s) with {self.threads} thread(s)…[/cyan]"
        )
        done = matched = 0
        with ThreadPoolExecutor(max_workers=self.threads) as ex:
            futures = {ex.submit(self._resolve, a): a for a in artists}
            for fut in as_completed(futures):
                a = futures[fut]
                try:
                    img, attempts = fut.result()
                except Exception as e:  # noqa: BLE001 - report and continue
                    img, attempts = None, [("internal", "error", str(e))]
                    logger.error(f"[red]match failed for {a.title!r}: {e}")
                results.append((a, img, attempts))
                done += 1
                matched += 1 if img else 0
                if self.verbose:
                    if img:
                        logger.info(f"[{done}/{total}] {a.title} [green]✓ {img.source}")
                    else:
                        why = ", ".join(f"{w}:{s}" for w, s, _ in attempts)
                        logger.info(
                            f"[{done}/{total}] {a.title} [yellow]— none[/yellow] ({why})"
                        )
                elif done % 25 == 0 or done == total:
                    console.print(f"[dim]  …matched {matched}/{done} of {total}[/dim]")
        return results

    # --- rendering ---------------------------------------------------------

    def _table(self, found: List[Tuple[Any, ArtistImage]]) -> None:
        table = Table(title="Artist posters to set")
        table.add_column("#", justify="right", style="dim")
        table.add_column("ratingKey", justify="right", style="dim")
        table.add_column("Artist")
        table.add_column("Matched as", overflow="fold")
        table.add_column("Source", style="cyan")
        table.add_column("Image URL", style="dim", overflow="fold")
        for i, (a, img) in enumerate(found, 1):
            # Flag when the provider-side name differs from the local tag.
            matched = img.matched_name or ""
            if matched and matched.casefold() != a.title.casefold():
                matched = f"[yellow]{matched}[/yellow]"
            url_cell = (
                f"[dim]<collage: {len(img.members)} portraits>[/dim]"
                if img.members
                else _fmt(img.url)
            )
            table.add_row(
                str(i),
                str(a.ratingKey),
                a.title,
                matched or "—",
                img.source,
                url_cell,
            )
        console.print(table)

    def _summary(self, results: List[Resolved]) -> int:
        found = [(a, img) for a, img, _ in results if img]
        nomatch = [(a, attempts) for a, img, attempts in results if not img]
        if found:
            self._table(found)
        console.print(
            f"\n[bold]Artists checked:[/bold] {len(results)}  "
            f"[bold green]with image:[/bold green] {len(found)}  "
            f"[bold yellow]no match:[/bold yellow] {len(nomatch)}"
        )
        if nomatch:
            # Observability: why did the no-matches fail? Separates recoverable
            # causes (rate-limit/error → re-run helps) from genuine misses.
            breakdown = Counter(_bucket(attempts) for _, attempts in nomatch)
            labels = {
                "miss": "genuine no-image",
                "rate_limited": "rate-limited (re-run may recover)",
                "error": "errors (re-run may recover)",
                "no_mbid": "no MBID + MBID-only providers",
            }
            parts = [f"{labels.get(k, k)}: {v}" for k, v in breakdown.most_common()]
            console.print("[dim]No-match breakdown:[/dim] " + "  |  ".join(parts))
            console.print(
                "[dim]No image found for:[/dim] "
                + ", ".join(a.title for a, _ in nomatch[:30])
            )
            if len(nomatch) > 30:
                console.print(f"[dim]  … +{len(nomatch) - 30} more[/dim]")
        return len(found)

    # --- dry run / write ---------------------------------------------------

    def preview(self) -> None:
        scope = "all artists" if self.overwrite else "artists missing a poster"
        console.print(f"[bold cyan]Dry run (read-only)[/bold cyan]  scope: {scope}\n")
        results = self.compute()
        n = self._summary(results)
        if n:
            console.print(
                "\n[dim]Dry run — no posters uploaded. Re-run with --write to apply.[/dim]"
            )

    def apply(self) -> None:
        results = self.compute()
        found = [(a, img) for a, img, _ in results if img]
        self._summary(results)
        n = len(found)
        if n == 0:
            logger.info("[green]Nothing to set — no artist images resolved.")
            return
        console.print(
            f"\n[bold]About to upload posters to [red]{n}[/red] artist(s) "
            f"in Plex.[/bold]"
        )
        if not confirm_destructive(
            f"This will set the poster on {n} Plex artist(s) "
            f"(artist images only — no other metadata touched).",
            "WRITE-IMAGES",
            title="Write Artist Images",
        ):
            logger.info("[yellow]Aborted — confirmation token did not match.")
            return
        ncollage = sum(1 for _, img in found if img.members)
        extra = f" ({ncollage} composited)" if ncollage else ""
        console.print(
            f"[cyan]Uploading {n} poster(s){extra} with {self.threads} thread(s)…[/cyan]"
        )
        tmpdir = tempfile.mkdtemp(prefix="rb2plex-collage-")

        def _upload(a: Any, img: ArtistImage) -> None:
            if img.members:
                path = os.path.join(tmpdir, f"{a.ratingKey}.jpg")
                if not compose_strips(img.members, path):
                    raise RuntimeError("could not fetch any member portrait")
                a.uploadPoster(filepath=path)
            else:
                a.uploadPoster(url=img.url)

        ok = done = 0
        try:
            with ThreadPoolExecutor(max_workers=self.threads) as ex:
                futures = {ex.submit(_upload, a, img): a for a, img in found}
                for fut in as_completed(futures):
                    a = futures[fut]
                    done += 1
                    try:
                        fut.result()
                        ok += 1
                        if self.verbose:
                            logger.info(f"[{done}/{n}] set poster: {a.title}")
                        elif done % 25 == 0 or done == n:
                            console.print(f"[dim]  …uploaded {ok}/{done} of {n}[/dim]")
                    except Exception as e:  # noqa: BLE001 - report and continue
                        logger.error(f"[red]Failed to set poster for {a.title!r}: {e}")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
        console.print(f"[bold green]✔ Set posters on {ok}/{n} artist(s).[/bold green]")
