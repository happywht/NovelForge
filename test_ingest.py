import requests

url = "http://127.0.0.1:8000/api/memory/ingest-relations"

# 测试数据
test_data = {
    "project_id": 1,
    "data": {
        "relations": [
            {
                "a": "测试角色A",
                "b": "测试角色B",
                "kind": "同门",
                "summary": "这是一个测试关系"
            }
        ]
    },
    "volume_number": 1,
    "chapter_number": 1
}

print("测试关系入图 API...")
print(f"URL: {url}")

try:
    response = requests.post(url, json=test_data, timeout=30)
    print(f"\n状态码: {response.status_code}")
    
    if response.status_code == 200:
        print("✅ API调用成功！")
        print(f"响应: {response.json()}")
    else:
        print(f"❌ API调用失败")
        print(f"响应: {response.json()}")
        
except Exception as e:
    print(f"❌ 请求失败: {e}")
