#!/bin/sh
# Publish this prepared branch to the owner's fork without overwriting main.
set -eu
cd "$(dirname "$0")/.."
expected_owner=matzem79
repo_name=home-assistant-fiftyfive
target_repo="$expected_owner/$repo_name"
current_owner=$(gh api user --jq .login)
if [ "$current_owner" != "$expected_owner" ]; then
    echo "Expected GitHub account $expected_owner, got $current_owner. Stop." >&2
    exit 1
fi
if [ -n "$(git status --porcelain)" ]; then
    echo 'Commit or stash local changes before publishing.' >&2
    exit 1
fi
if ! gh repo view "$target_repo" --json nameWithOwner >/dev/null 2>&1; then
    gh repo fork pimhofstee/home-assistant-fiftyfive --clone=false
fi
if git remote get-url own-fork >/dev/null 2>&1; then
    actual_remote=$(git remote get-url own-fork)
    if [ "$actual_remote" != "https://github.com/$target_repo.git" ]; then
        echo 'Remote own-fork points somewhere else. Stop.' >&2
        exit 1
    fi
else
    git remote add own-fork "https://github.com/$target_repo.git"
fi
# Never force-push. Preserve any existing main branch and its history.
git push own-fork HEAD:refs/heads/meter-counter
# HACS should install the modified integration from the fork's default branch.
gh repo edit "$target_repo" --default-branch meter-counter
git ls-remote own-fork refs/heads/meter-counter
printf '\nPublished: https://github.com/%s/tree/meter-counter\n' "$target_repo"
