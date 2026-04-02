import urllib.request
import json

try:
    r = urllib.request.urlopen("http://localhost:8080/api/config")
    data = json.loads(r.read().decode())
    print("Server is running!")
    print(json.dumps(data, indent=2))
except Exception as e:
    print(f"Error: {e}")
