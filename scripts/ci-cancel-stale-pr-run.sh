#!/usr/bin/env bash
set -uo pipefail

# Cancel the current workflow run if the PR was closed or converted back to draft
# between queuing and job start.

if ! state_line=$(gh pr view "$PR_NUMBER" --repo "$GITHUB_REPOSITORY" --json state,isDraft --jq '"\(.state) \(.isDraft)"'); then
  echo "::warning::cannot read PR #$PR_NUMBER state, running anyway"
  exit 0
fi

# Strip CR in case gh outputs CRLF on Windows runners.
state_line=${state_line//$'\r'/}
read -r pr_state is_draft <<< "$state_line"

# Cancel only on a clear answer; anything unexpected runs CI anyway.
if [ "$pr_state" != "CLOSED" ] && [ "$pr_state" != "MERGED" ] && [ "$is_draft" != "true" ]; then
  exit 0
fi

echo "Cancelling run $GITHUB_RUN_ID: PR #$PR_NUMBER is state=$pr_state isDraft=$is_draft"
if ! gh run cancel "$GITHUB_RUN_ID" --repo "$GITHUB_REPOSITORY"; then
  echo "::warning::cannot cancel run $GITHUB_RUN_ID, running anyway"
  exit 0
fi

# Wait for GitHub Actions to terminate the job after cancellation is requested.
sleep 120
echo "::error::cancel requested but the job is still running"
exit 1
