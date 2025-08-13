# SPDX-FileCopyrightText: 2024 NOI Techpark <digital@noi.bz.it>
#
# SPDX-License-Identifier: AGPL-3.0-or-later

# ------------------------------------------------------------------------------
# RAG all files in the given directory, chunk them, find the embedding
# vectors and store the chunks and vectors into PostgreSQL.
#
# Note:
#   - see get_embedding_model() in 'librag.py' to see what embedding model is used
#   - PostgreSQL location and credentials are read from 'secrets_pg.json'
#   - the script expect the ragdata table to be there (see 'schema.sql')
#   - the script is incremental, it will skip files that are already present
#     in the table
#       - ticket transactions are immutable, so that is not a problem as
#         the script will just add the new transactions
#       - readmes and wiki entries might change, so they should be deleted
#         periodically from the table, so the script can reRAG them:
#         delete from ragdata where tag in ('readme', 'wiki');
# ------------------------------------------------------------------------------

from librag import *

rag_dir("../data_readme", tag="readme", chunk_len=2000, overlap_len=250, hard_limit=2500)
rag_dir("../data_wiki",   tag="wiki",   chunk_len=2000, overlap_len=250, hard_limit=2500)
rag_dir("../data_rt",     tag="rt",     chunk_len=1000, overlap_len=250, hard_limit=1500)
