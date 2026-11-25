"""本地 Ollama + bge-m3 向量模型验证脚本。

在 PyCharm 里 Run 本文件，预期输出：
    向量维度: 1024
    前5个值: [...]
"""
import ollama

# 调用 embed 方法
response = ollama.embed(
    model="bge-m3",  # 替换为你下载的模型名称
    input="人工智能正在改变软件开发的方式123",
)

# 获取向量（注意：[0] 取出本次输入对应的向量，embeddings 是嵌套列表）
embedding = response["embeddings"][0]

print(f"向量维度: {len(embedding)}")
print(f"前5个值: {embedding[:5]}")
