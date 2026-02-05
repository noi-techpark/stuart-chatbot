#!/bin/bash

{
  cd $HOME/stuart-chatbot || exit 1
  source .venv/bin/activate
  cd scrapers || exit 1
  echo $(date) "START"
  echo "*** gh issues"
  python scrape_ghissues.py
  echo $(date) "STOP"
  echo
} >> $HOME/cron-scrape-ghissues.log 2>&1