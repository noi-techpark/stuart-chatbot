#!/bin/bash

{
  cd $HOME/stuart-chatbot || exit 1
  source .venv/bin/activate
  cd scrapers || exit 1
  echo $(date) "START"
  echo "*** wiki"
  bash scrape_wiki.sh 
  echo "*** readme"
  bash scrape_readme.sh 
  echo "*** rt"
  python scrape_rt.py
  echo $(date) "STOP"
  echo
} >> $HOME/cron-scrape.log 2>&1

