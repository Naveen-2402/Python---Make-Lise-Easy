#!/usr/bin/env python3
# run.py — verbose, no-args, uses PdfWriter (pypdf 5+)

import io
import re
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple

from pypdf import PdfReader, PdfWriter

# ====== CONFIG (hard-coded) ===================================================
PASSWORD = "38717002991"               # shared password for locked PDFs
OUTPUT_NAME = "merged_by_date.pdf"     # name of the merged (decrypted) output
PAUSE_ON_EXIT = False                  # set True if you double-click the script
# =============================================================================

PDF_DATE_RE = re.compile(
    r"^D:(?P<Y>\d{4})(?P<m>\d{2})?(?P<d>\d{2})?(?P<H>\d{2})?(?P<M>\d{2})?(?P<S>\d{2})?"
    r"(?P<tz>Z|[+\-]\d{2}'?\d{2}')?$"
)

def human_size(n: int) -> str:
    for unit in ["B","KB","MB","GB","TB"]:
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit=="B" else f"{n:.1f} {unit}"
        n //= 1024
    return "?"

def parse_pdf_date(s: str) -> Optional[datetime]:
    if not s:
        return None
    s = s.strip()
    m = PDF_DATE_RE.match(s)
    if not m:
        s2 = s[2:] if s.startswith("D:") else s
        s2 = re.sub(r"[^0-9]", "", s2)
        if len(s2) >= 4:
            try:
                y = int(s2[0:4])
                mo = int(s2[4:6]) if len(s2) >= 6 else 1
                d = int(s2[6:8]) if len(s2) >= 8 else 1
                H = int(s2[8:10]) if len(s2) >= 10 else 0
                M = int(s2[10:12]) if len(s2) >= 12 else 0
                S = int(s2[12:14]) if len(s2) >= 14 else 0
                return datetime(y, mo, d, H, M, S)
            except Exception:
                return None
        return None

    g = m.groupdict()
    try:
        y = int(g["Y"]); mo = int(g.get("m") or 1); d = int(g.get("d") or 1)
        H = int(g.get("H") or 0); M = int(g.get("M") or 0); S = int(g.get("S") or 0)
        return datetime(y, mo, d, H, M, S)
    except Exception:
        return None

def load_reader_from_disk(path: Path) -> Tuple[Optional[PdfReader], Optional[bool], Optional[str]]:
    """Return (reader, was_encrypted, error). Reader is decrypted if needed."""
    try:
        data = path.read_bytes()
    except Exception as e:
        return None, None, f"read error: {e}"

    print(f"  - Reading {path.name} ({human_size(len(data))})", flush=True)

    bio = io.BytesIO(data)
    try:
        reader = PdfReader(bio)
    except Exception as e:
        return None, None, f"open error: {e}"

    was_encrypted = bool(getattr(reader, "is_encrypted", False))
    if was_encrypted:
        print("    ↳ File is encrypted. Trying shared password…", flush=True)
        try:
            ok = reader.decrypt(PASSWORD)
            # pypdf may return 0/False on failure, or None even if ok; probe metadata as a sanity check
            try:
                _ = reader.metadata
            except Exception:
                if ok in (0, False):
                    return None, True, "cannot decrypt with provided password"
        except Exception:
            # Try constructor with password as fallback
            try:
                reader = PdfReader(io.BytesIO(data), password=PASSWORD)  # type: ignore[arg-type]
                _ = reader.metadata
            except Exception:
                return None, True, "cannot decrypt with provided password"
        print("    ↳ Decryption OK.", flush=True)
    else:
        print("    ↳ Not encrypted.", flush=True)

    return reader, was_encrypted, None

def pick_date(reader: PdfReader, path: Path) -> Tuple[datetime, str]:
    """Return (date, source_str) where source_str is 'CreationDate', 'ModDate', or 'file mtime'."""
    source = "file mtime"
    try:
        meta = reader.metadata or {}
    except Exception:
        meta = {}
    c = meta.get("/CreationDate") if isinstance(meta, dict) else None
    m = meta.get("/ModDate") if isinstance(meta, dict) else None
    for label, s in (("CreationDate", c), ("ModDate", m)):
        if isinstance(s, str):
            dt = parse_pdf_date(s)
            if dt:
                return dt, label
    return datetime.fromtimestamp(path.stat().st_mtime), source

@dataclass
class Item:
    path: Path
    when: datetime
    source: str
    reader: PdfReader
    pages: int

def main():
    print("="*70)
    print("PDF Unlock + Merge (verbose, PdfWriter)")
    print(f"Working folder: {Path.cwd()}")
    print(f"Shared password: {PASSWORD!r}")
    print(f"Output file: {OUTPUT_NAME}")
    print("="*70, flush=True)

    here = Path.cwd()
    all_files = list(here.iterdir())
    pdfs: List[Path] = [p for p in all_files if p.is_file() and p.suffix.lower() == ".pdf"]

    print(f"Found {len(all_files)} file(s) total, {len(pdfs)} PDF(s):", flush=True)
    for p in sorted(pdfs):
        try:
            size = human_size(p.stat().st_size)
        except Exception:
            size = "?"
        print(f"  • {p.name}  [{size}]", flush=True)

    if not pdfs:
        print("\nNo PDFs found in this folder. Make sure you run this script *inside* the folder with your PDFs.")
        if PAUSE_ON_EXIT:
            input("\nPress Enter to exit…")
        return

    items: List[Item] = []
    skipped: List[Tuple[str, str]] = []

    print("\nOpening & decrypting PDFs…", flush=True)
    for p in sorted(pdfs):
        try:
            reader, was_encrypted, err = load_reader_from_disk(p)
            if not reader:
                skipped.append((p.name, err or "unknown error"))
                print(f"    ↳ SKIP {p.name}: {err}", flush=True)
                continue

            try:
                pages = len(reader.pages)
            except Exception:
                pages = -1

            dt, src = pick_date(reader, p)
            print(f"    ↳ Date for sorting: {dt.isoformat(sep=' ', timespec='seconds')}  (source: {src})", flush=True)
            print(f"    ↳ Pages: {pages if pages>=0 else 'unknown'}", flush=True)

            items.append(Item(path=p, when=dt, source=src, reader=reader, pages=pages))
        except Exception as e:
            skipped.append((p.name, f"unexpected error: {e}"))
            print(f"    ↳ SKIP {p.name}: unexpected error\n{traceback.format_exc()}", flush=True)

    if not items:
        print("\nERROR: Could not open any PDFs.")
        if skipped:
            print("Details of skipped files:")
            for name, reason in skipped:
                print(f"  - {name}: {reason}")
        if PAUSE_ON_EXIT:
            input("\nPress Enter to exit…")
        return

    # Sort oldest → newest
    print("\nSorting PDFs by date (CreationDate → ModDate → file mtime)…", flush=True)
    items.sort(key=lambda x: x.when)

    print("Order to merge:", flush=True)
    for i, it in enumerate(items, 1):
        print(f" {i:2d}. {it.path.name}  ({it.when.isoformat(sep=' ', timespec='seconds')}, {it.source})", flush=True)

    # Merge with PdfWriter (pypdf 5+)
    writer = PdfWriter()
    print("\nMerging with PdfWriter…", flush=True)
    total_pages = 0
    for idx, it in enumerate(items, 1):
        try:
            print(f"  [{idx}/{len(items)}] append {it.path.name}", flush=True)
            for page in it.reader.pages:
                writer.add_page(page)
                total_pages += 1
        except Exception as e:
            skipped.append((it.path.name, f"append error: {e}"))
            print(f"    ↳ SKIP during merge {it.path.name}: {e}", flush=True)

    out_path = Path(OUTPUT_NAME)
    with out_path.open("wb") as f:
        writer.write(f)
    print(f"\nDONE: wrote '{out_path.name}' in {Path.cwd()}  (pages: {total_pages})", flush=True)

    if skipped:
        print("\nSome files were skipped:", flush=True)
        for name, reason in skipped:
            print(f"  - {name}: {reason}", flush=True)

    if PAUSE_ON_EXIT:
        input("\nPress Enter to exit…")

if __name__ == "__main__":
    main()
