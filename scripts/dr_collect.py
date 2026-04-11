import requests
try:
    resp = requests.post("http://netview_fastapi:8000/api/v1/network/dr-training/collect", timeout=60)
    print(resp.json())
except Exception as e:
    print(f"Error: {e}")
