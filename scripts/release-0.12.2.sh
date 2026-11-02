#!/bin/sh
# Publish only after both workflows for the exact release commit pass.
set -eu
cd "$(dirname "$0")/.."
repo=matzem79/home-assistant-fiftyfive
if [ -n "$(git status --porcelain)" ]; then
    echo 'Working tree must be clean before release.' >&2
    exit 1
fi
release_commit=$(git rev-parse HEAD)
python3 -c 'import json; assert json.load(open("custom_components/fiftyfive/manifest.json"))["version"] == "0.12.2"'
gh repo edit "$repo" --enable-issues --add-topic home-assistant --add-topic hacs --add-topic ev-charging
git push own-fork HEAD:refs/heads/meter-counter
for workflow in validate.yml tests.yml; do
    run_id=$(gh run list --repo "$repo" --workflow "$workflow" --commit "$release_commit" --event push --limit 1 --json databaseId --jq '.[0].databaseId // empty')
    if [ -z "$run_id" ]; then
        echo "No $workflow run for $release_commit yet. Wait for GitHub to queue it, then rerun this script." >&2
        exit 1
    fi
    gh run watch "$run_id" --repo "$repo" --exit-status
    result=$(gh run view "$run_id" --repo "$repo" --json conclusion --jq .conclusion)
    if [ "$result" != success ]; then
        echo "$workflow did not pass. Release stopped." >&2
        exit 1
    fi
done
gh release create v0.12.2 frontend/wallbox-dashboard.zip \
    --repo "$repo" --target "$release_commit" \
    --title '0.12.2 – Energy correction and Wallbox dashboard' \
    --notes-file docs/releases/v0.12.2.md --latest
