#!/usr/bin/env python3
"""Check that a copy of the unsigned dev definitions is usable by the tested firmware.

The firmware rejects definitions older than its minimum data version, which comes from
common/defs/ethereum/released-definitions-timestamp.json. Since the dev definitions are
only deployed on demand, they go stale whenever that timestamp moves past them.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import click

from trezorlib import definitions

ROOT = Path(__file__).resolve().parents[2]
TIMESTAMPS_FILE = (
    ROOT / "common" / "defs" / "ethereum" / "released-definitions-timestamp.json"
)
FORMAT_VERSION = "2"


def _utc(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()


@click.command()
@click.argument(
    "definitions_dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option("--chain-id", type=int, default=1, show_default=True)
def main(definitions_dir: Path, chain_id: int) -> None:
    """Check DEFINITIONS_DIR, a copy of `<deploy>/v2/definitions/`."""
    chain_dir = definitions_dir / "eth" / "chain-id" / str(chain_id)
    files = sorted(chain_dir.rglob("*.dat"))
    if not files:
        raise click.ClickException(
            f"No definitions in {chain_dir}. Did the download from S3 fail?"
        )
    if not (chain_dir / "network.dat").exists():
        raise click.ClickException(f"No network definition in {chain_dir}.")

    min_timestamp = int(
        datetime.fromisoformat(
            json.loads(TIMESTAMPS_FILE.read_text())[FORMAT_VERSION]
        ).timestamp()
    )
    kinds: Counter[str] = Counter()
    stale: list[Path] = []
    timestamps: list[int] = []
    for path in files:
        payload = definitions.Definition.parse(path.read_bytes()).payload
        if payload.version.decode() != FORMAT_VERSION:
            raise click.ClickException(
                f"{path}: format version {payload.version!r}, expected {FORMAT_VERSION}"
            )
        kinds[payload.data_type.name] += 1
        timestamps.append(payload.timestamp)
        if payload.timestamp < min_timestamp:
            stale.append(path)

    for kind, count in sorted(kinds.items()):
        click.echo(f"{kind}: {count}")
    click.echo(f"Timestamps: {_utc(min(timestamps))} .. {_utc(max(timestamps))}")
    click.echo(f"Firmware minimum: {_utc(min_timestamp)}")

    if stale:
        raise click.ClickException(
            f"{len(stale)} of {len(files)} dev definitions are older than the minimum "
            f"that the firmware accepts ({_utc(min_timestamp)}), e.g. {stale[0].name}. "
            "Re-run '[Deploy] unsigned dev firmware definitions' in trezor/definitions."
        )


if __name__ == "__main__":
    main()
