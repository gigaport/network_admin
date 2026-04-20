import requests
try:
    resp = requests.get("http://netview_fastapi:8000/api/v1/network/collect/multicast/arista/pr", timeout=120)
    print(resp.json() if resp.status_code == 200 else f"Error: {resp.status_code}")
except Exception as e:
    print(f"Error: {e}")
