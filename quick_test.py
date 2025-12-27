import requests

print("1. Testing Workflows...")
r = requests.get('http://127.0.0.1:8000/api/workflows')
data = r.json()['data']
print(f"   Found {len(data)} workflows")
for w in data:
    print(f"   - {w['id']}: {w['name']}")

print("\n2. Testing LLM Configs...")
r = requests.get('http://127.0.0.1:8000/api/llm-configs/')
data = r.json()['data']
print(f"   Found {len(data)} LLM configs")
for c in data:
    print(f"   - {c['id']}: {c.get('display_name', c['model_name'])}")

print("\n3. Testing Projects...")
r = requests.get('http://127.0.0.1:8000/api/projects')
data = r.json()['data']
projects = [p for p in data if p['id'] != 1]
print(f"   Found {len(projects)} user projects")
for p in projects:
    print(f"   - {p['id']}: {p['name']}")

if projects:
    project_id = projects[0]['id']
    print(f"\n4. Testing Cards for project {project_id}...")
    r = requests.get(f'http://127.0.0.1:8000/api/projects/{project_id}/cards')
    cards = r.json()['data']
    print(f"   Found {len(cards)} cards")
    for c in cards[:5]:
        print(f"   - {c['id']}: {c['title']} ({c.get('card_type_name', 'Unknown')})")

print("\nAll tests passed!")
