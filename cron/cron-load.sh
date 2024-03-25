#!/bin/bash

{
  cd $HOME/stuart-chatbot || exit 1
  source .venv/bin/activate
  cd rag || exit 1
  echo $(date) "START"
  python load.py
  echo $(date) "STOP"
  echo
} >> $HOME/cron-load.log 2>&1

