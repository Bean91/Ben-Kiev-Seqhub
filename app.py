import os, openai, bcrypt, secrets, dbservice as db
from pinecone import Pinecone, ServerlessSpec
from fastapi import FastAPI, Form, Response, Cookie, Query
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel
from dotenv import load_dotenv

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

def answer_rag(question, username, chat_id, k=5):
    context = "\n".join("• " + txt.replace("\n", " ") for txt, _ in top_k_chunks(question, k))
    history = db.get_chat_history(username, chat_id)
    last_five = history[-5:] if len(history) >= 5 else history
    chat_history_text = "\n".join(msg[0] for msg in last_five)
    sys_prompt = (
        "You are an expert assistant. Use ONLY the facts below (plus your own language knowledge) to answer:\n\n"
        + context + "\n\nHere is the chat history so far:\n\n"
        + chat_history_text
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
async def ask_openai(request: PromptRequest, session_token: str = Cookie(default=None), chat_id: str = Query(default=None)):
    if not session_token:
        return {"error": "No session token provided. Please log in."}
    username = db.get_session_user(session_token)
    db.create_chat_history_table()  # Ensure the chat history table is created
    print(chat_id)
    print(request.prompt)
    db.insert_message(username, chat_id, request.prompt, False)
    answer, in_tok, out_tok = answer_rag(request.prompt, username, chat_id)
    db.insert_message(username, chat_id, answer, True)
    db.update_tokens(username, in_tok+out_tok)
    print(answer)
    return {"response": answer}

# Auth System
db.create_user_table()  # Ensure the user table is created

def hash_password(plain_password: str) -> str:
    salt = bcrypt.gensalt()  # Generates a random salt
    hashed = bcrypt.hashpw(plain_password.encode('utf-8'), salt)
    return hashed.decode('utf-8')  # Store as a string in your database

@app.post("/login")
def login(response: Response, username: str = Form(...), password: str = Form(...)):
    if bcrypt.checkpw(password.encode('utf-8'), db.get_user_password(username).encode('utf-8')):
        session_token = secrets.token_urlsafe(32)  # secure random string
        db.store_session(session_token, username)
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(key="session_token", value=session_token, max_age=7200, httponly=False)
        return response
    return {"error": "Invalid credentials"}

@app.post("/signup")
def signup(username: str = Form(...), password: str = Form(...), confirm_password: str = Form(...), email: str = Form(...), first_name: str = Form(...), last_name: str = Form(...)):
    if db.get_user_password(username):
        return {"error": "Username already exists"}

    if password != confirm_password:
        return {"error": "Passwords do not match"}

    hashed = hash_password(password)
    db.create_user(username, hashed, email, first_name, last_name)
    return RedirectResponse(url="/static/signin.html", status_code=303)

@app.post("/updateusername")
def update_user(username: str = Form(...), session_token: str = Cookie(default=None)):
    if not session_token:
        return {"error": "No session token provided. Please log in."}
    current_user = db.get_session_user(session_token)
    if current_user != username:
        return {"error": "You can only update your own information."}
    db.update_user(current_user, username)
    return RedirectResponse(url="/static/dashboard.html", status_code=303)

@app.post("/updateemail")
def update_email(email: str = Form(...), session_token: str = Cookie(default=None)):
    if not session_token:
        return {"error": "No session token provided. Please log in."}
    username = db.get_session_user(session_token)
    db.update_user_email(username, email)
    return RedirectResponse(url="/static/dashboard.html", status_code=303)

@app.post("/delete_account")
def delete_account(session_token: str = Cookie(default=None)):
    if not session_token:
        return {"error": "No session token provided. Please log in."}
    username = db.get_session_user(session_token)
    db.delete_user(username)
    return RedirectResponse(url="/", status_code=303)

@app.post("/updatefirstname")
def update_firstname(firstname: str = Form(...), session_token: str = Cookie(default=None)):
    if not session_token:
        return {"error": "No session token provided. Please log in."}
    username = db.get_session_user(session_token)
    db.update_user_firstname(username, firstname)
    return RedirectResponse(url="/static/dashboard.html", status_code=303)

@app.post("/updatelastname")
def update_lastname(lastname: str = Form(...), session_token: str = Cookie(default=None)):
    if not session_token:
        return {"error": "No session token provided. Please log in."}
    username = db.get_session_user(session_token)
    db.update_user_lastname(username, lastname)
    return RedirectResponse(url="/static/dashboard.html", status_code=303)

@app.post("/user_info")
def user_info(session_token: str = Cookie(default=None)):
    if not session_token:
        return {"error": "No session token provided. Please log in."}
    username = db.get_session_user(session_token)
    user_info = db.get_user_info(username)
    if user_info:
        print(user_info)
        return {"success": True, "user_info": user_info}
    return {"error": "User not found."}

@app.post("/updatepassword")
def update_password(current_password: str = Form(...), new_password: str = Form(...), confirm_password: str = Form(...), session_token: str = Cookie(default=None)):
    if not session_token:
        return {"error": "No session token provided. Please log in."}
    username = db.get_session_user(session_token)
    if not username:
        return {"error": "Invalid session token."}
    if bcrypt.checkpw(current_password.encode('utf-8'), db.get_user_password(username).encode('utf-8')):
        if new_password != confirm_password:
            return {"error": "New passwords do not match."}
        hashed = hash_password(new_password)
        db.update_user_password(username, hashed)
        return RedirectResponse(url="/static/dashboard.html", status_code=303)
    return {"error": "Current password is incorrect."}