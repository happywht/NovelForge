import requests
import json

BASE_URL = "http://127.0.0.1:8000/api"

def test_workflows_list():
    """测试工作流列表"""
    print("\n=== 测试 1: 工作流列表 ===")
    try:
        r = requests.get(f"{BASE_URL}/workflows", timeout=5)
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            workflows = data.get("data", [])
            print(f"共有 {len(workflows)} 个工作流")
            for wf in workflows:
                print(f"  - ID {wf['id']}: {wf['name']}")
            return workflows
        else:
            print(f"Error: {r.text}")
            return []
    except Exception as e:
        print(f"Exception: {e}")
        return []

def test_llm_configs():
    """测试 LLM 配置"""
    print("\n=== 测试 2: LLM 配置列表 ===")
    try:
        r = requests.get(f"{BASE_URL}/llm-configs/", timeout=5)
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            configs = data.get("data", [])
            print(f"共有 {len(configs)} 个 LLM 配置")
            for cfg in configs:
                print(f"  - ID {cfg['id']}: {cfg.get('display_name', cfg['model_name'])} ({cfg['provider']})")
            return configs
        else:
            print(f"Error: {r.text}")
            return []
    except Exception as e:
        print(f"Exception: {e}")
        return []

def test_projects():
    """测试项目列表"""
    print("\n=== 测试 3: 项目列表 ===")
    try:
        r = requests.get(f"{BASE_URL}/projects", timeout=5)
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            projects = data.get("data", [])
            print(f"共有 {len(projects)} 个项目")
            for proj in projects:
                if proj['id'] != 1:  # Skip __free__
                    print(f"  - ID {proj['id']}: {proj['name']}")
            return projects
        else:
            print(f"Error: {r.text}")
            return []
    except Exception as e:
        print(f"Exception: {e}")
        return []

def test_cards(project_id):
    """测试卡片列表"""
    print(f"\n=== 测试 4: 项目 {project_id} 的卡片列表 ===")
    try:
        r = requests.get(f"{BASE_URL}/projects/{project_id}/cards", timeout=5)
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            cards = data.get("data", [])
            print(f"共有 {len(cards)} 张卡片")
            for card in cards[:10]:  # Only show first 10
                print(f"  - ID {card['id']}: {card['title']} ({card.get('card_type_name', 'Unknown')})")
            return cards
        else:
            print(f"Error: {r.text}")
            return []
    except Exception as e:
        print(f"Exception: {e}")
        return []

def test_workflow_trigger(workflow_id, project_id, card_id):
    """测试工作流触发"""
    print(f"\n=== 测试 5: 触发工作流 {workflow_id} ===")
    payload = {
        "scope_json": {
            "project_id": project_id,
            "card_id": card_id,
            "self_id": card_id
        },
        "params_json": {}
    }
    try:
        r = requests.post(f"{BASE_URL}/workflows/{workflow_id}/run", json=payload, timeout=10)
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            run_data = data.get("data", {})
            print(f"Run ID: {run_data.get('id')}")
            print(f"Status: {run_data.get('status')}")
            print(f"Error: {run_data.get('error_json', {})}")
            return run_data
        else:
            print(f"Error: {r.text}")
            return None
    except Exception as e:
        print(f"Exception: {e}")
        return None

if __name__ == "__main__":
    print("=" * 60)
    print("NovelForge 功能测试")
    print("=" * 60)
    
    # Test 1: Workflows
    workflows = test_workflows_list()
    
    # Test 2: LLM Configs
    llm_configs = test_llm_configs()
    
    # Test 3: Projects
    projects = test_projects()
    
    # Test 4: Cards (if we have a project)
    if projects:
        test_project = next((p for p in projects if p['id'] != 1), None)
        if test_project:
            cards = test_cards(test_project['id'])
            
            # Test 5: Trigger a workflow (if we have cards and workflows)
            if cards and workflows and llm_configs:
                # Find a chapter card
                chapter_card = next((c for c in cards if c.get('card_type_name') == '章节正文'), None)
                if chapter_card:
                    # Try workflow 4 (智能章节审计与同步)
                    workflow_4 = next((w for w in workflows if w['id'] == 4), None)
                    if workflow_4:
                        print(f"\n尝试触发: {workflow_4['name']}")
                        test_workflow_trigger(4, test_project['id'], chapter_card['id'])
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
