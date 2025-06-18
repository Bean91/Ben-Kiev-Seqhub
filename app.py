#pip install openai pinecone fastapi uvicorn pydantic python-dotenv -q
import os, openai
from pinecone import Pinecone, ServerlessSpec
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from dbservice import create_chat_history_table, insert_message, get_chat_history

# user="admin"
create_chat_history_table()  # Ensure the chat history table is created

load_dotenv()
# OpenAI API key input
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
openai.api_key = OPENAI_API_KEY

# Pinecone (v3) initialization
pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])

index_name = "java-embeddings"
if index_name not in pc.list_indexes().names():
    pc.create_index(
        name=index_name,
        dimension=1536,  # for text-embedding-3-small
        metric="cosine",
        spec=ServerlessSpec(
            cloud="aws",
            region="us-east-1"
        )
    )

index = pc.Index(index_name)

# Choose models
CHAT_MODEL   = "gpt-4o"
EMBED_MODEL  = "text-embedding-3-small"
def top_k_chunks(query, k=3):
    q_emb = openai.embeddings.create(model=EMBED_MODEL, input=query).data[0].embedding
    res = index.query(vector=q_emb, top_k=k, include_metadata=True)
    return [(match.metadata["text"], match.score) for match in res.matches]

def chat(messages, temp=0.0):
    resp = openai.chat.completions.create(
        model=CHAT_MODEL, messages=messages, temperature=temp
    )
    msg = resp.choices[0].message.content.strip()
    usage = resp.usage
    return msg, usage.prompt_tokens, usage.completion_tokens

def answer_kb_only(question, k=5):
    hits = top_k_chunks(question, k)
    return "\n\n-----------------\n".join(f"[Score {score:.3f}]\n{txt}" for txt, score in hits), 0, 0

def answer_rag(question, k=5):
    context = "\n".join("• " + txt.replace("\n", " ") for txt, _ in top_k_chunks(question, k))
    sys_prompt = (
        "You are an expert assistant. Use ONLY the facts below (plus your own language knowledge) to answer:\n\n"
        + context + "\n\nHere is the chat history so far:\n\n"
        + get_chat_history("admin")[-5][0]
    )
    msgs = [
        {"role": "system", "content": sys_prompt},
        {"role": "user",   "content": question}
    ]
    return chat(msgs)

def answer_no_context(question):
    msgs = [{"role": "user", "content": question}]
    return chat(msgs)

app = FastAPI(title="AP CS Test Teacher")

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def root():
    return FileResponse("static/index.html")

# Enable CORS for all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic model for the request body
class PromptRequest(BaseModel):
    prompt: str

@app.post("/ask")
async def ask_openai(request: PromptRequest):
    print(request.prompt)
    insert_message("admin", request.prompt)
    answer, in_tok, out_tok = answer_rag(request.prompt)
    insert_message("admin", answer)
    print(answer)
    return {"response": answer}