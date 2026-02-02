# SPDX-FileCopyrightText: 2024 NOI Techpark <digital@noi.bz.it>
#
# SPDX-License-Identifier: AGPL-3.0-or-later

# ------------------------------------------------------------------------------
# Interactive chat application.
# In a loop, prompt for user input and perform vector search, prompt
# the LLM using the user input and the top matching result from the
# search. In further iterations, include the LLM output in the search.
# Type 'q' to exit or 'r' to reset the conversation (forget the context).
#
# Note:
#
#   - you need to run 'load.py' to RAG you data before you can use
#     this script, see the comments there or the global README.md
#
#   - the embedding model is bge-m3 (license: MIT), the model has
#     been downloaded automatically when 'load.py' was run for the first time
#     (see get_embedding_model() in 'librag.py')
#
#     ref. model: https://huggingface.co/BAAI/bge-m3
#
#   - for inference, whatever model you configured in `secrets_llm_endpoint.json`
#     is used (see the global README.md for recommendations)
#
# If you have loaded the documents from ../data_examples, here are some questions you cn try:
#
#   What does gulp do?
#     # -> [explains some bogus software]
#   Wie heisst der blaue Elefant?
#     # -> Eli
#   Conosci un racconto di fantascienza? Di cosa parla?
#     # -> [talks about the-colony-on-xyris-9.txt]
#   Name the planets in the solar system!
#     # -> [there is a fictive planet named Fractulus...]
#   What's the name of the cat?
#     # -> [there is nothing about a cat, so it will say it doesn't know...]
# ------------------------------------------------------------------------------

import time
import sys
import re
import requests
import json

from librag import *
from libpg import *


# --- read endpoint info ---

try:
    file = open("secrets_llm_endpoint.json", "r")
    endpoint = json.load(file)
    file.close()
except FileNotFoundError:
    print("ERROR: cannot open file: secrets_llm_endpoint.json.")
    sys.exit(1)


# --- main loop ---

while True:

    iteration = 0
    last_message = {}
    conversation = []

    print("Stuart: You rang 🛎️ ?")
    print("Ask me anything or enter 'q' to exit. Enter 'r' to restart our conversation.")

    while True:

        iteration += 1

        # --- user input ---

        question = ""
        while re.fullmatch(r"\s*", question):
            question = input("> ")
            if question in ["q", "Q", "quit", "exit", r"\q"]:
                sys.exit(0)

        if question in ["r", "R", "reset", r"\r"]:
            break

        # --- search ---

        # use the first top_n results out of top_max retrieved
        # the default is top_n = 1, top_max = 5

        top_n = 1
        top_max = 5

        cursor = open_cursor()
        if iteration == 1:
            res = search(cursor, top_max, question)
        else:
            res = search(cursor, top_max, last_message.get("content") + "\n" + question)

        if len(res) < 1:
            print("ERROR: no results at all. Did you load some documents (load.py)?")
            sys.exit(1)

        top_max = min(len(res), top_max)
        top_n = min(len(res), top_n, top_max)

        print("{meta}")
        print("{meta} embedding vector search - top %d chunks:" % top_max)
        print("{meta} distance   tag  offset  file_name")
        print("{meta} --------   ---  ------  ---------")
        for i in range(0, top_max):
            if i < top_n:
                mark = " <-- will be added to context"
            else:
                mark = ""
            print("{meta} %.5f %6s %7d  %s%s" % (res[i]["distance"], res[i]["tag"], res[i]["start_pos"], res[i]["file_name"], mark))
            mark = ""

        print("{meta} please wait...")

        # --- LLM input ---

        context = ""
        for i in range(0, top_n):
            context = context + res[i]["file_body"]
        if iteration == 1:

            # first iteration

            prompt = (
f"""
Answer the question using only the context provided below. Respond in the same language as the question.
If the answer cannot be fully derived from the context, simply say \"I don't know\".

---
Question:
{question}

---
Context:
{context}
""")

            conversation = [
                      {"role": "system", "content": "You are an assistant who answers questions."},
                      {"role": "user",   "content": prompt}
            ]

        else:

            # follow-up iteration

            prompt = (
f"""
Answer the follow-up question based on the context of this conversation. Respond in the same language as the question.
If the answer cannot be fully derived from the context, simply say \"I don't know\".

---
Question:
{question}

---
Here is additional context.
If it is not relevant, ignore it. Otherwise, use it to refine your answer:
{context}
""")

            conversation.append(last_message)
            conversation.append({"role": "user", "content": prompt})

        # --- LLM output ---

        # debug print the message the LLM sees
        # print("DEBUG message:")
        # print(json.dumps(conversation))

        t0 = time.time()

        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + endpoint.get("api_key")
        }
        data = {
            "model": endpoint.get("model"),
            "messages": conversation
        }

        response = requests.post(endpoint.get("endpoint"), headers=headers, json=data)
        result = response.json()

        t1 = time.time()

        last_message = result.get("choices")[0].get("message")

        print("{meta} LLM output in %6.3fs" % (t1-t0))    # token usage is in result.get("usage")
        print("{meta}")
        print(last_message.get("content"))
