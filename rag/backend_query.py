# SPDX-FileCopyrightText: 2024 NOI Techpark <digital@noi.bz.it>
#
# SPDX-License-Identifier: AGPL-3.0-or-later

# ------------------------------------------------------------------------------
# Chat with the backend.
# This code performs the same operations on the LLM as query.py,
# except it communicates with the web backend instead with the user directly.
#
# See query.py for details about the interaction with the LLM.
# ------------------------------------------------------------------------------

import time
import sys
import re
import requests
from datetime import datetime


from librag import *
from libpg import *

from llama_cpp import Llama


def log(msg: str):
    print(str(datetime.now()) + " " + msg)


# --- load configuration ---

try:
    file = open("backend.json", "r")
    parameters = json.load(file)
    file.close()
except FileNotFoundError:
    print("ERROR: cannot read configuration file.")
    sys.exit(1)

endpoint = parameters["endpoint"]
preshared_secret = parameters["preshared_secret"]

# --- load LLM ---

llm = Llama(
    model_path="../../mistral-7b-instruct-v0.2.Q5_K_M.gguf",
    chat_format="mistral-instruct",
    n_ctx=32768,
    n_gpu_layers=-1,  # -1 use all available GPU cores, or 0 run on CPU only
    seed=0,
    verbose=False
)


# --- main loop ---

while True:

    # --- poll for a new job to process ---

    log("polling for new job...")

    connection_timeout = 2.0

    claim = {}

    while True:

        try:
            response = requests.get(endpoint + "/claim_job?secret=" + preshared_secret)
        except requests.exceptions.ConnectionError:
            log("sleep %.0f s after ConnectionError" % connection_timeout)
            time.sleep(connection_timeout)
            if connection_timeout < 32:
                connection_timeout *= 2
            continue

        connection_timeout = 2.0

        if response.text.strip() == "{}":
            time.sleep(1.0)
            continue

        try:
            claim = json.loads(response.text)
        except:
            log("cannot parse JSON response from claim_job")
            time.sleep(5.0)
            continue
        break

    conversation = json.loads(claim.get("conversation"))
    conversation_llm = json.loads(claim.get("conversation_llm"))
    source = json.loads(claim.get("source"))
    unique_id = claim.get("uuid")

    log("claimed new job uuid = %s" % unique_id )

    if not (len(conversation_llm) == 0 and len(conversation) == 1) and not (len(conversation_llm) > 1 and len(conversation_llm) == len(conversation)):
        log("inconsistent length of conversation arrays (%d, %d) - skipping" % (len(conversation_llm), len(conversation)))
        continue

    question = conversation[len(conversation) - 1]

    # --- search ---

    cursor = open_cursor()
    top = 5
    if len(conversation_llm) == 0:
        log("first question - searching...")
        res = search(cursor, top, question)
    else:
        log("follow-up question - searching...")
        res = search(cursor, top, conversation[len(conversation) - 2] + "\n" + question)

    log("")
    log("embedding vector search - top %d chunks:" % top)
    log("distance   tag  offset  file_name")
    log("--------   ---  ------  ---------")
    mark = " <-- will be added to context"
    for r in res:
        log("%.5f %6s %7d  %s%s" % (r["distance"], r["tag"], r["start_pos"], r["file_name"], mark))
        mark = ""
    log("")

    if len(res) > 0:
        context = res[0]["file_body"]
        source.append("Source: document %s (tag: %s) at offset %d chars." % (res[0]["file_name"], res[0]["tag"], res[0]["start_pos"]))
    else:
        context = ""
        log("zero results from DB, using empty context")

    # --- LLM input ---

    if len(conversation_llm) == 0:

        log("first question - inferring...")

        prompt = f"""
Answer the question based on the context below.
If the question can't be answered based on the context, just say \"I don't know\".
---
Context:
{context}

---
Question:
{question}
"""

        conversation_llm = [
                  {"role": "system", "content": "You are an assistant who answers questions."},
                  {"role": "user",   "content": prompt}
        ]

    else:

        log("follow-up question - inferring...")

        prompt = f"""
{question}

Below is more context that might be useful or not.
If the context is irrelevant, ignore it silently. Otherwise use it to refine your answer.
---
Context:
{context}
"""

        conversation_llm.append({"role": "user", "content": prompt})

    # --- LLM output ---

    try:
        t0 = time.time()
        result = llm.create_chat_completion(
            messages=conversation_llm
        )
        t1 = time.time()
        answer = result["choices"][0].get("message").get("content")
    except Exception as e:
        answer = "[LLM exception, context length might be exceeded, please start a new session]"

    conversation_llm.append({"role": "assistant", "content": answer})
    conversation.append(answer)

    log("LLM output in %6.3fs" % (t1-t0))
    log("")

    post_data = {
        "secret": preshared_secret,
        "uuid": unique_id,
        "conversation_llm": json.dumps(conversation_llm),
        "conversation": json.dumps(conversation),
        "source": json.dumps(source)
    }
    response = requests.post(endpoint + "/finish_job", data=post_data)
    log("post results: %d %s" % (response.status_code, response.text))


    log("--------------------------------------------------------------------------")
    print(conversation_llm)
    log("--------------------------------------------------------------------------")
    print(conversation)
    log("--------------------------------------------------------------------------")
