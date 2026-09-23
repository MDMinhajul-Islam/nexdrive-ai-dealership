import httpx
import sys
from app.utils.config import get_settings

def run_diagnostic():
    s = get_settings()
    api_key = s.retell_api_key
    agent_id = s.retell_agent_id

    if not api_key or not agent_id:
        print("HTTP status: N/A (Missing local config)")
        print("Agent exists: N/A")
        print("is_published: N/A")
        print("version: N/A")
        sys.exit(0)

    try:
        resp = httpx.get(
            f"https://api.retellai.com/get-agent/{agent_id}",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        print(f"HTTP status: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            print("Agent exists: yes")
            print(f"is_published: {data.get('is_published', 'N/A')}")
            print(f"version: {data.get('version', 'N/A')}")
        else:
            print("Agent exists: no")
            print("is_published: N/A")
            print("version: N/A")
    except Exception as e:
        print(f"HTTP status: Error ({type(e).__name__})")
        print("Agent exists: N/A")
        print("is_published: N/A")
        print("version: N/A")

if __name__ == "__main__":
    run_diagnostic()
