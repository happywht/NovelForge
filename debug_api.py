import requests
import json

print("Testing API Response Format...")
r = requests.get('http://127.0.0.1:8000/api/workflows')
print(f"Status Code: {r.status_code}")
print(f"Content-Type: {r.headers.get('Content-Type')}")
print(f"\nRaw Response Text (first 500 chars):")
print(r.text[:500])
print(f"\nResponse Type: {type(r.json())}")
print(f"\nResponse Keys: {list(r.json().keys()) if isinstance(r.json(), dict) else 'Not a dict'}")
print(f"\nFull Response:")
print(json.dumps(r.json(), indent=2, ensure_ascii=False)[:1000])
