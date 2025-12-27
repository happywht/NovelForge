import requests

BASE_URL = "http://127.0.0.1:8000/api"

print("=" *60)
print("NovelForge Feature Tests")
print("=" * 60)

# Test 1: Workflows
print("\n[1/5] Testing Workflows API...")
try:
    r = requests.get(f'{BASE_URL}/workflows')
    workflows = r.json() if isinstance(r.json(), list) else r.json().get('data', [])
    print(f"   ✓ Found {len(workflows)} workflows:")
    for w in workflows:
        print(f"     - ID {w['id']}: {w['name']}")
except Exception as e:
    print(f"   ✗ Error: {e}")

# Test 2: LLM Configs
print("\n[2/5] Testing LLM Configs API...")
try:
    r = requests.get(f'{BASE_URL}/llm-configs/')
    data = r.json()
    configs = data if isinstance(data, list) else data.get('data', [])
    print(f"   ✓ Found {len(configs)} LLM configurations:")
    for c in configs:
        print(f"     - ID {c['id']}: {c.get('display_name', c['model_name'])} ({c['provider']})")
except Exception as e:
    print(f"   ✗ Error: {e}")

# Test 3: Projects
print("\n[3/5] Testing Projects API...")
try:
    r = requests.get(f'{BASE_URL}/projects')
    data = r.json()
    all_projects = data if isinstance(data, list) else data.get('data', [])
    projects = [p for p in all_projects if p['id'] != 1]
    print(f"   ✓ Found {len(projects)} user projects:")
    for p in projects:
        print(f"     - ID {p['id']}: {p['name']}")
except Exception as e:
    print(f"   ✗ Error: {e}")
    projects = []

# Test 4: Cards
if projects:
    project_id = projects[0]['id']
    print(f"\n[4/5] Testing Cards API (Project {project_id})...")
    try:
        r = requests.get(f'{BASE_URL}/projects/{project_id}/cards')
        data = r.json()
        cards = data if isinstance(data, list) else data.get('data', [])
        print(f"   ✓ Found {len(cards)} cards:")
        for c in cards[:8]:
            print(f"     - ID {c['id']}: {c['title']} ({c.get('card_type_name', 'Unknown')})")
        if len(cards) > 8:
            print(f"     ... and {len(cards) - 8} more cards")
    except Exception as e:
        print(f"   ✗ Error: {e}")
else:
    print("\n[4/5] Skipping Cards test (no projects)")

# Test 5: Card Types
print("\n[5/5] Testing Card Types API...")
try:
    r = requests.get(f'{BASE_URL}/card-types')
    data = r.json()
    card_types = data if isinstance(data, list) else data.get('data', [])
    print(f"   ✓ Found {len(card_types)} card types:")
    for ct in card_types[:5]:
        print(f"     - {ct['name']}")
    if len(card_types) > 5:
        print(f"     ... and {len(card_types) - 5} more types")
except Exception as e:
    print(f"   ✗ Error: {e}")

print("\n" + "=" * 60)
print("✓ All API tests completed!")
print("=" * 60)
