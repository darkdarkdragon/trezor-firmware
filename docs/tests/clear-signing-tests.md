# Clear-signing tests

Nightly UI tests of Ethereum clear signing (ERC-7730). They sign the test transactions of
the [clear-signing registry](https://github.com/ethereum/clear-signing-erc7730-registry)
on the emulator, with the display formats of the unsigned dev definitions of
[trezor/definitions](https://github.com/trezor/definitions). Only mainnet, only English,
on all core models.

They are separate from the [device tests](device-tests.md): they live in
`tests/clear_signing_tests/`, run in their own workflow
(`.github/workflows/core-clear-signing.yml`), and keep their own UI fixtures in
`tests/clear_signing_tests/fixtures.json`.

## Inputs

The test cases and the definitions must match, so both come from one trezor/definitions
commit: the one built by the last run of its "[Deploy] unsigned dev firmware
definitions" workflow (from any branch).

- **Definitions:** that deploy, `s3://dev.firmware.sldev.cz/unsigned/v2/definitions/`
  (from the internal network also `https://dev.firmware.sldev.cz/unsigned/v2/definitions/`).
- **Test cases:** the `registry/*/testsv2/calldata-*.tests.json` files of the registry
  commit that this trezor/definitions commit pins as a submodule.

So the tests change exactly when someone deploys the unsigned dev definitions.
`ci/clear_signing/resolve_inputs.py` finds the commits. It fails when the last deploy did
not succeed, since a failed deploy may have left the bucket half-synced.
`ci/clear_signing/check_dev_definitions.py` fails when the deployed definitions are older
than the minimum that the firmware accepts
(`common/defs/ethereum/released-definitions-timestamp.json`). In both cases, re-run the
deploy.

## What fails

Each registry case with a chain ID 1 transaction is one test. A case is skipped when the
dev definitions have no display format for its contract and function (the definitions
converter dropped it, or it is not deployed there), or when its calldata is longer than
the firmware clear-signs (6144 bytes).

A test fails when:

- the firmware falls back to blind signing (it shows the `confirm_data` screen),
- signing fails,
- its screens differ from `fixtures.json` or are not there yet (`UI_FAILED`, `UI_MISSING`),
- a recorded test no longer runs, e.g. because a display format disappeared.

The registry's `expected` texts (intent, labels and values) are also looked up on the
screens, but a text that is not found is only reported: the firmware formats some values
differently.

## Results

The summary of the workflow run has, per model, the counts and links to the
[UI report](ui-tests.md), and lists the skipped cases, the failures, and the expected
texts that were not found. The per-case results (screens' texts, ButtonRequests) are in
the `clear-signing-results-<model>` artifacts.

To accept the screens of a run, update the fixtures from it on a branch, and open a pull
request. A new deploy of the dev definitions usually needs this.

```sh
make -C core clear_signing_fixtures_update RUN=<run id>
```

## Running locally

From the internal network, the dev definitions can be used by their URL. Check out the
registry at the commit from `resolve_inputs.py`:

```sh
ci/clear_signing/resolve_inputs.py   # prints registry_sha
git clone --filter=blob:none --sparse https://github.com/ethereum/clear-signing-erc7730-registry /tmp/registry
git -C /tmp/registry sparse-checkout set --no-cone '/registry/*/testsv2/'
git -C /tmp/registry checkout <registry_sha>

export TREZOR_CLEAR_SIGNING_REGISTRY=/tmp/registry
export TREZOR_CLEAR_SIGNING_DEFINITIONS=https://dev.firmware.sldev.cz/unsigned/v2/definitions/
```

Then, with an emulator built with debuglink (e.g. `xtask build firmware --emulator -m T3W1 -p test`):

```sh
# a few cases against a temporary emulator
TREZOR_UI_FIXTURES=tests/clear_signing_tests/fixtures.json \
  ./core/emu.py -h -t -q -c pytest tests/clear_signing_tests -k 1inch --ui=test --lang=en
# all cases, like CI
make -C core test_emu_clear_signing_ui
# record all cases into tests/clear_signing_tests/fixtures.json
make -C core test_emu_clear_signing_ui_record
```

Always set `TREZOR_UI_FIXTURES` when running these tests with `--ui`, otherwise their
screens go to `tests/ui_tests/fixtures.json`. The make targets do it.
