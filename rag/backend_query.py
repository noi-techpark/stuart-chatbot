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
import json
from datetime import datetime


from librag import *
from libpg import *


def log(msg: str):
    print(str(datetime.now()) + " " + msg)


# --- read configuration files ---

try:
    file = open("backend.json", "r")
    parameters = json.load(file)
    file.close()
except FileNotFoundError:
    print("ERROR: cannot read configuration file.")
    sys.exit(1)

stuart_web_endpoint = parameters["endpoint"]
preshared_secret = parameters["preshared_secret"]

try:
    file = open("secrets_llm_endpoint.json", "r")
    llm_service_endpoint = json.load(file)
    file.close()
except FileNotFoundError:
    print("ERROR: cannot open file: secrets_llm_endpoint.json.")
    sys.exit(1)


# --- main loop ---

while True:

    # --- poll for a new job to process ---

    log("polling for new job...")

    connection_timeout = 2.0

    claim = {}

    while True:

        try:
            response = requests.get(stuart_web_endpoint + "/claim_job?secret=" + preshared_secret)
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

    # use the first top_n results out of top_max retrieved
    # the default is top_n = 1, top_max = 5

    top_n = 1
    top_max = 5

    cursor = open_cursor()
    if len(conversation_llm) == 0:
        log("first question - searching...")
        res = search(cursor, top_max, question)
    else:
        log("follow-up question - searching...")
        res = search(cursor, top_max, conversation[len(conversation) - 2] + "\n" + question)

    top_max = min(len(res), top_max)
    top_n = min(len(res), top_n, top_max)

    log("")
    log("embedding vector search - top %d chunks:" % top_max)
    log("distance   tag  offset  file_name")
    log("--------   ---  ------  ---------")
    for i in range(0, top_max):
        if i < top_n:
            mark = " <-- will be added to context"
        else:
            mark = ""
        log("%.5f %6s %7d  %s%s" % (res[i]["distance"], res[i]["tag"], res[i]["start_pos"], res[i]["file_name"], mark))

    log("")

    # --- LLM input ---

    if len(res) > 0:

        context = ""
        source_str = "Source: "
        for i in range(0, top_n):
            context = context + res[i]["file_body"]
            source_str = source_str + "Source: document %s (tag: %s) at offset %d chars." % (res[0]["file_name"], res[0]["tag"], res[0]["start_pos"])

        source.append(source_str)

    else:

        context = ""
        log("zero results from DB, using empty context")

    if len(conversation_llm) == 0:

        # first iteration

        log("first question - inferring...")

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

        conversation_llm = [
                  {"role": "system", "content": "You are an assistant who answers questions."},
                  {"role": "user",   "content": prompt}
        ]

    else:

        # follow-up iteration

        log("follow-up question - inferring...")

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

        conversation_llm.append({"role": "user", "content": prompt})

    # --- LLM output ---

    t0 = time.time()

    try:

        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + llm_service_endpoint.get("api_key")
        }
        data = {
            "model": llm_service_endpoint.get("model"),
            "messages": conversation_llm
        }
        response = requests.post(llm_service_endpoint.get("endpoint"), headers=headers, json=data)
        result = response.json()
        answer = result["choices"][0].get("message").get("content")

    except Exception as e:

        answer = "[LLM exception, context length might be exceeded, please start a new session]"

    t1 = time.time()

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
    response = requests.post(stuart_web_endpoint + "/finish_job", data=post_data)
    log("post results: %d %s" % (response.status_code, response.text))


    log("--------------------------------------------------------------------------")
    print(conversation_llm)
    log("--------------------------------------------------------------------------")
    print(conversation)
    log("--------------------------------------------------------------------------")
