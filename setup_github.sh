#!/bin/bash
# Run this once from inside the silent-patient-pool-finder folder
# Usage: bash setup_github.sh <YOUR_GITHUB_TOKEN> <YOUR_GITHUB_USERNAME>

set -e

TOKEN=$1
USERNAME=$2

if [ -z "$TOKEN" ] || [ -z "$USERNAME" ]; then
  echo "Usage: bash setup_github.sh <token> <github_username>"
  exit 1
fi

echo "→ Creating GitHub repo..."
curl -s -X POST \
  -H "Authorization: token $TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/user/repos \
  -d "{\"name\":\"silent-patient-pool-finder\",\"description\":\"Multi-signal inference engine to identify undiagnosed chronic-disease patient pools\",\"private\":false,\"auto_init\":false}" \
  | python3 -c "import sys,json; r=json.load(sys.stdin); print('Repo created:', r.get('html_url', r.get('message','check output')))"

echo "→ Initialising git..."
git init
git add .
git commit -m "Initial commit: architecture, README, repo structure"
git branch -M main
git remote add origin https://$TOKEN@github.com/$USERNAME/silent-patient-pool-finder.git
git push -u origin main

echo ""
echo "✓ Done — repo live at: https://github.com/$USERNAME/silent-patient-pool-finder"

# Remove this script after use (token was passed as arg, not stored in file)
rm -- "$0"
