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
#     this script, see the comments there
#
#   - the embedding model is bge-m3 (license: MIT), the model has
#     been downloaded automatically when 'load.py' was run (see
#     get_embedding_model() in 'librag.py')
#
#     ref. model: https://huggingface.co/BAAI/bge-m3
#
#   - the LLM is Mistral-7B-Instruct-v0.2 (license: Apache 2), please
#     download the model in GGUF format manually and place it in $HOME:
#     curl -LO https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/resolve/main/mistral-7b-instruct-v0.2.Q5_K_M.gguf
#
#     ref. original model: https://huggingface.co/mistralai/Mistral-7B-Instruct-v0.2
#     ref. quantized versions: https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF
#
# Some sample questions:
#
#   Wie kann ich ein Hotel als familienfreundlich taggen?
#   Come posso ottenere informazioni sui mercatini di Natale di Bolzano?
#   Who do I need to contact to obtain a user account for making authenticated requests to the Open Data Hub?
# ------------------------------------------------------------------------------

import time
import sys
import re
from pprint import pprint

from librag import *
from libpg import *

from llama_cpp import Llama

# --- load LLM ---

llm = Llama(
    model_path="../../mistral-7b-instruct-v0.2.Q5_K_M.gguf",
    chat_format="mistral-instruct",
    n_ctx=8192,
    n_gpu_layers=-1,  # -1 use all available GPU cores, or 0 run on CPU only
    seed=0,
    verbose=False
)


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

        cursor = open_cursor()
        top = 5
        if iteration == 1:
            res = search(cursor, top, question)
        else:
            res = search(cursor, top, last_message.get("content") + "\n" + question)

        print("{meta}")
        print("{meta} embedding vector search - top %d chunks:" % top)
        print("{meta} distance   tag  offset  file_name")
        print("{meta} --------   ---  ------  ---------")
        mark = " <-- will be added to context"
        for r in res:
            print("{meta} %.5f %6s %7d  %s%s" % (r["distance"], r["tag"], r["start_pos"], r["file_name"], mark))
            mark = ""

        if len(res) < top:
            print("ERROR: not enough results.")
            sys.exit(1)

        print("{meta} please wait...")

        # --- LLM input ---

        context = res[0]["file_body"]

        if iteration == 1:

            # first iteration

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

            conversation = [
                      {"role": "system", "content": "You are an assistant who answers questions."},
                      {"role": "user",   "content": prompt}
            ]

        else:

            # follow-up iteration

            prompt = f"""
    {question}
    
    Below is more context that might be useful or not.
    If the context is irrelevant, ignore it silently. Otherwise use it to refine your answer.
    ---
    Context:
    {context}
    """

            # conversation.append()
            conversation.append(last_message)
            conversation.append({"role": "user", "content": prompt})

        # debug print
        # print("***")
        # print("LLM input:")
        # pprint(conversation)
        # print("***")

        # --- LLM output ---

        t0 = time.time()
        result = llm.create_chat_completion(
              messages=conversation
        )
        t1 = time.time()

        last_message = result["choices"][0].get("message")

        print("{meta} LLM output in %6.3fs" % (t1-t0))
        print("{meta} usage: %s" % result["usage"])
        print("{meta}")
        print(last_message.get("content"))

        # debug print
        # print("***")
        # print("LLM OUTPUT:")
        # pprint(result)
        # print("***")
