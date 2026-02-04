#!/bin/bash
# ------------------------------------------------------------------------------
# Scrape the Open Data Hub repository Readme files.
#
# Notes:
#   - the URLs are hand-picked and read from 'scrape_readme_urls.txt'
#   - it will get the file from the first branch that exists
#     in the sequence: main, master, development
#   - the script tries to download the README.md from each repository
#     and save it to '../data_readme'
# ------------------------------------------------------------------------------

URLS_FILE=scrape_readme_urls.txt

if [ ! -r "$URLS_FILE" ]; then
  echo "ERROR: $0: cannot read '$URLS_FILE'"; exit 1;
fi

TEMP_DIR=$(mktemp -d)

function cleanup {
  rm -rf "$TEMP_DIR"
}
trap cleanup EXIT

URLS=$(cat scrape_readme_urls.txt)

cd "$TEMP_DIR" || { echo "ERROR: $0: cannot cd to temp dir"; exit 1; }

NUM=0
BAD=0
while read -r URL; do
  ((NUM++))
  NAME=$(echo "$URL" | cut -d '/' -f 5)
  NAME="$NAME".md
  SUCCESS=0
  for BRANCH in main master development; do
    TRYURL=${URL/development/$BRANCH}
    curl -f -L "$TRYURL" > "$NAME" 2>/dev/null
    if [ $? -eq 0 ]; then
      SUCCESS=1
      break
    fi
  done
  if [ $SUCCESS -eq 0 ]; then
      ((BAD++))
      echo "WARNING: $0: failed to get readme for ${NAME/.md/}"
      rm "$NAME"
  fi
done <<< "$URLS"

((GOOD=NUM-BAD))

cd - || { echo "ERROR: $0: cannot cd back"; exit 1; }
rm -f ../data_readme/*md
cp "$TEMP_DIR"/*md ../data_readme/ || { echo "ERROR: $0: cannot cp *.md files"; exit 1; }

echo "$GOOD / $NUM readme files scraped"