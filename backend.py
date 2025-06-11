import os, textwrap, math, openai, uvicorn
from tqdm.auto import tqdm
import numpy as np
from pinecone import Pinecone, ServerlessSpec
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pyngrok import ngrok
import multiprocessing as mp

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Welcome to the OpenAI Proxy API!"}
def start_api():
    uvicorn.run(app, host="0.0.0.0", port=8000)

# Launch with ngrok
if __name__ == "__main__":
    NGROK_AUTH_TOKEN = "2qNN16PXhoH2qlmHiXOiPcC1tUd_3BXtmjv9JxCt6dH4N9qaY"
    ngrok.set_auth_token(NGROK_AUTH_TOKEN)
    ngrok.kill()  # Clean any previous tunnels
    public_url = ngrok.connect(addr="8000", proto="http", bind_tls=True)
    print("Public URL:", public_url.public_url)

    # Start API in a separate process
    api_proc = mp.Process(target=start_api, daemon=True)
    api_proc.start()

    try:
        api_proc.join()
    except KeyboardInterrupt:
        print("\nShutting down…")
        api_proc.terminate()
        ngrok.kill()