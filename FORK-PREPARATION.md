# GitHub fork preparation

Prepared destination: **matzem79/home-assistant-fiftyfive**. The owner was
inferred from the local GitHub CLI account configuration. The implementation is committed locally. GitHub could not be reached from
this environment, so no remote repository creation, push or release has been
confirmed.

The working branch is `meter-counter`, based on upstream's
`feature/add-2fa-support` at `5000d90f307ce7476f1e5f08965cac959e70faf2`.
The candidate version is **0.12.1**. Manifest metadata, 2FA setup help and the
update checker point to the prepared destination. The component domain is
still `fiftyfive`; existing config entries and entity IDs can be reused.

## Ready locally

- Implementation, 51 isolated tests, source-selection translations.
- Public README, external-meter guide, changelog and German verification record.
- Optional firmware snippet with no credentials or customer identifiers.
- Upstream license and history preserved.
- Tests workflow; inherited lint and hassfest/HACS workflows retained.

The local `script_from_ha` directory and app-analysis files are outside this Git
repository and are not part of the fork. No captured session cookies, passwords,
API keys or tokens have been added by this change.

## Publish from a terminal with GitHub access

```sh
bash scripts/publish-fork.sh
```

The script checks the logged-in account is `matzem79`, requires a clean working
tree, reuses the owner's existing repository or creates its GitHub fork, and
pushes the current commit to `meter-counter` without force. It uses a separate
`own-fork` remote and leaves the existing upstream remote unchanged.

After a successful push it makes `meter-counter` the fork's default branch so
HACS downloads the modified integration. The fork's existing `main` branch is
preserved. No upstream pull request, release or tag is created. Check GitHub
Actions before creating a release from this branch.

The candidate version is 0.12.1. To publish it after review, create the release
`v0.12.1` from `meter-counter`, using `CHANGELOG.md` as release notes. The local
`fiftyfive-2fa-meter.zip` is outside the Git repository and is not automatically
uploaded.

GitHub API and SSH access failed during preparation because the host could not
be resolved/reached. Ruff could not be installed because PyPI access failed;
full lint and hassfest results are not claimed. All 51 local tests pass.
