#!/usr/bin/env python3
"""Summarize the nightly clear-signing test results as Markdown, for $GITHUB_STEP_SUMMARY."""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import click

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.clear_signing_tests.registry import (  # noqa: E402
    definitions_source,
    load_cases,
    read_results,
)

JOB = "core_clear_signing_test"
LANG = "en"
REPORT_URL = "https://data.trezor.io/dev/firmware/ui_report/{run}/{model}-{lang}-{job}-{page}.html"
MAX_LINES = 300


def _short(sha: str | None) -> str:
    return f"`{sha[:10]}`" if sha else "?"


def _inputs_line(inputs: dict) -> str:
    definitions_sha = inputs.get("definitions_sha")
    definitions = f"[{_short(definitions_sha)}](https://github.com/trezor/definitions/commit/{definitions_sha})"
    if inputs.get("definitions_ref"):
        definitions = f"`{inputs['definitions_ref']}` @ {definitions}"
    if inputs.get("deploy_run_url"):
        definitions += (
            f", [deployed {inputs['deployed_at']}]({inputs['deploy_run_url']})"
        )
    registry_sha = inputs.get("registry_sha")
    registry = f"[{_short(registry_sha)}](https://github.com/{inputs.get('registry_repo')}/tree/{registry_sha})"
    return f"Definitions: {definitions} · Registry: {registry}"


def _capped(lines: list[str]) -> list[str]:
    if len(lines) <= MAX_LINES:
        return lines
    rest = len(lines) - MAX_LINES
    return lines[:MAX_LINES] + [f"\n… and {rest} more, see the results artifacts."]


@click.command()
@click.option(
    "--inputs",
    "inputs_file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
)
@click.option(
    "--registry",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    required=True,
)
@click.option(
    "--definitions", required=True, help="Copy or URL of the dev definitions."
)
@click.option(
    "--results",
    "results_dir",
    type=click.Path(file_okay=False, path_type=Path),
    required=True,
)
@click.option("--run-id", required=True)
@click.option(
    "--models", "models_json", required=True, help="Tested models as a JSON list."
)
def main(
    inputs_file: Path,
    registry: Path,
    definitions: str,
    results_dir: Path,
    run_id: str,
    models_json: str,
) -> None:
    inputs = json.loads(inputs_file.read_text())
    models: list[str] = json.loads(models_json)
    cases = load_cases(registry, definitions_source(definitions))
    to_run = [case for case in cases if not case.skip_reason]
    results = read_results(results_dir) if results_dir.exists() else {}

    print("## Clear-signing registry tests\n")
    print(_inputs_line(inputs) + "\n")
    print(
        f"{len(cases)} mainnet cases: {len(to_run)} run on each model, "
        f"{len(cases) - len(to_run)} skipped.\n"
    )

    print(
        "| Model | Clear-signed | Blind-signed | Error | Not run | Text not found | UI report |"
    )
    print("|---|---:|---:|---:|---:|---:|---|")
    problems: dict[str, list[str]] = defaultdict(
        list
    )  # test_id -> ["T3W1: blind", ...]
    not_found: dict[
        str, tuple[list[str], list[str]]
    ] = {}  # test_id -> (models, missing)
    for model in models:
        model_results = results.get(model, {})
        counts: Counter[str] = Counter()
        for case in to_run:
            result = model_results.get(case.test_id)
            status = result["status"] if result else "not run"
            counts[status] += 1
            if status == "clear_signed":
                if result and (missing := result.get("missing")):
                    counts["text not found"] += 1
                    entry = not_found.setdefault(case.test_id, ([], missing))
                    entry[0].append(model)
            else:
                detail = (result or {}).get("message", "")
                problems[case.test_id].append(f"{model}: {status} {detail}".strip())
        links = " · ".join(
            f"[{name}]({REPORT_URL.format(run=run_id, model=model, lang=LANG, job=JOB, page=page)})"
            for name, page in (
                ("report", "index"),
                ("differing screens", "differing_screens"),
            )
        )
        print(
            f"| {model} | {counts['clear_signed']} | {counts['blind']} | {counts['error']} "
            f"| {counts['not run']} | {counts['text not found']} | {links} |"
        )

    print(
        "\nThe UI report compares the screens with `tests/clear_signing_tests/fixtures.json`. "
        "To accept them, run `make -C core clear_signing_fixtures_update RUN="
        f"{run_id}` on a branch and open a pull request.\n"
    )

    skipped = Counter(case.skip_reason for case in cases if case.skip_reason)
    print(f"<details><summary>Skipped cases ({sum(skipped.values())})</summary>\n")
    print("| Reason | Cases |\n|---|---:|")
    for reason, count in skipped.most_common():
        print(f"| {reason} | {count} |")
    print("\n</details>\n")

    print(
        f"<details><summary>Blind-signed, failed or not run ({len(problems)})</summary>\n"
    )
    print(
        "\n".join(
            _capped(
                [
                    f"- `{test_id}`: {'; '.join(lines)}"
                    for test_id, lines in sorted(problems.items())
                ]
            )
        )
    )
    print("\n</details>\n")

    print(
        f"<details><summary>Clear-signed, but expected text not found on screen "
        f"({len(not_found)})</summary>\n"
    )
    print(
        "The registry's `expected` texts that no page showed. The firmware formats some "
        "values differently, so this is for review, not a failure.\n"
    )
    print(
        "\n".join(
            _capped(
                [
                    f"- `{test_id}` ({', '.join(found_models)}): {'; '.join(missing)}"
                    for test_id, (found_models, missing) in sorted(not_found.items())
                ]
            )
        )
    )
    print("\n</details>")


if __name__ == "__main__":
    main()
