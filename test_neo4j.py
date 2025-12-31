import os
from neo4j import GraphDatabase

# 从环境变量读取配置
uri = os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
user = os.getenv("NEO4J_USER", "neo4j")
password = os.getenv("NEO4J_PASSWORD", "12345678")

print(f"测试 Neo4j 连接...")
print(f"URI: {uri}")
print(f"User: {user}")
print(f"Password: {'*' * len(password)}")
print()

try:
    driver = GraphDatabase.driver(uri, auth=(user, password))
    with driver.session() as session:
        result = session.run("RETURN 'Connection successful!' AS message")
        message = result.single()[0]
        print(f"✅ {message}")
        
        # 测试写入权限
        session.run("MERGE (n:TestNode {name: 'test'}) RETURN n")
        print("✅ 写入权限正常")
        
        # 清理测试节点
        session.run("MATCH (n:TestNode {name: 'test'}) DELETE n")
        print("✅ 删除权限正常")
        
    driver.close()
    print("\n✅ Neo4j 连接和权限测试全部通过！")
    
except Exception as e:
    print(f"\n❌ 连接失败: {type(e).__name__}")
    print(f"错误详情: {str(e)}")
    print("\n可能的解决方案:")
    print("1. 检查 Neo4j 是否正在运行")
    print("2. 检查密码是否正确（默认是 'neo4j'，首次登录后会要求修改）")
    print("3. 尝试使用 bolt:// 替代 neo4j://")
    print("4. 检查 Neo4j 是否监听在 7687 端口")
