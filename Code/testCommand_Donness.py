import requests

# 定义API的URL
url = "http://192.168.100.64:7999/api/v1/cooking/voice-command"  # 替换为实际的API地址

# 定义要发送的数据
data = {
    "voice_command": 1  
}

# 发送POST请求
response = requests.post(url, json=data)

# 打印响应结果
print(f"状态码: {response.status_code}")
print(f"响应内容: {response.text}")