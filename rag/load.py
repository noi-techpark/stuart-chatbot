# SPDX-FileCopyrightText: 2024 NOI Techpark <digital@noi.bz.it>
#
# SPDX-License-Identifier: AGPL-3.0-or-later

# ------------------------------------------------------------------------------
# RAG all text files ending in .txt or .md in the directories given below, chunk them,
# find the embedding vectors and store the chunks and vectors into PostgreSQL.
#
# Do you have files in other formats, such as PDFs? You need to convert them to
# .md with a tool such as MarkItDown.
#
# As distributed, this will just read files from ../data_example. For the deployment
# at NOI Techpark, we use ../data_ghissues, ../data_readme, ../data_rt, and 
# ../data_wiki.
#
# Notes:
#   - see get_embedding_model() in 'librag.py' to see what embedding model is used
#   - Postgres location and credentials are read from 'secrets_pg.json'
#   - the script expects the ragdata table to have been loaded into Postgres
#     (see global README.md)
#   - the script is incremental, it will skip files that are already present in
#     the database
# ------------------------------------------------------------------------------

from librag import *


rag_dir("../data_example", tag="example", chunk_len=5000, overlap_len=500, hard_limit=6000)

# used at NOI Techpark:
# rag_dir("../data_ghissues", tag="ghissues", chunk_len=5000, overlap_len=500, hard_limit=6000)
# rag_dir("../data_readme",   tag="readme",   chunk_len=5000, overlap_len=500, hard_limit=6000)
# rag_dir("../data_rt",       tag="rt",       chunk_len=5000, overlap_len=500, hard_limit=6000)
# rag_dir("../data_wiki",     tag="wiki",     chunk_len=5000, overlap_len=500, hard_limit=6000)
