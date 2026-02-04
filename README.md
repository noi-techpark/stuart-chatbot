[![REUSE Compliance](https://github.com/noi-techpark/stuart-chatbot/actions/workflows/reuse-lint.yml/badge.svg)](https://github.com/noi-techpark/opendatahub-docs/wiki/REUSE#badges)

# Stuart 🛎

(**S**uper **T**alkative **U**nderstanding **A**rtificial **R**esponse **T**echnology)

<!-- TOC -->
  * [Background](#background)
  * [Installation](#installation)
    * [Stuart RAG](#stuart-rag)
    * [Required service: Postgres with the pgvector extension](#required-service-postgres-with-the-pgvector-extension)
    * [Required service: LLM inference web service endpoint](#required-service-llm-inference-web-service-endpoint)
      * [Which LLM to use?](#which-llm-to-use)
      * [How to run the LLM?](#how-to-run-the-llm)
  * [Running](#running)
    * [Preparing and RAGging the documents](#preparing-and-ragging-the-documents)
    * [Running the chatbot on the command line](#running-the-chatbot-on-the-command-line)
    * [Running the chatbot as a web application](#running-the-chatbot-as-a-web-application)
  * [Document scrapers (optional)](#document-scrapers-optional)
  * [FAQ](#faq)
    * [What about documents in other formats (.pdf, .docx, etc...)?](#what-about-documents-in-other-formats-pdf-docx-etc)
    * [What about database performance?](#what-about-database-performance)
    * [What about chunk length? What about top-N searches?](#what-about-chunk-length-what-about-top-n-searches)
<!-- TOC -->

**Changelog of this document**

- 2026-02-01 updated for the major revision
- 2024-07-07 expanded to include information about the new web frontend and add a few recommendations for custom deployments
- 2024-03-27 added note about llama-cpp-python compile options
- 2024-03-25 first release - Chris Mair <chris@1006.org>

![README-screen01.png](README-screen01.png)

---
## Background

Stuart uses **RAG** (_retrieval-augmented generation_). RAG improves the quality of responses by
combining the capabilities of two main components: a retrieval system and a generative model.

The **retrieval system** searches a database of the user's documents to find information
that is relevant to the user's question. This step is crucial as it allows the generative model
to access knowledge that is not contained in its pre-trained parameters.

The **generative model** receives a prompt that is constructed from the retrieved 
information and the user's input. It then generates a coherent, natural text based on that prompt.

Stuart is a proof-of-concept system built with a few guiding principles:

- the system should run be able to run locally,
- it should only rely on Free models,
- it should be able to run on modest hardware (expensive datacenter GPUs are supported for fast performance, but not required),
- it should be easily expandable for users that wish to deploy a RAG system using their own documents.

When Stuart was first implemented at the beginning of 2024, there were already a few well known
Python packages to build RAG systems such as [LlamaIndex](https://docs.llamaindex.ai/en/stable/) and
[LangChain](https://www.langchain.com/). These packages were basically glue code
that abstracts away details about the underlying models and software components.

An early prototype of Stuart used LlamaIndex. However, LlamaIndex was and still is in very quick
evolution, are somewhat black-boxy and the integration between their components and the
documentation is sometimes lagging their quick progress.

To better understand the underlying technology and to keep things stable and simple,
we opted to not rely on any of these frameworks and rather implement a few functions,
such as text chunking and database access from scratch. It turned out that the
resulting code was not much longer, but easier to understand and using way fewer 
dependencies.

This makes Stuart **ideal as a testbed for experimenting with all the components
of a RAG system**. Early 2026 Stuart was updated to be even more flexible and **easier to use**.

At **NOI Techpark**, Stuart is installed with access to documentation related to the **Open Data Hub**.
There are custom scrapers for the GitHub issues, the repository readme files, the past help desk
tickets and the wiki.

---
## Installation

### Stuart RAG

To install the Stuart RAG code, your computer should have Python3 installed (with the ability to create virtual environments)
as well as have `git` available. Any Linux system should do, as well as macOS with the developer tools installed.

You can check the availability of these requirements with these commands:

```shell
python3 --version                                   # should give some version >= 3.9
echo "import venv, ensurepip" | python3; echo $?    # should give `0`
git --version                                       # should give some version >= 2.18
```

> If the second command fails on Debian/Ubuntu, run a `sudo apt install python3-venv` to get the required Python modules.

If everything is good, fetch Stuart from its GitHub page and create a virtual environment for it:

```shell
cd ~
git clone https://github.com/noi-techpark/stuart-chatbot
python3 -m venv ~/stuart-chatbot/.venv
```

Remember to activate this virtual environment, whenever you work in it:

```shell
source ~/stuart-chatbot/.venv/bin/activate
```

The core Stuart RAG code is under the `rag/` subdirectory. Change to that directory and install the requirements
into the virtual environment:

```shell
source ~/stuart-chatbot/.venv/bin/activate
cd ~/stuart-chatbot/rag
pip install -r requirements.txt
```

> Expect about **15 GiB** of storage for the installation of this part.
> 
> While there are just three dependencies, one dependency (the package `sentence-transformers`) is unfortunately huge.
> After installing that one, the virtual environment directory will be 7.3 GiB in size. After running it the first time,
> 2.2 GiB will be added (embedding model download). Additionally, pip will cache another 4 GiB of files.

### Required service: Postgres with the pgvector extension

Stuart needs access to a **[Postgres](https://www.postgresql.org/) database server** with
the **[pgvector](https://github.com/pgvector/pgvector) extension**.

This can be any installation, local or managed. 

For a quick experiment, the most simple way to set this up is running the pgvector project's docker container:

```shell
docker run --restart unless-stopped --name mypg -e POSTGRES_USER=rag -e POSTGRES_PASSWORD=rag -e POSTGRES_DB=ragdb  -p 127.0.0.1:5432:5432 -d pgvector/pgvector:pg18-trixie
```

You might want to give it a stronger password, though.

Once the container is up, connect to the newly created instance:

```shell
docker exec -it mypg /usr/bin/psql -U rag ragdb
```

This will give you access to a Postgres shell. There, enable the pgvector extension and create the table
Stuart will use:

```sql
create extension vector;

create table ragdata (
    id          bigserial,
    tag         text not null,
    file_name   text not null,
    start_pos   bigint,
    end_pos     bigint,
    ts timestamp with time zone default now() not null,
    file_body   text not null,
    embedding   vector(1024) not null,
    primary key(id),
    unique(tag, file_name, start_pos, end_pos)
);
```

At the end leave the Postgres shell with `\q`.

For a production installation, we recommend performing a native installation of Postgres using the best practices
depending on your environment.

If you're using a different Postgres service (or use a stronger password), update the information under
`~/stuart-chatbot/rag/secrets_pg.json` accordingly, so Stuart will be able to connect to your Postgres service.


### Required service: LLM inference web service endpoint

Stuart needs access to a large language model (LLM). All you need is provide Stuart with a so called
**OpenAI-compatible chat-completion endpoint**. That's a fancy word to describe a LLM running behind a
web service using a de-facto standard API.

There are two sub-task here: **which LLM should I use** and **how do I run it** (as a suitable web service)?

#### Which LLM to use?

When LLMs first become popular and useful during 2023, they had an aura of being only available as a service through big,
proprietary vendors. During 2024 and 2025 there was a very fast-paced development in this space. Many vendors came up with
newer, smarter, faster models. Open weight models that you can freely download and run locally under FOSS licenses appeared,
and **we now have open weight models that beat the original state-of-the-art models from the time Stuart was first released**.

At the same time the software to run the models improved, allowing faster inference on machines without a GPU or with
less VRAM or RAM.

RAG doesn't even need state-of-the-art models anymore. Small to mid-range models are smart enough now for RAG.
According to  our experiments, the quality of the search and the fact newer model can be fed larger contexts improves
the performance more than model "intelligence".

Here are a some open weight LLMs that we tested and can recommend as of Feb 2026. They are small enough
to run on reasonably sized machines (see the next section).

| LLM               | parameters  | Author                    | License  |
|-------------------|-------------|---------------------------|----------|
| Mistral Small 3.2 | 24b (dense) | MistralAI (Europe/France) | Apache 2 |
| Qwen3-VL-30B      | 31b (MOE)   | Alibaba Cloud (China)     | Apache 2 |
| gpt-oss-20b       | 21b (MOE)   | OpenAI (USA)              | Apache 2 |
| Qwen3-VL-8b       | 9b (MOE)    | Alibaba Cloud (China)     | Apache 2 |

They all work well for RAG and can digest documents and understand questions in many languages just fine
(we tested English, German and Italian).

When answering in German or Italian, the most grammatically accurate responses come from Mistral Small 3.2,
closely followed by both Qwen3-VL models. Expect occasional grammar errors from gpt-oss-20b.

#### How to run the LLM?

Earlier versions of Stuart linked to a library to run the LLM inside Stuart. This was not very flexible.

Nowadays most deployments use an external software to run the LLM that exposes the model as a web service:
the so called **OpenAI-compatible chat-completion endpoint**. This has become a de facto standard and
starting from the current version, Stuart supports. this.

You can also use third-party service providers that offer open-weight models as a service. A popular
provider is [OpenRouter](https://openrouter.ai/). If you're looking for an EU-based provider, check out
[Scaleway's Generative APIs service](https://www.scaleway.com/en/generative-apis/).

If you use a third-party service, just fill in the endpoint, model name and API key that you obtain
from your provider, and you're done (file `~/stuart-chatbot/rag/secrets_llm_endpoint.json`).

For a truly independent setup, you can run the models locally!

There are a few popular software packages to run LLM inference. The NOI Techpark installation, for
example, uses [llama.cpp](https://github.com/ggml-org/llama.cpp).

For a quick experiment, one of the easiest ways to run open weight models locally is
[downloading and running a software called Ollama](https://ollama.com/download).

Ollama maintains a repository of open weight LLMs. Once you set the software up you can pull models from there.
The following table lists the recommended models together with the names in Ollama's repository: 

| LLM               | parameters/quantization | name in Ollama repo                     | download size | GPU VRAM when used with Stuart |
|-------------------|-------------------------|-----------------------------------------|---------------|--------------------------------|
| Mistral Small 3.2 | 24b (dense) / 8 bits    | mistral-small3.2:24b-instruct-2506-q8_0 | 26 GiB        | ~ 30 GiB                       |
| Qwen3-VL-30B      | 31b (MOE) / 4 bits      | qwen3-vl:30b                            | 20 GiB        | ~ 24 GiB                       |
| gpt-oss-20b       | 21b (MOE) / 4 bits      | gpt-oss:20b                             | 14 GiB        | ~ 16 GiB                       |
| Qwen3-VL-8b       | 9b (MOE) / 4 bits       | qwen3-vl:8b                             | 6.1 GiB       | ~ 11 GiB                       | 

You will get the best performance on a system with a **GPU** that has at least the amount of **VRAM** given in the last column.

The VRAM estimates might seem somewhat generous. Take into account we expect the LLM is running locally on
the same machine where Stuart is also running. So, besides the LLM with the long contexts typically encountered
when doing RAG, also the embedding model should fit into VRAM. Furthermore, for Mistral Small 3.2, we picked
versions with better quantization quality (i.e. 8 bits), higher than Ollama's defaults.

> Models _can_ be run on systems with less VRAM at the cost of slower performance or **without a GPU** at the cost
> of much slower performance. If you want to try out Stuart in such situations you're advised to use the smallest model
> (Qwen3-VL-8b). On a Linux machine without a GPU, 16 GB of RAM is then enough to run Stuart RAG, Postgres and LLM inference
> all together locally.

To pull a model, run `ollama pull` with the exact Ollama repo model name from the table above, for example:

```bash
ollama pull mistral-small3.2:24b-instruct-2506-q8_0
```

Whatever model provider you choose, remember to update the file `~/stuart-chatbot/rag/secrets_llm_endpoint.json`.

For a locally running Ollama (the software) serving gpt-oss-20b (the LLM), you would leave the API key empty:

```json
{
  "endpoint": "http://127.0.0.1:11434/v1/chat/completions",
  "model": "gmistral-small3.2:24b-instruct-2506-q8_0",
  "api_key": ""
}
```

---
## Running

### Preparing and RAGging the documents

Before you can use Stuart for asking questions about your documents, you need to make them available
as text or Markdown files and save them into one or more directories.

To get you started, there is a directory (`~/stuart-chatbot/data_example`) with 5 suitable example files.

> In a follow-up sections we will explain how to **scrape documents** from other sources. Have a look at the FAQ
> on how to **convert documents** from other formats into Markdown.

Let's proceed to load the documents in the example directory to be used for RAG. To "RAG" the documents means:
- read all the files from the given directory
- chunk them into overlapping chunks of roughly equal size
- call a sentence embedding model (see [Wikipedia for an explanation](https://en.wikipedia.org/wiki/Sentence_embedding))
  to encode meaningful semantic information from each chunk into a point in a high-dimensional vector space
- store the file name, chunk and vector into Postgres.

That's the job of `~/stuart-chatbot/rag/load.py`.

That script contains a single line to "RAG" all files in a directory:

```python
rag_dir("../data_example", tag="example", chunk_len=5000, overlap_len=500, hard_limit=6000)
```

Feel free to edit the script and copy the line to add the directories with your documents.
The parameters indicate the chunk lengths in number of characters. Typical values might be in the order
of 1000-10000 characters. See the FAQ below for more information on picking good values for `chunk_len`.

Run the script:

```shell
source ~/stuart-chatbot/.venv/bin/activate
cd ~/stuart-chatbot/rag
python load.py
```

When it runs for the first time, the script will automatically
download the sentence embedding model (2.2 GiB) and put it into `~/.cache`.

The model we use is [bge-m3](https://huggingface.co/BAAI/bge-m3) (license: MIT).
We pinned the version to 5a212480c9a75bb651bcb894978ed409e4c47b82 (2024-03-21). 

The model is quite large (2.2 GiB) for sentence embedding models, but performs very well,
can embed a variety of text sizes from short sentences to longer documents (8192 tokens ~ 20k characters) and
has been trained on many languages.

Expected output is:

```text
5/5 new files, 5 new chunks, chunked in 0.000s, embedded in 0.481s, stored in 0.253s
```

The run time very much depends on the capabilities of your hardware and the size
of the document. On a system with a single CPU core and no GPU, sentence embedding the
documents for the Open Data Hub (~ 20 million characters) might **take a few hours**.
Luckily, `load.py` **works incrementally** (it will just add new files), so that is
typically not a problem.

Note that `load.py` **never deletes or updates** document chunks in the database, it just adds
chunks from new files!

If you want to delete chunks from the database you need to do that using SQL. Again connect
to Postgre and run a delete query. Here are some examples:

```SQL
delete from ragdata where tag = 'example'; -- delete chunks with a given tag (files from the same directory have the same tag)
delete from ragdata where tag = 'example' and file_name = 'eli-the-elephant.txt'; -- delete chunks from a given file
truncate ragdata; -- delete everything (!)
```

### Running the chatbot on the command line

Run the RAG chatbot:

```shell
source ~/stuart-chatbot/.venv/bin/activate
cd ~/stuart-chatbot/rag
python query.py
```

This will get you into an easy to use endless loop with the chatbot. Here is a sample session:

---

```text
$ python query.py 
Stuart: You rang 🛎️ ?
Ask me anything or enter 'q' to exit. Enter 'r' to restart our conversation.
```
```text
> Che nome ha il robot che deve proteggere la colonia spaziale?
```
```text
{meta}
{meta} embedding vector search - top 5 chunks:
{meta} distance   tag  offset  file_name
{meta} --------   ---  ------  ---------
{meta} 0.52625 example       0  the-colony-on-xyris-9.txt <-- will be added to context
{meta} 0.61479 example       0  a-detective-story.md
{meta} 0.62225 example       0  readme-about-imaginary-project.md
{meta} 0.65012 example       0  planets.txt
{meta} 0.69569 example       0  eli-the-elephant.txt
{meta} please wait...
{meta} LLM output in  0.641s
{meta}
```
```text
Il robot che deve proteggere la colonia spaziale si chiama K-7X.
```
```text
> Che direttiva ha?
```
```text
{meta}
{meta} embedding vector search - top 5 chunks:
{meta} distance   tag  offset  file_name
{meta} --------   ---  ------  ---------
{meta} 0.38186 example       0  the-colony-on-xyris-9.txt <-- will be added to context
{meta} 0.62792 example       0  a-detective-story.md
{meta} 0.63127 example       0  readme-about-imaginary-project.md
{meta} 0.64229 example       0  planets.txt
{meta} 0.71697 example       0  eli-the-elephant.txt
{meta} please wait...
{meta} LLM output in  1.363s
{meta}
```
```text
La direttiva di K-7X è semplice: proteggere la colonia. Ma in seguito scopre che il suo compito è: preservare la vita umana.
```

---

Let's break down the parts

1. The user asks in Italian: **Che nome ha il robot che deve proteggere la colonia spaziale?**
   (What's the name of the robot that must protect the space colony?).

2. This piece of text is embedded and transformed into a vector. A query is run to find
   the closest vector stored in PostgreSQL and the top-5 matches are shown (lines starting 
   with `{meta}` are debug output). The best match is actually the right document: it's
   the file `data_example/the-colony-on-xyris-9.txt` that contains a science fiction short story.

3. The code proceeds to build a prompt using the original question and the chunk from
   the document and inputs it into the LLM.

4. The LLM answers correctly, based on our document, keeping the conversation in Italian:
   **Il robot che deve proteggere la colonia spaziale si chiama K-7X.**
   (The robot that must protect the space colony is called K-7X.)

5. The user asks a follow-up question: **Che direttiva ha?**
   (What is its directive?)

6. Now the LLMs previous answer plus the new question is again embedded and searched for (leading
   to the same document found as best match).

7. A new prompt is built using the follow-up question and the same chunk and input again into the LLM.

8. The LLMs answers with the correct information: **La direttiva di K-7X è semplice: proteggere la colonia. 
   Ma in seguito scopre che il suo compito è: preservare la vita umana.**
   (The directive of K-7X is simple: protect the colony. But later, it discovers that its task is: preserve human life.)

> Pause a moment to think about how powerful semantic search is! We use a multi-language
> embedding model, so language doesn't matter anymore. The search will find texts that are
> close to the _meaning_ of the question, regardless the language. Here, the Italian words of the question 
> do not appear in the English short story (not even "robot"), still the search finds the right text.

Here are some questions and follow-up questions you can try on the example data in different languages:

- What does gulp do? How do you install it?
- Wie heisst der blaue Elefant? Wem hat er geholfen?
- Che nome ha il robot che deve proteggere la colonia spaziale? Che direttiva ha?
- Name the planets in the solar system! What's Factulus' moon called?
- What's the name of the cat?

Note how the chatbot is instructed to follow the information it gets from the retrival fase:

```text
Q: Name the planets in the solar system!

A: Based on the context provided, here are the planets in the solar system:

- Mercury
- Venus
- Earth
- Mars
- Jupiter
- Saturn
- Factulus
- Uranus
- Neptune
```

As you probably know, there is no planet _Factulus_. We've put that one into `data_example/planets.txt` to test
the chatbots capability to answer questions based only on the RAG prompt and ignore its pretrained knowledge!

Also note how the LLM is instructed to admit it doesn't know when the information is just not there (there is no cat in the examples).

```text
Q: What's the name of the cat?

A: I don't know.
```

> **Note: when you want to ask a new, different question, do not forget to enter "r" to reset the context!** Otherwise, the previous answer
> will be added in the search. This will likely result in the wrong document being found.


### Running the chatbot as a web application

Stuart also comes with a web application and a system to queue and process multiple conversations concurrently.

The files related to this part are under the directory `~/stuart-chatbot/web/`.

Before running for the first time, edit the file `backend.json` there:

```JSON
{
  "bind_ip": "127.0.0.1",
  "bind_port": "9001",
  "preshared_secret": "**********"
}
```

If you need to be able to connect via network instead of 127.0.0.1 (localhost), the value of `bind_ip`
should be changed to `0.0.0.0` (or any IP address you want).

**Please be aware that this opens up the web application to any users that may connect via
your configured network. There is no built-in authentication for users of the web interface.
Anybody who has access to the web application can open a session to input prompts and get
the answers.**

The value of `preshared_secret` is a secret string used by the inference backend to authenticate
itself against the web application to be allowed to process jobs. Put some hard to guess string
there.

To just run the application in the virtual Python environment already prepared for the
rest of Stuart perform these steps:

```text
source ~/stuart-chatbot/.venv/bin/activate
cd ~/stuart-chatbot/web/
pip install -r requirements.txt  # note this adds Flask
python backend.py
```

Alternatively, you can run the application in a container with the provided Dockerfile.
The Docker host can be an independent server, there's no need to have the other Stuart components
installed. You don't need the Python environment or even Python at all on that host.

Remember to set the value of `bind_ip` in `web/backend.json` to `0.0.0.0` and proceed to build
the Docker image:

```text
cd ~/stuart-chatbot/web/
docker build -t stuart-web .
```

Then run the new image:

```text
docker run -p 127.0.0.1:8080:9001 stuart-web
```

Again, take care on where exactly you map the HTTP endpoint. With the `-p` parameter given
here, the application becomes visible on the host at `http://127.0.0.1:8080`. Change the value
according to what you need.

At this point the web application is ready. If you connect, a new session will be created,
and you can insert a question that will be queued:

![README-screen03.png](README-screen03.png)

However, nobody is yet processing the queue! So the question stays in the "question queued" state
indefinitely. We need to go back to the directory `~/stuart-chatbot/rag/`, where the chatbot command line application lives:

```text
source ~/stuart-chatbot/.venv/bin/activate
cd ~/stuart-chatbot/rag/
```

In this directory, there is another `backend.json`. Edit it to point to the URL of the web application and set
the value of `preshared_secret` to the same string as above.

```JSON
{
  "endpoint": "http://127.0.0.1:9001",
  "preshared_secret": "**********"
}
```

Then start these two tasks:

```text
source ~/stuart-chatbot/.venv/bin/activate
cd ~/stuart-chatbot/rag/
python backend_query.py
python backend_heartbeat.py
```

`backend_query.py` is the task that polls the web application and runs the jobs in the queue
in the same way as `query.py` did for the command line interface.

`backend_heartbeat.py` is not strictly necessary, it just updates a status field so the web
application is aware of the fact the queue is being processed (see the top left status
indicator of the web interface).

At this point the web interface is ready and will process your questions.

The session information (including all past questions and answers) is stored in a local
SQLite database (file stuart.db). It is recreated automatically at startup, if it is not present.

> The files `docker-compose.yml`, `.env.example` and the directory `infrastructure` are specific
> to the deployment at NOI Techpark.

---
## Document scrapers (optional)

Scraping means:

- download the documents,
- save them as plain text files.

For the Open Data Hub deployment, the document sources are:

- the GitHub issues from the relevant NOI Techpark repositories,
- the readme Markdown files from the relevant NOI Techpark repositories,
- the tickets from the Open Data Hub Request Tracker installation.
- the wiki Markdown files from the Open Data Hub Docs wiki,

For each category, there is a custom scraper in `~/stuart-chatbot/scrapers/`.
The scrapers are specially crafted for the Open Data Hub:

`scrape_ghissues.py` scrapes the GitHub issues from all repositories of the
Open Data Hub GitHub account configured in `secrets_gh.json`.

`scrape_readme.sh` scrapes the readme Markdown files from the NOI Techpark repositories 
on GitHub that are relevant to the Open Data Hub. The links are read from a hand-crafted 
file (`scrape_readme_urls.txt`).

`scrape_rt.py` scrapes tickets from a well known ticketing system (Best Practice' Request Tracker)
in use at the Open Data Hub.
It scrapes transactions of type 'Ticket created', 'Correspondence added'
or 'Comments added'. Remember to set up the location and credentials of the
Request Tracker installation in `scrape_rt.json`! 

`scrape_wiki.sh` scrapes the wiki Markdown files from the [ODH-Docs wiki](https://github.com/noi-techpark/odh-docs/wiki).

The documents are stored in the `~/stuart-chatbot/data_*` directories.

Currently, scraping the readmes and the wiki just takes a few seconds, but 
**scraping the tickets takes a few hours**. Luckily `scrape_rt.py` works
incrementally, but it still needs about 20 minutes to check each ticket for
new transactions. Scraping the GitHub issues, also is incremental, but is
slow due to the necessary rate limiting imposed by GitHub.

> The easiest way to run all these scripts is to set up a cronjob that runs
> `cron/cron-scrape.sh` and `cron/cron-scrape-gh-issues.sh` that will take care of everything.

Stuart is designed to be easily extendable. You can **add scrapers for your own
documents**. The only requirement is the scrapers output **plain text files** (of any
dimension).

Again, there is a handy script that can be called from **crontab**: `cron/cron-load.sh`.

---
## FAQ

### What about documents in other formats (.pdf, .docx, etc...)?

To "RAG" documents for Stuart, the documents need to be saved as **plain text** (`.txt`) or **Markdown** (`.md`) files into
one or more directories.

Other documents can be converted into Markdown, for example with the toolset [**MarkItDown**](https://github.com/microsoft/markitdown).

You can install MarkItDown into your existing RAG virtual environment:

```shell
source ~/stuart-chatbot/.venv/bin/activate
cd ~/stuart-chatbot/rag/
pip install 'markitdown[all]'
```

Let's download a PDF manual (`odh.pdf`), convert it to Markdown (`odh.md`) and store it into a directory `testdocs/`:

```shell
curl -o odh.pdf https://opendatahub.readthedocs.io/_/downloads/en/latest/pdf/
markitdown odh.pdf > odh.md
mkdir testdocs
mv odh.md testdocs/
````

Now, edit `~/stuart-chatbot/rag/load.py` with line to load the file from `testdocs/`:

```Python
rag_dir("testdocs", tag="odh-manual", chunk_len=10000, overlap_len=500, hard_limit=11000)
```

and RAG the file:

```shell
source ~/stuart-chatbot/.venv/bin/activate
cd ~/stuart-chatbot/rag/
python load.py
```

The expected output is:

```text
1/1 new files, 8 new chunks, chunked in 0.001s, embedded in 1.425s, stored in 0.066s
```

That means one new file was found in `testdocs/`, it was split into 8 chunks, each was embedded and loaded into Postgres.

Great! Now let's ask an obscure detail from that document:

```text
$ python query.py 
Stuart: You rang 🛎️ ?
Ask me anything or enter 'q' to exit. Enter 'r' to restart our conversation.
```
```text
> I'm querying the Open Data Hub. I'm using a WHERE clause in the URL like this: where=a.eq.5.
  However, now I want to add an and-condition to filter a second parameter. How do I do that?
```
```text
{meta}
{meta} embedding vector search - top 5 chunks:
{meta} distance   tag  offset  file_name
{meta} --------   ---  ------  ---------
{meta} 0.43727 odh-manual   39899  odh.md <-- will be added to context
{meta} 0.45549 odh-manual   49978  odh.md
{meta} 0.48636 odh-manual   19860  odh.md
{meta} 0.48812 odh-manual       0  odh.md
{meta} 0.49266 odh-manual    9996  odh.md
{meta} please wait...
{meta} LLM output in  3.334s
{meta}
```
```text
To add an and-condition to filter a second parameter in your WHERE clause for the Open Data Hub query, you can use the following format:

where=a.eq.5,b.eq.value

Replace "value" with the value you want to filter the second parameter by. The comma (,) acts as an implicit AND operator, so both conditions must be true for the records to be included in the response.
```

As you can see, the search found the chunk from the file starting at offset 39899. That's the text starting a bit before "Advanced Data Processing"
on page 18. That's exactly where this topic is discussed! The LLM used that information to answer the question.


### What about database performance?

As long as you're handling less than, say, hundreds of MB of text, don't worry
about performance. Search times won't matter much. Embedding the query text and
prompting the LLM will take most of the time. Once you feel search time increases, 
you can create an index on the vector column. Connect again to Postgres and
create and index on the embedding column:

```sql
CREATE INDEX ragdata_embedding_hnsw_ix ON ragdata
USING hnsw (embedding vector_cosine_ops);
```

You just need to do this once, the index will be automatically updated whenever the data changes.


### What about chunk length? What about top-N searches?

When "RAG"ging your documents using `~/stuart-chatbot/rag/load.py` what value should be set for the parameter `chunk_len`?

For an LLM to be able to answer questions about your document, it must be fed your document in the prompt behind the scene.
However, LLMs can't process prompts of unlimited length. Currently, typical maximum context lengths are in the order of a
few hundred thousand characters. When you interact with a RAG system, the whole conversation (your questions, the answers,
all (hidden) prompts with extracts from your documents) must fit in that amount of text. There's also a performance issue
as the longer the prompt, the more compute load is generated.

If this wasn't the case, we could just fit all of your texts into the system prompt and get rid of embedding, searching
and vector databases altogether!

All that being said, what's the ideal chunk length?

Look at your texts. If you have smaller texts, like wiki pages or knowledge base articles, check their size distribution.
If all the pages are, say in the range few to 3000 characters, you get the best performance when you extract each page into
its own file and set the chunk length to 3000. This way, each page will map to one chunk. When you use the system,
the search will identify the best matching page and the LLM will get the whole page.

If you have 99% of all pages within 3000 characters and just 1% of larger pages, like 100000 characters. Still keep 3000
and accept that there will be cases where the search will find just chunks of the longer page (hopefully the relevant ones).

If you have huge documents, like PDFs with thousands of pages in a single file (converted to Markdown) spanning millions
of characters each, try picking a largish chunk length, say, 10000. Increasing chunk length too much will make search less
precise. There is also a limit in the embedding model. You will get an error if you exceed the limit of 8192 tokens of our
embedding model (equivalent to about 20000-30000 characters). For these kind of situations the problem often is that a
question can only be answered after looking at different parts of the large document, and, you cannot increase chunk
length to accomodate the whole document.

There is also another trick here. Keep the chunk size reasonably small, like  5000-10000 characters, but instead of
feeding the single top chunk into the LLM, provide the top-N ones.

This can be set in Stuart's query code: `~/stuart-chatbot/rag/query.py` for the command line client or
`~/stuart-chatbot/rag/backend_query.py` for the webclient backend.

Find this part:

```python

# --- search ---

# use the first top_n results out of top_max retrieved
# the default is top_n = 1, top_max = 5

top_n = 1
top_max = 5
```

and set top_n to some value larger than 1. 

For example, with `top_n = 2`, the LLM will get two different (hopefully relevant) chunks out of a large document
and might be able to give better answers.