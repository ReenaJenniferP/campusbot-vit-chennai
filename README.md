# CampusBot

**Student:** Reena Jennifer P  
**Register Number:** 24BCE1041

CampusBot is a local RAG-based chatbot built for **VIT Chennai**.  
It answers user questions using content collected from the **VIT Chennai website** and official PDF resources, then shows the most relevant source links used for the response.

## Features

- Simple frontend interface for asking questions
- Local backend built with FastAPI
- Retrieval using FAISS vector search
- Answers grounded in VIT Chennai website and document data
- Source links displayed with each answer

## Project Structure

```text
CampusBot Project/
├── backend/
│   └── server.py
├── data/
│   ├── vit_chennai_other_resources.txt
│   ├── vit_chennai_pages.txt
│   ├── vit_chunks.jsonl
│   ├── vit_chunks.sqlite
│   ├── vit_corpus.jsonl
│   ├── vit_embeddings.jsonl
│   ├── vit_faiss.index
│   ├── vit_faiss_ids.npy
│   └── vit_meta.jsonl
├── frontend/
│   ├── home.html
│   ├── index.html
│   ├── login.html
│   ├── styles.css
│   └── js/
│       ├── ask.js
│       ├── bg-canvas.js
│       └── login.js
├── scripts/
│   ├── all_pages.py
│   ├── build_faiss_index.py
│   ├── build_vectors.py
│   ├── search_faiss.py
│   ├── site_analyzer.py
│   ├── verify_vectors.py
│   └── vit_corpus_builder.py
├── requirements.txt
└── README.md
```

## Technologies Used

- HTML
- CSS
- JavaScript
- Python
- FastAPI
- FAISS
- Ollama
- NumPy
- BeautifulSoup
- PyPDF

## How It Works

1. Crawls and collects VIT Chennai website pages
2. Builds a text corpus from website pages and PDFs
3. Splits the corpus into chunks
4. Generates embeddings using Ollama
5. Builds a FAISS index for similarity search
6. Accepts a user question from the frontend
7. Retrieves the most relevant chunks
8. Generates an answer and displays source links

## How to Run

### 1. Install dependencies

```bash
pip3 install -r requirements.txt
```

### 2. Make sure Ollama is running

The project expects Ollama locally at:

```text
http://localhost:11434
```

### 3. Start the backend server

From the project root:

```bash
python3 -m uvicorn backend.server:app --reload
```

### 4. Open the frontend

Open one of these files in your browser:

```text
frontend/login.html
frontend/home.html
```

## Notes

- This project is designed for local execution.
- The frontend sends requests to the backend at `http://localhost:8000/ask`.
- The chatbot uses local vector search and local LLM/embedding models through Ollama.
- The login page is a simple project interface and does not implement real authentication.

## Author

**Reena Jennifer P**  
**Reg No: 24BCE1041**
