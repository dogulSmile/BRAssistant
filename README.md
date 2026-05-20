# Platform Engine (Elasticsearch & LLM Processing Pipeline)

This repository contains the backend processing and indexing pipeline for log analysis and document processing. The system leverages Elasticsearch for storage and search capability, combined with a Python-based asynchronous pipeline utilizing NLP tools (`sentence-transformers`) and LLM orchestration (`openrouter`).

## Prerequisites

Ensure your host machine has the following installed:
* Python 3.10 or higher
* Docker & Docker Compose
* `curl` (for verification)

---

## Infrastructure Setup

The pipeline requires an active Elasticsearch 8.x instance. You can run it either locally via systemd or containerized via Docker.

### Option A: Docker Deployment (Recommended)

Run the following command to spin up a single-node Elasticsearch container with security features disabled for development purposes:

```bash
docker run -d --name elasticsearch \
  -p 9200:9200 \
  -e "discovery.type=single-node" \
  -e "xpack.security.enabled=false" \
  -e "ES_JAVA_OPTS=-Xms512m -Xmx512m" \
  docker.elastic.co/elasticsearch/elasticsearch:8.12.0
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
curl -s "http://localhost:9200/_cat/indices?v&h=index,docs.count,pri.store.size,store.size&s=index"
```

---

## Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd <repository-folder>
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
   Create a `.env` file in the root directory to store your API keys and configuration configurations:
   ```env
   GEMINI_API_KEY="your_key_here"
   HF_TOKEN="your_key_here"
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
