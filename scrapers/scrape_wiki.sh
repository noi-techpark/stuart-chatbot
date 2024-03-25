#!/bin/bash
# ------------------------------------------------------------------------------
# Scrape the Open Data Hub wiki.
#
# Notes:
#   - wiki is at https://github.com/noi-techpark/odh-docs/wiki
#   - the script just git clones the repo and copies all .md files
#     except _Footer.md and _Sidebar.md to '../data_wiki'
# ------------------------------------------------------------------------------

TEMP_DIR=$(mktemp -d)

function cleanup {
  rm -rf "$TEMP_DIR"
}
trap cleanup EXIT

cd "$TEMP_DIR" || { echo "ERROR: $0: cannot cd to temp dir"; exit 1; }
git clone https://github.com/noi-techpark/odh-docs.wiki.git || { echo "ERROR: $0: cannot git clone"; exit 1; }
cd - || { echo "ERROR: $0: cannot cd back"; exit 1; }
rm -f ../data_wiki/*md
cp "$TEMP_DIR"/odh-docs.wiki/*md ../data_wiki/ || { echo "ERROR: $0: cannot cp *.md files"; exit 1; }
rm -f ../data_wiki/_Footer.md
rm -f ../data_wiki/_Sidebar.md

NUM=$(ls ../data_wiki/*md | wc -l)

echo "$NUM wiki files scraped"