import os
import time
import gc

from libpg import *

from sentence_transformers import SentenceTransformer


def find_sentence_boundary(body: str, pos: int, direction: int) -> int:
    delimiters = [". ", "! ", "? ", ".\n", "!\n", "?\n", "\n\n"]
    pos -= 2
    while True:
        if direction == -1 and pos < 0:
            return 0
        if direction == 1 and pos >= len(body):
            return len(body)
        for delimiter in delimiters:
            if body[pos:pos + 2].startswith(delimiter):
                return pos + 2
        pos += direction


def find_word_boundary(body: str, pos: int, direction: int) -> int:
    delimiters = [" ", "\t", "\n"]
    pos -= 1
    while True:
        if direction == -1 and pos < 0:
            return 0
        if direction == 1 and pos >= len(body):
            return len(body)
        for delimiter in delimiters:
            if body[pos:pos + 1].startswith(delimiter):
                return pos + 1
        pos += direction


def chunk_text(body: str, chunk_len: int, overlap_len: int, hard_limit: int) -> List[Dict[str, int]]:
    if chunk_len < 1 or overlap_len < 0 or hard_limit < 1:
        print("ERROR: chunk_text(): inconsistent arguments.")
        sys.exit(1)
    if chunk_len + overlap_len > hard_limit or overlap_len > chunk_len:
        print("ERROR: chunk_text(): inconsistent arguments relative to each other.")
        sys.exit(1)
    # find ideal chunk limit positions
    chunks = []
    num = 0
    while not num * chunk_len >= len(body):
        chunks.append({"start": num * chunk_len,
                       "end": (num + 1) * chunk_len + overlap_len})
        num += 1
    # grow each chunk to avoid mid-sentence cuts
    for pos in chunks:
        # candidate positions
        start_s = find_sentence_boundary(body, pos["start"], -1)
        end_s = find_sentence_boundary(body, pos["end"], 1)
        start_w = find_word_boundary(body, pos["start"], -1)
        end_w = find_word_boundary(body, pos["end"], 1)
        # grow the chunk to the nicest fit that doesn't exceed hard_limit,
        # if possible (otherwise keep the hard cuts)
        if end_s - start_s <= hard_limit:
            pos["start"] = start_s
            pos["end"] = end_s
        elif end_w - start_s <= hard_limit:
            pos["start"] = start_s
            pos["end"] = end_w
        elif end_s - start_w <= hard_limit:
            pos["start"] = start_w
            pos["end"] = end_s
        elif end_w - start_w <= hard_limit:
            pos["start"] = start_w
            pos["end"] = end_w
        elif pos["end"] - start_w <= hard_limit:
            pos["start"] = start_w
        elif end_w - pos["start"] <= hard_limit:
            pos["end"] = end_w
        # consistency check
        if pos["end"] - pos["start"] > hard_limit:
            print("ERROR: chunk_text(): consistency check 1 failed.")
            sys.exit(1)
    # avoid the last chunk just being a subset of the one but last chunk
    if len(chunks) >= 2:
        if chunks[-1]["end"] == chunks[-2]["end"]:
            chunks.pop()
        # consistency check
        if chunks[-1]["end"] != len(body):
            print("ERROR: chunk_text(): consistency check 2 failed.")
            sys.exit(1)

    return chunks


def get_embedding_model() -> SentenceTransformer:
    # https://huggingface.co/BAAI/bge-m3 (license: MIT)
    # we use revision 5a212480c9a75bb651bcb894978ed409e4c47b82 (downloaded 2024-03-21)
    # when called for the first time, this downloads and caches the model (2.1 GiB) into
    # ~/.cache/huggingface/hub/models--BAAI--bge-m3/
    return SentenceTransformer("BAAI/bge-m3", revision="5a212480c9a75bb651bcb894978ed409e4c47b82")


def rag_dir(dirname: str, tag: str,
            chunk_len: int, overlap_len: int, hard_limit: int) -> None:

    try:
        files = os.listdir(dirname)
        files.sort()
    except FileNotFoundError:
        print("ERROR: rag_dir(): cannot open directory '%s'." % dirname)
        sys.exit(1)
    known_extensions = [".txt", ".md"]

    cursor = open_cursor()

    model = get_embedding_model()

    num_files_old = num_files_new = num_chunks = 0
    t1_chunk = t1_embed = t1_store = 0.0

    for file_name in files:

        extension = os.path.splitext(file_name)[1]
        if extension not in known_extensions:
            print("INFO: rag_dir(): skipping '%s' with unknown extension." % file_name)
            continue

        file = open("%s/%s" % (dirname, file_name), "r")
        try:
            body = file.read()
        except UnicodeDecodeError:
            print("INFO: rag_dir(): skipping '%s' with invalid unicode." % file_name)
            file.close()
            continue
        file.close()

        if len(body) < 5:
            print("INFO: rag_dir(): skipping (almost) empty file '%s'." % file_name)
            continue

        res = select_one(cursor,
                         """
                         select count(1) as cnt from ragdata where tag = %s and file_name = %s
                         """,
                         [tag, file_name])
        if int(res["cnt"]) > 0:
            num_files_old += 1
            continue

        # print("%5d %s" % (len(body), file_name))

        t0 = time.time()
        chunks = chunk_text(body, chunk_len, overlap_len, hard_limit)
        strings = []
        for chunk in chunks:
            strings.append(body[chunk["start"]:chunk["end"]])
        t1_chunk += time.time() - t0

        t0 = time.time()
        embeddings = model.encode(strings, batch_size=1)
        t1_embed += time.time() - t0
        t0 = time.time()
        for i in range(0, len(embeddings)):
            execute(cursor,
                    """
                    insert into ragdata (tag, file_name, start_pos, end_pos, file_body, embedding)
                    values(%s, %s, %s, %s, %s, %s)
                    """,
                    [tag, file_name, chunks[i]["start"], chunks[i]["end"], strings[i], embeddings[i].tolist()])
            num_chunks += 1
        cursor.connection.commit()
        t1_store += time.time() - t0

        num_files_new += 1
        gc.collect()

    close_cursor(cursor)
    print("%d/%d new files, %d new chunks, chunked in %.3fs, embedded in %.3fs, stored in %.3fs" %
          (num_files_new, (num_files_old + num_files_new), num_chunks, t1_chunk, t1_embed, t1_store))


def search(cursor: psycopg2.extras.DictCursor, top: int, query_str: str) -> List[Dict[str, any]]:
    model = get_embedding_model()
    embedding = model.encode(query_str)
    # when searching, note that we add a small penalty for chunks with tag 'rt'
    res = select_all(cursor,
                     """
                     select tag, file_name, start_pos, file_body,
                            (embedding <=> %s::vector) + case when tag = 'rt' then 0.1 else 0.0 end as distance
                     from ragdata
                     order by distance asc limit %s
                     """,
                     [embedding.tolist(), top])
    return res
