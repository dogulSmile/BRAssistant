# Buildroot Review Assistant

An AI-powered automated code review assistant designed specifically for the **Buildroot** project. The system leverages Retrieval-Augmented Generation (RAG) by combining an **Elasticsearch** vector database with an AI agent (here **Gemini 3 Flash (Thinking Mode)**) to analyze patches, enforce manual compliance, cross-reference historical rejections (jurisprudence), and handle complex multi-part patch series.

---

## Key Features

* **Dual-Engine RAG**: Performs semantic kNN vector searches over both the official Buildroot User Manual and a curated history of past patch rejections.
* **Code-Signature Alignment**: Employs a unified embedding strategy to match raw patch diff patterns directly with natural language developer logs.
* **Patchwork Series Awareness**: Automatically detects patch structures (e.g., `[v5, 2/5]`), securely querying the Patchwork API to pull and reconstruct the context of the series' Cover Letter ($0/n$) and previous patches before reviewing the target file.
* **Strict Hierarchy of Truth**: Validates submissions through an ordered priority loop: Manual Rules $\\rightarrow$ Past Case-Law $\\rightarrow$ Expert Intuition.
* **Production-Ready Output**: Generates editable standard `.eml` mail draft reviews containing precise, inline file feedback.

---

## Prerequisites

Ensure your host machine has the following prerequisites installed:
* **Python 3.10** or higher
* **Docker** & Docker Engine
* `curl` (for database verification)

---

## Infrastructure Setup

The processing pipeline requires an active Elasticsearch 8.x instance to store embeddings.

### Option A: Docker Deployment (Recommended)

Run the following command to spin up a single-node Elasticsearch container with security features disabled for development purposes:

```bash
docker pull docker.elastic.co/elasticsearch/elasticsearch:8.12.0

docker run -d --name elasticsearch \
  -p 9200:9200 \
  -e "discovery.type=single-node" \
  -e "xpack.security.enabled=false" \
  -e "ES_JAVA_OPTS=-Xms2g -Xmx2g" \
  docker.elastic.co/elasticsearch/elasticsearch:8.12.0

docker start elasticsearch
```

### Option B: Host Systemd Service

If Elasticsearch is installed directly on the host system, manage the service using systemd outside of any Python virtual environment (outside venv):

```bash
# Check service status
sudo systemctl status elasticsearch

# Start service if stopped
sudo systemctl start elasticsearch
```

### Verifying Elasticsearch Status

Verify that the cluster is up and inspect available indices (including document counts and store sizes) using the following `curl` command:

```bash
curl -s "http://localhost:9200/"
```
Please also verify that your disk usage is below 85% or you might have indexation problems (see https://www.elastic.co/docs/troubleshoot/elasticsearch/fix-watermark-errors) :

```bash
curl -s "http://localhost:9200/_cat/allocation?v"
```
---

## Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/dogulSmile/BRAssistant
   cd BRAssistant
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Environment Variables:**
   Get your keys here (no specific permissions required) :
      https://aistudio.google.com/app/api-keys?project=gen-lang-client-0489474561
      https://huggingface.co/settings/tokens
   and create a `.env` file in the root directory to store your API keys and configuration configurations:
   ```env
   GEMINI_API_KEY="your_key_here"
   HF_TOKEN="your_key_here"
   ```

4. **Environment Variables:**

   Launch those 2 commands at the root of the project to initialize the database (Elasticsearch must be started):
   ```bash
   python3 elastic_functions/vectorializer.py -d ressources/The_Buildroot_user_manual.html reset
   python3 elastic_functions/vectorializer.py -p ressources/buildroot_lessons.jsonl reset

   (You can enhance the database by adding other files, but the format has to be respected.)
   ```

---

## Technical Stack & Dependencies

The project relies on the core dependencies specified in `requirements.txt`:

| Package | Purpose |
| :--- | :--- |
| `elasticsearch` (< 9.0.0) | Official client library for database interactions and vector storage. |
| `sentence-transformers` | Generates text embeddings locally for semantic search. |
| `huggingface_hub` | Manages download and caching of NLP models. |
| `bs4` (BeautifulSoup) | Handles HTML/XML log parsing and text extraction. |
| `python-dotenv` | Loads configuration options seamlessly from `.env` files. |
| `openrouter` | Interface tool for LLM inference APIs. |
| `asyncio` / `aiohttp` | Core asynchronous engines for concurrent network and file operations. |
| `tenacity` | Advanced retry handling for robust API calls and database synchronization. |

## Usage

To launch the agent, please verify that your venv is activated, then in the root of the project simply launch this command :

```bash
python3 ./agent_gemini.py 
```
You will be asked to put the patch to review, you have 2 possible choices:
  - file : simply put the path of the .patch to analyze (ex: /home/user/Downloads/package-test.patch)
  - link : paste the patchwork url of the patch (ex: https://patchwork.ozlabs.org/project/buildroot/patch/20260520092415.665898-1-giulio.benetti@benettiengineering.com/)

You can also directly indicate the patch to analyze this way:

```bash
python3 ./agent_gemini.py <url/path of the patch>
```

After the analyze, you will find your review ready in .eml format in the reviews_eml/ directory, you can open it with your favorite mail software.

To analyze another patch, you can simply enter again another url/path of a patch, and another .eml file will be created.
