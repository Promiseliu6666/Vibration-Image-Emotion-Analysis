from openai import OpenAI
import os
client = OpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)

try:
    models = client.models.list()
    print("可用模型：")
    for m in models.data:
        print(m.id)
except Exception as e:
    print("获取模型列表失败：", e)

