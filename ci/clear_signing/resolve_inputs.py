#!/usr/bin/env python3
"""Resolve the inputs of the nightly clear-signing tests.

The tests run the ERC-7730 registry cases against the unsigned dev definitions. Both
must come from the same trezor/definitions commit: the one that the last run of its
"[Deploy] unsigned dev firmware definitions" workflow built (from any branch). The
registry is the submodule that this commit pins.

Writes the result as JSON, and as step outputs when $GITHUB_OUTPUT is set.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import click
import requests

DEFINITIONS_REPO = "trezor/definitions"
DEPLOY_WORKFLOW = "deploy-dev-definitions.yaml"
REGISTRY_SUBMODULE = "ethereum/clear-signing-erc7730-registry"
REGISTRY_REPO = "ethereum/clear-signing-erc7730-registry"


def _get(path: str) -> dict:
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    response = requests.get(
        f"https://api.github.com/{path}", headers=headers, timeout=30
    )
    response.raise_for_status()
    return response.json()


def _last_deploy() -> dict:
    runs = _get(
        f"repos/{DEFINITIONS_REPO}/actions/workflows/{DEPLOY_WORKFLOW}/runs?per_page=1"
    )["workflow_runs"]
    if not runs:
        raise click.ClickException(f"{DEFINITIONS_REPO} has no {DEPLOY_WORKFLOW} runs")
    run = runs[0]
    url = run["html_url"]
    # A run that did not finish may have left the bucket half-synced (`aws s3 sync --delete`).
    if run["status"] != "completed":
        raise click.ClickException(
            f"The last unsigned dev deploy is still {run['status']}: {url}"
        )
    if run["conclusion"] != "success":
        raise click.ClickException(
            f"The last unsigned dev deploy ended with '{run['conclusion']}', so the dev "
            f"definitions may be incomplete: {url}\nRe-run the deploy."
        )
    return {
        "definitions_sha": run["head_sha"],
        "definitions_ref": run["head_branch"],
        "deploy_run_url": url,
        "deployed_at": run["updated_at"],
    }


@click.command()
@click.option(
    "--definitions-sha",
    help="Use this trezor/definitions commit instead of the last unsigned dev deploy.",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Write the inputs as JSON to this file.",
)
def main(definitions_sha: str | None, output: Path | None) -> None:
    if definitions_sha:
        inputs = {
            "definitions_sha": definitions_sha,
            "definitions_ref": None,
            "deploy_run_url": None,
            "deployed_at": None,
        }
    else:
        inputs = _last_deploy()

    submodule = _get(
        f"repos/{DEFINITIONS_REPO}/contents/{REGISTRY_SUBMODULE}"
        f"?ref={inputs['definitions_sha']}"
    )
    if submodule.get("type") != "submodule":
        raise click.ClickException(
            f"{REGISTRY_SUBMODULE} is not a submodule at {inputs['definitions_sha']}"
        )
    inputs["registry_repo"] = REGISTRY_REPO
    inputs["registry_sha"] = submodule["sha"]

    text = json.dumps(inputs, indent=2)
    click.echo(text)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n")
    if github_output := os.environ.get("GITHUB_OUTPUT"):
        with open(github_output, "a") as f:
            for key in ("definitions_sha", "registry_sha"):
                f.write(f"{key}={inputs[key]}\n")


if __name__ == "__main__":
    main()
