import os
import shutil
from typing import Dict, List, Optional, Set, Tuple

from mutagen.id3 import ID3
from rich.table import Table

from ._ActionBase import ActionBase
from ..config import (
    get_lossless_exts,
    get_lossy_exts,
    get_music_root,
    get_plex_media_path_map,
    get_show_mode,
    get_tag_backup_dir,
    get_tag_copy_limit,
    should_delete_lossy,
    should_ignore_case,
    should_mirror_id3_version,
    should_refresh_plex,
    should_remove_name,
    should_write,
)
from ..utils.aiff_chunks import rewrite_name
from ..utils.confirm import confirm_destructive
from ..utils.id3_tags import copy_id3_wholesale, read_id3_fields
from ..utils.logger import console, logger
from ..utils.media_paths import parse_media_path_map, resolve_container_path
from ..utils.paths import PROJECT_ROOT
from ..utils.progress_bar import progress_instance

# Only AIFF/AIFF-C carry ID3 in a way this wholesale copy + NAME-chunk fix
# supports. FLAC (Vorbis comments) and WAV are skipped even if configured.
AIFF_EXTS = (".aiff", ".aif")

# (field key from read_id3_fields, column header) shown in the diff table.
_DIFF_COLS = [
    ("title", "Title"),
    ("artist", "Artist"),
    ("album", "Album"),
    ("albumartist", "AlbumArtist"),
    ("genre", "Genre"),
]


def _fmt(value: object) -> str:
    if value is None or value == "":
        return "[dim]—[/dim]"
    return str(value)


class LosslessTagCopy(ActionBase):
    """Copy ID3 tags wholesale from a leftover lossy file (MP3) onto a same-named
    lossless replacement (AIFF) sitting in the same folder, so curated metadata
    survives swapping the file.

    Read-only by default: walks the music root, pairs each lossy file with its
    lossless sibling by basename, and prints the tags that would transfer.
    ``--write`` overwrites the lossless file's ID3 (backing up each original),
    aligns the AIFF ``NAME`` chunk so Plex shows the new title, and — with
    ``--delete-lossy`` — removes the now-redundant lossy source."""

    def __init__(self) -> None:
        super().__init__("lossless tag copy")
        self.root = get_music_root()
        self.lossy_exts = get_lossy_exts()
        self.lossless_exts = get_lossless_exts()
        self.ignore_case = should_ignore_case()
        self.remove_name = should_remove_name()
        self.refresh = should_refresh_plex()
        self.delete_lossy = should_delete_lossy()
        self.mirror_version = should_mirror_id3_version()
        self.show = get_show_mode()
        self.limit = get_tag_copy_limit()
        self.path_map = parse_media_path_map(get_plex_media_path_map())

    def run(self) -> None:
        if not self.root:
            logger.error(
                "[red]No music root set — pass --root <dir> or set MUSIC_ROOT."
            )
            return
        if not os.path.isdir(self.root):
            logger.error(f"[red]Music root is not a directory: {self.root}")
            return
        if should_write():
            self.apply()
        else:
            self.preview()

    # --- pairing -----------------------------------------------------------

    def _classify(self, ext: str) -> Optional[str]:
        if ext in self.lossy_exts:
            return "lossy"
        if ext in self.lossless_exts:
            return "lossless"
        return None

    def _usable(self, path: str) -> Optional[str]:
        """Return None if the file is usable, else a skip reason. Guards broken
        symlinks and zero-byte files (both ends of a pair go through this)."""
        real = os.path.realpath(path)
        if not os.path.isfile(real):
            return "broken symlink / not a regular file"
        try:
            if os.path.getsize(real) == 0:
                return "zero-byte file"
        except OSError as e:
            return f"stat failed ({e})"
        return None

    def compute(
        self,
    ) -> Tuple[List[Dict], List[str], List[Tuple[str, str]]]:
        """Walk the root and return (pairs, unmatched, skipped).

        pair: {lossy, lossless, lossy_fields, lossless_fields, overwrite}.
        unmatched: lossy files with no lossless sibling (not yet upgraded).
        skipped: (lossy_path, reason) for ambiguous / unusable pairings."""
        assert self.root is not None  # guaranteed by run()
        pairs: List[Dict] = []
        unmatched: List[str] = []
        skipped: List[Tuple[str, str]] = []

        for dirpath, _dirnames, filenames in os.walk(self.root):
            # Group this directory's files by basename stem (extension stripped).
            groups: Dict[str, Dict[str, List[str]]] = {}
            for fn in filenames:
                stem, ext = os.path.splitext(fn)
                kind = self._classify(ext.lower())
                if kind is None:
                    continue
                key = stem.lower() if self.ignore_case else stem
                full = os.path.join(dirpath, fn)
                groups.setdefault(key, {"lossy": [], "lossless": []})[kind].append(full)

            for grp in groups.values():
                for lossy in grp["lossy"]:
                    losslesses = grp["lossless"]
                    if not losslesses:
                        unmatched.append(lossy)
                        continue
                    if len(losslesses) > 1:
                        names = ", ".join(os.path.basename(p) for p in losslesses)
                        skipped.append((lossy, f">1 lossless sibling ({names})"))
                        continue
                    lossless = losslesses[0]
                    ext = os.path.splitext(lossless)[1].lower()
                    if ext not in AIFF_EXTS:
                        skipped.append(
                            (lossy, f"unsupported lossless target '{ext}' (AIFF only)")
                        )
                        continue
                    for p in (lossy, lossless):
                        reason = self._usable(p)
                        if reason:
                            skipped.append((lossy, f"{os.path.basename(p)}: {reason}"))
                            break
                    else:
                        lossy_fields = read_id3_fields(lossy)
                        if not lossy_fields:
                            skipped.append((lossy, "no ID3 tag in lossy source"))
                            continue
                        lossless_fields = read_id3_fields(lossless)
                        pairs.append(
                            {
                                "lossy": lossy,
                                "lossless": lossless,
                                "lossy_fields": lossy_fields,
                                "lossless_fields": lossless_fields,
                                # A lossless file that already carries tags will be
                                # overwritten — surface that in the preview.
                                "overwrite": any(
                                    lossless_fields.get(k) for k, _ in _DIFF_COLS
                                ),
                            }
                        )

        pairs.sort(key=lambda d: d["lossless"].lower())
        unmatched.sort(key=str.lower)
        skipped.sort(key=lambda t: t[0].lower())
        if self.limit is not None:
            pairs = pairs[: self.limit]
        return pairs, unmatched, skipped

    # --- rendering ---------------------------------------------------------

    def _print_pairs(self, pairs: List[Dict]) -> None:
        title = "Tags to copy (lossy → lossless), incoming values shown"
        table = Table(title=title)
        table.add_column("#", justify="right", style="dim")
        for _key, header in _DIFF_COLS:
            table.add_column(header, style="green", overflow="fold")
        table.add_column("Art", justify="center")
        table.add_column("Overwrite?", justify="center")
        table.add_column("Lossless file", style="dim", overflow="fold")
        for i, p in enumerate(pairs, 1):
            lf = p["lossy_fields"]
            row = [str(i)]
            row += [_fmt(lf.get(k)) for k, _ in _DIFF_COLS]
            row.append("[green]✓[/green]" if lf.get("has_artwork") else "[dim]—[/dim]")
            row.append("[yellow]yes[/yellow]" if p["overwrite"] else "[dim]no[/dim]")
            row.append(p["lossless"])
            table.add_row(*row)
        console.print(table)

    def _print_unmatched(self, unmatched: List[str]) -> None:
        console.print(
            f"\n[bold]Lossy files with no lossless replacement yet:[/bold] "
            f"{len(unmatched)}"
        )
        for p in unmatched:
            console.print(f"  [yellow]·[/yellow] {p}")

    def _print_skipped(self, skipped: List[Tuple[str, str]]) -> None:
        if not skipped:
            return
        console.print(f"\n[yellow]Skipped {len(skipped)} pairing(s):[/yellow]")
        for path, reason in skipped[:20]:
            console.print(f"  [yellow]{reason}[/yellow] — {path}")
        if len(skipped) > 20:
            console.print(f"  [dim]… +{len(skipped) - 20} more[/dim]")

    def _summary(self, pairs: List[Dict], unmatched: List[str]) -> None:
        console.print(
            f"\n[bold]Matched pairs:[/bold] {len(pairs)}    "
            f"[bold]Not yet upgraded:[/bold] {len(unmatched)}"
        )

    # --- dry run -----------------------------------------------------------

    def preview(self) -> None:
        console.print(
            f"[bold cyan]Dry run (read-only)[/bold cyan] — root={self.root} "
            f"lossy={','.join(self.lossy_exts)} lossless={','.join(self.lossless_exts)} "
            f"show={self.show}\n"
        )
        pairs, unmatched, skipped = self.compute()
        if self.show in ("matched", "both") and pairs:
            self._print_pairs(pairs)
        if self.show in ("unmatched", "both"):
            self._print_unmatched(unmatched)
        self._print_skipped(skipped)
        self._summary(pairs, unmatched)
        if pairs:
            console.print(
                "\n[dim]Dry run — no files modified. Re-run with --write to apply.[/dim]"
            )
        else:
            console.print("[bold green]✔ No lossy→lossless pairs to copy.")

    # --- write -------------------------------------------------------------

    def _backup_dir(self) -> str:
        return get_tag_backup_dir() or str(PROJECT_ROOT / "lossless-tag-backups")

    def _v2_version(self, lossy: str) -> int:
        """ID3 major version to write: 3 (v2.3, default) unless --mirror-version,
        in which case mirror the source's version (falling back to 3)."""
        if not self.mirror_version:
            return 3
        try:
            ver = ID3(lossy).version
            return ver[1] if ver and ver[1] in (3, 4) else 3
        except Exception:  # noqa: BLE001 - fall back to the safe default
            return 3

    def apply(self) -> None:
        pairs, unmatched, skipped = self.compute()
        if self.show in ("unmatched", "both"):
            self._print_unmatched(unmatched)
        self._print_skipped(skipped)
        n = len(pairs)
        if n == 0:
            logger.info("[green]Nothing to copy — no lossy→lossless pairs found.")
            return

        self._print_pairs(pairs)
        backup_dir = self._backup_dir()
        extras = []
        if self.remove_name:
            extras.append("remove the AIFF NAME chunk")
        else:
            extras.append("set the AIFF NAME chunk to the copied title")
        if self.delete_lossy:
            extras.append("[red]delete the lossy source[/red]")
        console.print(
            f"\n[bold]About to copy tags onto [red]{n}[/red] lossless file(s)[/bold] "
            f"and {', '.join(extras)}.\n"
            f"  Lossless originals are backed up under: {backup_dir}"
        )
        if not confirm_destructive(
            f"This overwrites the ID3 tags of {n} lossless file(s)"
            + (" and deletes the matched lossy source(s)" if self.delete_lossy else "")
            + ".",
            "WRITE-TAGS",
            title="Write Lossless Tags",
        ):
            logger.info("[yellow]Aborted — confirmation token did not match.")
            return

        ok = 0
        deleted = 0
        changed_dirs: Set[str] = set()
        failed: List[Tuple[Dict, str]] = []
        with progress_instance() as progress:
            task = progress.add_task("", total=n)
            for p in pairs:
                progress.update(
                    task,
                    advance=1,
                    description=f'[cyan]Copying → "{os.path.basename(p["lossless"])}"...',
                )
                try:
                    self._copy_pair(p, backup_dir)
                    ok += 1
                    changed_dirs.add(os.path.dirname(os.path.realpath(p["lossless"])))
                    if self.delete_lossy:
                        deleted += 1
                except Exception as e:  # noqa: BLE001 - report and continue
                    failed.append((p, str(e)))

        console.print(
            f"[bold green]✔ Copied tags onto {ok}/{n} lossless file(s).[/bold green]"
            + (f" Deleted {deleted} lossy source(s)." if self.delete_lossy else "")
        )
        for p, err in failed:
            logger.error(f"[red]Failed: {p['lossless']}: {err}")

        if ok:
            self._after_write(changed_dirs)

    def _copy_pair(self, pair: Dict, backup_dir: str) -> None:
        """Back up the pristine lossless original, copy the lossy ID3 onto it,
        align the NAME chunk, then (optionally) delete the lossy source. The MP3
        is only removed once every prior step has succeeded."""
        lossy = pair["lossy"]
        aiff = os.path.realpath(pair["lossless"])

        # 1. Pristine backup BEFORE any mutation (mutagen.save writes in place).
        backup = os.path.join(backup_dir, aiff.lstrip("/"))
        os.makedirs(os.path.dirname(backup), exist_ok=True)
        shutil.copy2(aiff, backup)

        # 2. Wholesale ID3 copy (leaves SSND/NAME chunks intact).
        new_title = copy_id3_wholesale(lossy, aiff, v2_version=self._v2_version(lossy))

        # 3. Align the native NAME chunk so Plex shows the new title (or strip it).
        rewrite_name(aiff, None if self.remove_name else new_title, None)

        # 4. Only now is it safe to remove the redundant lossy source.
        if self.delete_lossy:
            os.remove(lossy)

    def _after_write(self, changed_dirs: Set[str]) -> None:
        if not self.refresh:
            console.print(
                "\n[dim]Plex won't reflect the changes until it re-reads the files. "
                "Re-run with --refresh-plex (needs PLEX_MEDIA_PATH_MAP), or trigger a "
                "library scan of the affected folders in Plex.[/dim]"
            )
            return
        if not self.path_map:
            logger.warning(
                "[yellow]--refresh-plex needs PLEX_MEDIA_PATH_MAP to map host dirs "
                "back to Plex paths — skipping the scan."
            )
            return
        from ..plex.resolvers.library import get_music_library

        library, _name = get_music_library()
        console.print(
            f"\n[cyan]Queuing a partial Plex scan of {len(changed_dirs)} folder(s)…[/cyan]"
        )
        for host_dir in sorted(changed_dirs):
            container = resolve_container_path(host_dir, self.path_map)
            if container is None:
                logger.warning(
                    f"[yellow]No PLEX_MEDIA_PATH_MAP prefix for {host_dir} — skipped."
                )
                continue
            try:
                library.update(path=container)
                console.print(f"  [green]scan queued[/green] {container}")
            except Exception as e:  # noqa: BLE001
                logger.warning(f"[yellow]Scan failed for {container}: {e}")
