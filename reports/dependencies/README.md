# Original RoCC dependency recovery

Source: https://doi.org/10.5281/zenodo.16260752 (official artifact).
File: `accfg-artifacts.repo.tar.gz`, 208836477 bytes.
Published MD5: `e58bd6e1f9d424bd80fd67536ce7ca04` (verified).
Archive SHA-256: `e4c241f84215954f031971c8f582d64cb713bd9f1716f721faeb7123d8a13365`.

The original `ibm/rocc-software` URL returned 404; the original target was not
available through the checked ucb-bar commit API. No replacement source is used.
Git objects were selected from the archive's
`.git/modules/gemmini-rocc-tests/modules/rocc-software/`, excluding hooks and configuration.
All selected members were checked again against the complete verified archive.

The 22313-byte bundle contains complete reachable history for
`fddb795a0b52e82f8f4ce9ead9b1428440a62ab0`, under `refs/heads/paper-restored`.
Bundle SHA-256: `df36c801ded194acf10e4f977a987e00f9d765154622dcf1e6f4320c6c42b6c3`.
`git fsck --full --no-reflogs` and `git bundle verify` passed.
The original license is included as `rocc-software.LICENSE`.

Run `python3 reports/scripts/restore_dependencies.py` from the project root.
The script verifies the bundle, preserves existing dirty/misaligned checkouts,
sets only the local RoCC submodule URL to the versioned bundle, and initializes
pinned dependencies. Neither `.gitmodules` nor any paper gitlink is changed.
The versioned bundle makes this original commit retrievable from the personal
Fork without depending on the unavailable IBM repository.
