import os, openai, bcrypt, secrets, dbservice as db
from pinecone import Pinecone, ServerlessSpec
from fastapi import FastAPI, Form, Response, Cookie, Query
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from email_service import send_reset_email

load_dotenv()
# OpenAI API key input
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
openai.api_key = OPENAI_API_KEY

# Pinecone (v3) initialization
pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])

index_name = "final-embeddings"
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

#DIFFERENT RAG ARCHITECTURES:

def answer_rag(question, username, chat_id, k=5):
    context = "\n".join("• " + txt.replace("\n", " ") for txt, _ in top_k_chunks(question, k))
    history = db.get_chat_history(username, chat_id)
    last_five = history[-5:] if len(history) >= 5 else history
    
    chat_history_text = "\n".join(msg[0] for msg in last_five)
    sys_prompt = (
        "You are an expert teacher. You are going to help the user study for various standardized tests and AP's. Be as helpful and kind as possible, and refrain from just giving the user the answer please, please try to teach them as much as possible. Also, try to ask them as many questions as possible, to confirm their learning, and drive home when they arent comprehending as well as they could. Use ONLY the facts below (plus your own language knowledge) to answer:\n\n"
        + context + "\n\nHere is the chat history so far:\n\n"
        + chat_history_text
    )
    msgs = [
        {"role": "system", "content": sys_prompt},
        {"role": "user",   "content": question}
    ]
    return chat(msgs)

def query_driven_retrieval(query, username, chat_id):
    prompt = (
        f"You are an expert teacher. You are going to help the user study for various standardized tests and AP's. Be as helpful and kind as possible, and refrain from just giving the user the answer please, please try to teach them as much as possible. Also, try to ask them as many questions as possible, to confirm their learning, and drive home when they arent comprehending as well as they could. Rephrase the user question to be precise and decomposed for retrieval of relevant context from this java text book:\nQuestion: '{query}'"
    )
    reform = openai.chat.completions.create(
        model=CHAT_MODEL,
        messages=[{"role": "system", "content": prompt}]
    ).choices[0].message.content.strip()
    return answer_rag(reform, username, chat_id)

def answer_rag_faithfulness(question, username, chat_id, k=5):
    context = "\n".join("• " + txt.replace("\n", " ") for txt, _ in top_k_chunks(question, k))
    history = db.get_chat_history(username, chat_id)
    last_five = history[-5:] if len(history) >= 5 else history
    chat_history_text = "\n".join(msg[0] for msg in last_five)
    sys_prompt = (
        "You are an expert teacher. You are going to help the user study for various standardized tests and AP's. Be as helpful and kind as possible, and refrain from just giving the user the answer please, please try to teach them as much as possible. Also, try to ask them as many questions as possible, to confirm their learning, and drive home when they arent comprehending as well as they could. Use ONLY the facts below (plus your own language knowledge) to answer:\n\nn"
        + context + "\n\nHere is the chat history so far:\n\n"
        + chat_history_text
    )
    msgs = [
        {"role": "system", "content": sys_prompt},
        {"role": "user",   "content": question}
    ]
    response, i, o = chat(msgs)
    return response, context, i, o

def faithfulness_aware(query, username, chat_id):
    answer, context, in_tok, out_tok = answer_rag_faithfulness(query, username, chat_id)
    prompt = (
        "You are an expert teacher. You are going to help the user study for various standardized tests and AP's. Be as helpful and kind as possible, and refrain from just giving the user the answer please, please try to teach them as much as possible. Also, try to ask them as many questions as possible, to confirm their learning, and drive home when they arent comprehending as well as they could. Here is the prompt that the user asked you:\n" + query + "\n\nHere is what your answer was:\n" + answer + "\n\nHere was the evidence given:\n" + context + "\n\nPlease brutally critique your former answer, thanks"
    )
    msgs = [
        {"role": "system", "content": prompt}
    ]
    response, i, o = chat(msgs)
    in_tok += i
    out_tok += o
    prompt = (
        "You are an expert teacher. You are going to help the user study for various standardized tests and AP's. Be as helpful and kind as possible, and refrain from just giving the user the answer please, please try to teach them as much as possible. Also, try to ask them as many questions as possible, to confirm their learning, and drive home when they arent comprehending as well as they could. Here is the prompt that the user asked you:\n" + query + "\n\nHere is what your answer was:\n" + answer + "\n\nHere was the evidence given:\n" + context + "\n\nHere are you're critiques:\n" + response + "\n\nPlease fix your answer."
    )
    msgs = [
        {"role": "system", "content": prompt}
    ]
    response, i, o = chat(msgs)
    in_tok += i
    out_tok += o
    return response, in_tok, out_tok

def retrieval_guided(query, username, chat_id):
    context = "\n".join("• " + txt.replace("\n", " ") for txt, _ in top_k_chunks(query))
    history = db.get_chat_history(username, chat_id)
    last_five = history[-5:] if len(history) >= 5 else history
    chat_history_text = "\n".join(msg[0] for msg in last_five)
    prompt = (
        "You are an expert teacher. You are going to help the user study for various standardized tests and AP's. Be as helpful and kind as possible, and refrain from just giving the user the answer please, please try to teach them as much as possible. Also, try to ask them as many questions as possible, to confirm their learning, and drive home when they arent comprehending as well as they could.Here is the users question:\n" + query + "\nPlease write a summary for each of the following pieces of context and how they relate to the question:\n" + context + "\n\nHere is the chat history so far:\n\n"
        + chat_history_text
    )
    msgs = [
        {"role": "system", "content": prompt}
    ]
    response, in_tok, out_tok = chat(msgs)
    prompt = (
        "You are an expert teacher. You are going to help the user study for various standardized tests and AP's. Be as helpful and kind as possible, and refrain from just giving the user the answer please, please try to teach them as much as possible. Also, try to ask them as many questions as possible, to confirm their learning, and drive home when they arent comprehending as well as they could. Here is the users question:\n" + query + "\nAnd here is the summary of the context.\n" + response  + "\n\nHere is the chat history so far:\n\n"
        + chat_history_text
    )
    msgs = [
        {"role": "system", "content": prompt}
    ]
    answer, i, o = chat(msgs)
    in_tok += i
    out_tok += o
    return answer, in_tok, out_tok

def iterative_retrieval(query, username, chat_id):
    history = db.get_chat_history(username, chat_id)
    last_five = history[-5:] if len(history) >= 5 else history
    chat_history_text = "\n".join(msg[0] for msg in last_five)
    prompt = (
        "You are an expert teacher. You are going to help the user study for various standardized tests and AP's. Be as helpful and kind as possible, and refrain from just giving the user the answer please, please try to teach them as much as possible. Also, try to ask them as many questions as possible, to confirm their learning, and drive home when they arent comprehending as well as they could. Here is the users question:\n" + query + "\nPlease write a prompt or phrase that you think will give the most relevant information for the first reasoning step."  + "\n\nHere is the chat history so far:\n\n"
        + chat_history_text
    )
    msgs = [
        {"role": "system", "content": prompt}
    ]
    answer1, in_tok, out_tok = chat(msgs)
    context = "\n".join("• " + txt.replace("\n", " ") for txt, _ in top_k_chunks(answer1))
    prompt = (
        "You are an expert teacher. You are going to help the user study for various standardized tests and AP's. Be as helpful and kind as possible, and refrain from just giving the user the answer please, please try to teach them as much as possible. Also, try to ask them as many questions as possible, to confirm their learning, and drive home when they arent comprehending as well as they could. Here is the users question:\n" + query + "\nHere is the information asked for got in the first round:" + answer1 + "\nHere is the information given to you from all the past rounds:" + context + "\nPlease write a prompt or phrase that you think will give the most relevant information for the next reasoning step."  + "\n\nHere is the chat history so far:\n\n"
        + chat_history_text
    )
    msgs = [
        {"role": "system", "content": prompt}
    ]
    answer2, i, o = chat(msgs)
    in_tok += i
    out_tok += o
    context += "\n".join("• " + txt.replace("\n", " ") for txt, _ in top_k_chunks(answer2))
    prompt = (
        "You are an expert teacher. You are going to help the user study for various standardized tests and AP's. Be as helpful and kind as possible, and refrain from just giving the user the answer please, please try to teach them as much as possible. Also, try to ask them as many questions as possible, to confirm their learning, and drive home when they arent comprehending as well as they could. Here is the users question:\n" + query + "\nHere is the information you asked for in the first round:" + answer1 + "\nHere is the information you asked for in the second round:" + answer2 + "\nHere is the information given to you from all the past rounds:" + context + "\nPlease write a prompt or phrase that you think will give the most relevant information for the next reasoning step."  + "\n\nHere is the chat history so far:\n\n"
        + chat_history_text
    )
    msgs = [
        {"role": "system", "content": prompt}
    ]
    answer3, i, o = chat(msgs)
    in_tok += i
    out_tok += o
    context = "\n".join("• " + txt.replace("\n", " ") for txt, _ in top_k_chunks(answer3))
    prompt = (
        "You are an expert teacher. You are going to help the user study for various standardized tests and AP's. Be as helpful and kind as possible, and refrain from just giving the user the answer please, please try to teach them as much as possible. Also, try to ask them as many questions as possible, to confirm their learning, and drive home when they arent comprehending as well as they could. Here is the users question:\n" + query + "\nHere is the information you aksed for in the first round:" + answer1 + "\nHere is the information you asked for in the second round:" + answer2 + "\nHere is the information you asked for in the third round:" + answer3 + "\nHere is the information given to you from all the past rounds:" + context + "\nPlease write an answer with all of the information given to you thanks.."  + "\n\nHere is the chat history so far:\n\n"
        + chat_history_text
    )
    msgs = [
        {"role": "system", "content": prompt}
    ]
    response, i, o = chat(msgs)
    in_tok += i
    out_tok += o
    return response, in_tok, out_tok

app = FastAPI(title="Standardized Test Study Helper")

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

class ApiRequest(BaseModel):
    prompt: str
    chat_history: str

db.create_user_table()  # Ensure the user table is created

@app.post("/ask")
async def ask_openai(request: PromptRequest, session_token: str = Cookie(default=None), chat_id: str = Query(default=None), type_selector: str = Query(default="naive")):
    if not session_token:
        return {"error": "No session token provided. Please log in."}
    username = db.get_session_user(session_token)
    db.create_chat_history_table()  # Ensure the chat history table is created
    db.create_history_table()
    print(chat_id)
    history = db.get_chat_history(username, chat_id)
    if len(history) == 0:
        prompt = ("Please generate a concise title for this chat. Here is the first message sent:\n\n"+request.prompt)
        msgs = [
            {"role": "system", "content": prompt}
        ]
        answer, _, _ = chat(msgs)
        db.new_chat(answer, chat_id, username)
    print(chat_id)
    print(request.prompt)
    db.insert_message(username, chat_id, request.prompt, False)
    if type_selector == "naive":
        answer, in_tok, out_tok = answer_rag(request.prompt, username, chat_id)
    elif type_selector == "reform":
        answer, in_tok, out_tok = query_driven_retrieval(request.prompt, username, chat_id)
    elif type_selector == "faithful":
        answer, in_tok, out_tok = faithfulness_aware(request.prompt, username, chat_id)
    elif type_selector == "retrieval":
        answer, in_tok, out_tok = retrieval_guided(request.prompt, username, chat_id)
    elif type_selector == "iterative":
        answer, in_tok, out_tok = iterative_retrieval(request.prompt, username, chat_id)
    db.insert_message(username, chat_id, answer, True)
    db.update_tokens(username, in_tok+out_tok)
    print(answer)
    return {"response": answer}


#API SETUP
def answer_rag_api(question, chat_history_text):
    context = "\n".join("• " + txt.replace("\n", " ") for txt, _ in top_k_chunks(question))
    sys_prompt = (
        "You are an expert teacher. You are going to help the user study for various standardized tests and AP's. Be as helpful and kind as possible, and refrain from just giving the user the answer please, please try to teach them as much as possible. Also, try to ask them as many questions as possible, to confirm their learning, and drive home when they arent comprehending as well as they could. Use ONLY the facts below (plus your own language knowledge) to answer:\n\n"
        + context + "\n\nHere is the chat history so far:\n\n"
        + chat_history_text
    )
    msgs = [
        {"role": "system", "content": sys_prompt},
        {"role": "user",   "content": question}
    ]
    return chat(msgs)

def query_driven_retrieval_api(query, chat_history):
    prompt = (
        f"You are an expert teacher. You are going to help the user study for various standardized tests and AP's. Be as helpful and kind as possible, and refrain from just giving the user the answer please, please try to teach them as much as possible. Also, try to ask them as many questions as possible, to confirm their learning, and drive home when they arent comprehending as well as they could. Rephrase the user question to be precise and decomposed for retrieval of relevant context from this java text book:\nQuestion: '{query}'"
    )
    reform = openai.chat.completions.create(
        model=CHAT_MODEL,
        messages=[{"role": "system", "content": prompt}]
    ).choices[0].message.content.strip()
    return answer_rag_api(reform, chat_history)

def answer_rag_faithfulness_api(question, chat_history_text):
    context = "\n".join("• " + txt.replace("\n", " ") for txt, _ in top_k_chunks(question))
    sys_prompt = (
        "You are an expert teacher. You are going to help the user study for various standardized tests and AP's. Be as helpful and kind as possible, and refrain from just giving the user the answer please, please try to teach them as much as possible. Also, try to ask them as many questions as possible, to confirm their learning, and drive home when they arent comprehending as well as they could. Use ONLY the facts below (plus your own language knowledge) to answer:\n\n"
        + context + "\n\nHere is the chat history so far:\n\n"
        + chat_history_text
    )
    msgs = [
        {"role": "system", "content": sys_prompt},
        {"role": "user",   "content": question}
    ]
    response, i, o = chat(msgs)
    return response, context, i, o

def faithfulness_aware_api(query, chat_history):
    answer, context, in_tok, out_tok = answer_rag_faithfulness_api(query, chat_history)
    prompt = (
        "You are an expert teacher. You are going to help the user study for various standardized tests and AP's. Be as helpful and kind as possible, and refrain from just giving the user the answer please, please try to teach them as much as possible. Also, try to ask them as many questions as possible, to confirm their learning, and drive home when they arent comprehending as well as they could. Here is the prompt that the user asked you:\n" + query + "\n\nHere is what your answer was:\n" + answer + "\n\nHere was the evidence given:\n" + context + "\n\nPlease brutally critique your former answer, thanks"
    )
    msgs = [
        {"role": "system", "content": prompt}
    ]
    response, i, o = chat(msgs)
    in_tok += i
    out_tok += o
    prompt = (
        "You are an expert teacher. You are going to help the user study for various standardized tests and AP's. Be as helpful and kind as possible, and refrain from just giving the user the answer please, please try to teach them as much as possible. Also, try to ask them as many questions as possible, to confirm their learning, and drive home when they arent comprehending as well as they could. Here is the prompt that the user asked you:\n" + query + "\n\nHere is what your answer was:\n" + answer + "\n\nHere was the evidence given:\n" + context + "\n\nHere are you're critiques:\n" + response + "\n\nPlease fix your answer."
    )
    msgs = [
        {"role": "system", "content": prompt}
    ]
    response, i, o = chat(msgs)
    in_tok += i
    out_tok += o
    return response, in_tok, out_tok

def retrieval_guided_api(query, chat_history_text):
    context = "\n".join("• " + txt.replace("\n", " ") for txt, _ in top_k_chunks(query))
    prompt = (
        "You are an expert teacher. You are going to help the user study for various standardized tests and AP's. Be as helpful and kind as possible, and refrain from just giving the user the answer please, please try to teach them as much as possible. Also, try to ask them as many questions as possible, to confirm their learning, and drive home when they arent comprehending as well as they could.Here is the users question:\n" + query + "\nPlease write a summary for each of the following pieces of context and how they relate to the question:\n" + context + "\n\nHere is the chat history so far:\n\n"
        + chat_history_text
    )
    msgs = [
        {"role": "system", "content": prompt}
    ]
    response, in_tok, out_tok = chat(msgs)
    prompt = (
        "You are an expert teacher. You are going to help the user study for various standardized tests and AP's. Be as helpful and kind as possible, and refrain from just giving the user the answer please, please try to teach them as much as possible. Also, try to ask them as many questions as possible, to confirm their learning, and drive home when they arent comprehending as well as they could. Here is the users question:\n" + query + "\nAnd here is the summary of the context.\n" + response  + "\n\nHere is the chat history so far:\n\n"
        + chat_history_text
    )
    msgs = [
        {"role": "system", "content": prompt}
    ]
    answer, i, o = chat(msgs)
    in_tok += i
    out_tok += o
    return answer, in_tok, out_tok

def iterative_retrieval_api(query, chat_history_text):
    prompt = (
        "You are an expert teacher. You are going to help the user study for various standardized tests and AP's. Be as helpful and kind as possible, and refrain from just giving the user the answer please, please try to teach them as much as possible. Also, try to ask them as many questions as possible, to confirm their learning, and drive home when they arent comprehending as well as they could. Here is the users question:\n" + query + "\nPlease write a prompt or phrase that you think will give the most relevant information for the first reasoning step."  + "\n\nHere is the chat history so far:\n\n"
        + chat_history_text
    )
    msgs = [
        {"role": "system", "content": prompt}
    ]
    answer1, in_tok, out_tok = chat(msgs)
    context = "\n".join("• " + txt.replace("\n", " ") for txt, _ in top_k_chunks(answer1))
    prompt = (
        "You are an expert teacher. You are going to help the user study for various standardized tests and AP's. Be as helpful and kind as possible, and refrain from just giving the user the answer please, please try to teach them as much as possible. Also, try to ask them as many questions as possible, to confirm their learning, and drive home when they arent comprehending as well as they could. Here is the users question:\n" + query + "\nHere is the information asked for got in the first round:" + answer1 + "\nHere is the information given to you from all the past rounds:" + context + "\nPlease write a prompt or phrase that you think will give the most relevant information for the next reasoning step."  + "\n\nHere is the chat history so far:\n\n"
        + chat_history_text
    )
    msgs = [
        {"role": "system", "content": prompt}
    ]
    answer2, i, o = chat(msgs)
    in_tok += i
    out_tok += o
    context += "\n".join("• " + txt.replace("\n", " ") for txt, _ in top_k_chunks(answer2))
    prompt = (
        "You are an expert teacher. You are going to help the user study for various standardized tests and AP's. Be as helpful and kind as possible, and refrain from just giving the user the answer please, please try to teach them as much as possible. Also, try to ask them as many questions as possible, to confirm their learning, and drive home when they arent comprehending as well as they could. Here is the users question:\n" + query + "\nHere is the information you asked for in the first round:" + answer1 + "\nHere is the information you asked for in the second round:" + answer2 + "\nHere is the information given to you from all the past rounds:" + context + "\nPlease write a prompt or phrase that you think will give the most relevant information for the next reasoning step."  + "\n\nHere is the chat history so far:\n\n"
        + chat_history_text
    )
    msgs = [
        {"role": "system", "content": prompt}
    ]
    answer3, i, o = chat(msgs)
    in_tok += i
    out_tok += o
    context = "\n".join("• " + txt.replace("\n", " ") for txt, _ in top_k_chunks(answer3))
    prompt = (
        "You are an expert teacher. You are going to help the user study for various standardized tests and AP's. Be as helpful and kind as possible, and refrain from just giving the user the answer please, please try to teach them as much as possible. Also, try to ask them as many questions as possible, to confirm their learning, and drive home when they arent comprehending as well as they could. Here is the users question:\n" + query + "\nHere is the information you aksed for in the first round:" + answer1 + "\nHere is the information you asked for in the second round:" + answer2 + "\nHere is the information you asked for in the third round:" + answer3 + "\nHere is the information given to you from all the past rounds:" + context + "\nPlease write an answer with all of the information given to you thanks.."  + "\n\nHere is the chat history so far:\n\n"
        + chat_history_text
    )
    msgs = [
        {"role": "system", "content": prompt}
    ]
    response, i, o = chat(msgs)
    in_tok += i
    out_tok += o
    return response, in_tok, out_tok

@app.post("/api")
async def api_request(apiData: ApiRequest, id: str = Query(), type_selector: str = Query(default="naive")):
    if not id:
        return {"error": "No session user ID provided."}
    prompt = apiData.prompt
    chat_history = apiData.chat_history
    username = db.id_to_username(id)
    db.create_api_history_table()
    
    print(id)
    if type_selector == "naive":
        answer, in_tok, out_tok = answer_rag_api(prompt, chat_history)
    elif type_selector == "reform":
        answer, in_tok, out_tok = query_driven_retrieval_api(prompt, chat_history)
    elif type_selector == "faithful":
        answer, in_tok, out_tok = faithfulness_aware_api(prompt, chat_history)
    elif type_selector == "retrieval":
        answer, in_tok, out_tok = retrieval_guided_api(prompt, chat_history)
    elif type_selector == "iterative":
        answer, in_tok, out_tok = iterative_retrieval_api(prompt, chat_history)
    else:
        answer, in_tok, out_tok = chat((prompt+chat_history))
    print(in_tok+out_tok)
    print(username)
    db.update_tokens(username, in_tok+out_tok)
    print(answer)
    db.insert_api_message(username, apiData.prompt, False, type_selector, apiData.chat_history)
    db.insert_api_message(username, answer, True, type_selector, "")
    return {"response": answer}

# Auth System

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
def update_password(current_password: str = Form(...), password: str = Form(...), confirm_password: str = Form(...), session_token: str = Cookie(default=None), reset: bool = Query(...)):
    if not session_token and not reset:
        return {"error": "No session token provided. Please log in."}
    username = db.get_session_user(session_token)
    if not username and not reset:
        return {"error": "Invalid session token."}
    if bcrypt.checkpw(current_password.encode('utf-8'), db.get_user_password(username).encode('utf-8')) or reset:
        if password != confirm_password:
            return {"error": "New passwords do not match."}
        hashed = hash_password(password)
        db.update_user_password(username, hashed)
        return RedirectResponse(url="/static/dashboard.html", status_code=303)
    return {"error": "Current password is incorrect."}

@app.post("/reset_pw")
async def reset_pw(email: str = Form(...)):
    username = db.email_to_username(email)
    name = db.get_user_name(username)[0] + " " + db.get_user_name(username)[1]
    if username:
        session_token = secrets.token_urlsafe(32)
        db.store_session(session_token, username)
        reset_link = "https://ben.seqhubai.com/static/resetpw.html?session_token="+session_token
        await send_reset_email(email, name, reset_link)
    return RedirectResponse(url="/", status_code=303)

@app.post("/loadhistory")
def load_history(session_token: str = Cookie(default=None)):
    username = db.get_session_user(session_token)
    if (username):
        return {"history": db.get_history(username)}
    else:
        return {"error": "Login Required"}
    
@app.post("/get_chat_history")
def get_chat_history(chat_id: str = Query(...), session_token: str = Cookie(default=None)):
    username = db.get_session_user(session_token)
    print(db.get_chat_history_special(username, chat_id))
    return db.get_chat_history_special(username, chat_id)