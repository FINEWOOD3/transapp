import requests
import hashlib
import random

def test_baidu_api():
    appid = "20250512002355172"  # 替换为你的百度API ID
    secret_key = "U61SJn6nPiA4lVjARcSH"  # 替换为你的密钥
    url = "https://fapi.baidu.com/api/trans/vip/translate"
    
    text = "hello world"
    salt = random.randint(32768, 65536)
    sign = appid + text + str(salt) + secret_key
    sign = hashlib.md5(sign.encode()).hexdigest()
    
    params = {
        "q": text,
        "from": "en",
        "to": "zh",
        "appid": appid,
        "salt": salt,
        "sign": sign
    }
    
    try:
        response = requests.get(url, params=params)
        print("HTTP状态码:", response.status_code)
        print("API返回:", response.json())
    except Exception as e:
        print("请求失败:", e)

test_baidu_api()