# server.py
# Dummy backend for your CampusBot frontend.
# It just replies with a fake answer so you can test frontend <-> backend.

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="CampusBot Dummy Server")

# ✅ CORS allows your HTML file (opened in browser) to call this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # for class project simplicity
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    question: str

@app.get("/")
def home():
    return {"status": "ok", "message": "CampusBot dummy backend running"}

@app.post("/chat")
def chat(req: ChatRequest):
    q = req.question.strip()

    # Dummy answer (replace later with Ollama + vector search)
    answer = (
        "✅ Dummy reply from backend!\n\n"
        f"You asked: {q}\n\n"
        "Next step: we'll connect this endpoint to your vectors + Ollama (Qwen3)."
    )

    return {"answer": answer}


if __name__ == "__main__":
    import uvicorn
    # Run on localhost:8000
    uvicorn.run(app, host="127.0.0.1", port=8000)
