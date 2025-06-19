# test_network.py
import socket
import requests

def test_connection():
    try:
        # 测试DNS
        print("解析IP:", socket.gethostbyname('api.fanyi.baidu.com'))
        
        # 测试HTTPS
        r = requests.get("https://api.fanyi.baidu.com", timeout=5)
        print("HTTP状态码:", r.status_code)
        
        return True
    except Exception as e:
        print("连接测试失败:", e)
        return False

if test_connection():
    print("网络正常，请检查API参数")
else:
    print("网络故障，请按文档排查")