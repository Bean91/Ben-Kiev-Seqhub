import os, requests
from dotenv import load_dotenv

load_dotenv()

stack_project_id = os.getenv("STACK_PROJECT_ID")
stack_publishable_key = os.getenv("STACK_PUBLISHABLE_CLIENT_KEY")
stack_secret_key = os.getenv("STACK_SECRET_SERVER_KEY")

def stack_auth_request(method: str, endpoint: str, **kwargs):
    headers = {
        "x-stack-access-type": "server",
        "x-stack-project-id": stack_project_id,
        "x-stack-publishable-client-key": stack_publishable_key,
        "x-stack-secret-server-key": stack_secret_key,
        **kwargs.pop("headers", {}),
    }
    url = f"https://api.stack-auth.com{endpoint}"
    resp = requests.request(method, url, headers=headers, **kwargs)
    resp.raise_for_status()
    return resp.json()
