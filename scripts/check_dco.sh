#!/usr/bin/env bash
# check_dco.sh — pre-push guard ensuring every commit has a DCO sign-off
set -euo pipefail

RED='\033[0;31m'
NC='\033[0m'

remote="$1"
url="$2"

EXIT_CODE=0

while read -r local_ref local_oid remote_ref remote_oid; do
    # Skip delete pushes
    if [ "$local_oid" = "0000000000000000000000000000000000000000" ]; then
        continue
    fi

    # Determine range: new branch vs update
    if [ "$remote_oid" = "0000000000000000000000000000000000000000" ]; then
        # New branch — check commits not on any remote branch
        range="$local_oid --not --remotes"
    else
        range="$remote_oid..$local_oid"
    fi

    # shellcheck disable=SC2086
    for commit in $(git rev-list $range 2>/dev/null); do
        if ! git log -1 --format='%B' "$commit" | grep -qE '^Signed-off-by: .+ <.+>'; then
            echo -e "${RED}ERROR: Commit $(git rev-parse --short "$commit") is missing a DCO sign-off:${NC}"
            git log -1 --format='  %h %s' "$commit"
            EXIT_CODE=1
        fi
    done
done

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "All commits must include: Signed-off-by: Name <email>"
    echo "To fix, amend with: git commit --amend  (and add the sign-off line)"
    echo "Or to skip this check: git push --no-verify"
fi

exit $EXIT_CODE
