import requests
import json

# 测试灵感助手接口
url = "http://127.0.0.1:8000/api/ai/assistant/chat"

payload = {
    "user_prompt": "你好，请简单介绍一下你自己",
    "context_info": "",
    "llm_config_id": 4,
    "project_id": 1,
    "prompt_name": "灵感对话",
    "thinking_enabled": False
}

print("发送测试请求...")
print(f"URL: {url}")
print(f"Payload: {json.dumps(payload, ensure_ascii=False, indent=2)}")
print("\n" + "="*80)

try:
    response = requests.post(url, json=payload, stream=True, timeout=30)
    print(f"状态码: {response.status_code}")
    print(f"响应头: {dict(response.headers)}")
    print("\n流式响应内容:")
    print("-"*80)
    
    chunk_count = 0
    for line in response.iter_lines():
        if line:
            chunk_count += 1
            decoded = line.decode('utf-8')
            print(f"[Chunk {chunk_count}] {decoded}")
            
            # 尝试解析 SSE 格式
            if decoded.startswith("data: "):
                data_str = decoded[6:]  # 去掉 "data: " 前缀
                try:
                    data = json.loads(data_str)
                    print(f"  → 解析后: {json.dumps(data, ensure_ascii=False, indent=4)}")
                except json.JSONDecodeError as e:
                    print(f"  → JSON解析失败: {e}")
    
    print("-"*80)
    print(f"总共接收到 {chunk_count} 个数据块")
    
except requests.exceptions.Timeout:
    print("❌ 请求超时")
except requests.exceptions.ConnectionError as e:
    print(f"❌ 连接错误: {e}")
except Exception as e:
    print(f"❌ 发生错误: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
