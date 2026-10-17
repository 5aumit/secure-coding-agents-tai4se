#!/usr/bin/env python3
"""Fetch the immutable released artifact into ignored benchmark storage."""

import hashlib
import sys
from pathlib import Path
import urllib.request
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from benchmarks.issuetrojan.data import ARCHIVE_SHA256, ZENODO_RECORD

URL = (
    f"https://zenodo.org/api/records/{ZENODO_RECORD}/files/issuetrojanbench.zip/content"
)
SHA256 = ARCHIVE_SHA256


def main():
    destination = Path("benchmarks/issuetrojan-data")
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / "artifact.zip"
    content = urllib.request.urlopen(URL, timeout=60).read()
    if hashlib.sha256(content).hexdigest() != SHA256:
        raise RuntimeError("Zenodo release checksum mismatch; refusing changed data")
    archive.write_bytes(content)
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            path = Path(member.filename)
            if not member.filename.startswith("issuetrojanbench/"):
                continue
            if path.is_absolute() or ".." in path.parts:
                raise RuntimeError("Unsafe archive path")
            bundle.extract(member, destination)
    print("Verified release extracted to", destination)


if __name__ == "__main__":
    main()
