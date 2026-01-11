import requests

# 测试后端API是否正常工作
try:
    response = requests.get('http://localhost:8081/api/tasks')
    print(f'API响应状态码: {response.status_code}')
    print(f'API响应内容: {response.text}')
    print('API测试成功！')
except Exception as e:
    print(f'API测试失败: {e}')
