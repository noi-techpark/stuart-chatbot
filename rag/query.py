# ------------------------------------------------------------------------------
# Accept user input as a single argument from the command line.
# Find and list top-matching chunks via vector search. Construct
# an LLM context using this information and run the LLM.
# Output the result.
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
# ------------------------------------------------------------------------------

import time
import sys
from pprint import pprint

from librag import *
from libpg import *

from llama_cpp import Llama

# --- user input ---

# some sample/default questions
# question = "Wie kann ich ein Hotel als familienfreundlich taggen?"
question = "Come posso ottenere informazioni sui mercatini di Natale di Bolzano?"
# question = "Who do I need to contact to obtain a user account for making authenticated requests to the Open Data Hub?"
if len(sys.argv) >= 2:
    question = sys.argv[1]
print("---")
print("user input:")
print(question)

# --- search ---

cursor = open_cursor()
top = 10
res = search(cursor, top, question)

print("---")
print("embedding vector search: top %d chunks:" % top)
print("distance tag   offset  file_name")
for r in res:
    print("%.4f %6s %7d  %s" % (r["distance"], r["tag"], r["start_pos"], r["file_name"]))

if len(res) < top:
    print("ERROR: not enough results.")
    sys.exit(1)

# --- load LLM ---

llm = Llama(
      model_path="../../mistral-7b-instruct-v0.2.Q5_K_M.gguf",
      chat_format="mistral-instruct",
      n_ctx=8192,
      n_gpu_layers=-1,  # -1 use all available GPU cores, or 0 run on CPU only
      seed=0,
      verbose=False
)

# --- LLM input ---

context = res[0]["file_body"]

prompt = f"""Answer the question based on the context below.
If the question can't be answered based on the context, say \"I don't know\".
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

print("---")
print("LLM input:")
pprint(conversation)

# --- LLM output ---

t0 = time.time()
result = llm.create_chat_completion(
      messages=conversation
)
t1 = time.time()

print("---")
print("LLM output in %6.3fs" % (t1-t0))
print("usage: %s" % result["usage"])
print(result["choices"][0].get("message").get("content"))
print()

# here's how we would refine the answer with the second chunk
# from the list; this is commented out here as it probably makes
# more sense in an interactive application where the user also
# adds something to the discussion

# # --- LLM input second iteration ---
#
# context = res[1]["file_body"]
#
# prompt = f"""We have the opportunity to refine the existing answer
# (only if needed) with some more context below. Given the additional
# context, refine the original answer to better answer the query.
# If the context isn't useful, return the original answer.
# ---
# Context:
# {context}
# """
#
# conversation.append(result["choices"][0].get("message"))
# conversation.append({"role": "user", "content": prompt})
#
# print("---")
# print("LLM input after refining:")
# pprint(conversation)
#
# # --- LLM output second iteration ---
#
# t0 = time.time()
# result = llm.create_chat_completion(
#       messages=conversation
# )
# t1 = time.time()
#
# print("---")
# print("LLM output after refining in %6.3fs" % (t1-t0))
# print("usage: %s" % result["usage"])
# print(result["choices"][0].get("message").get("content"))
# print()
#
