import requests
import hashlib
import random
import json
from typing import Optional
from src.core.translator import AbstractTranslator, TranslationResult

class BaiduTranslator(AbstractTranslator):
    def __init__(self):
        self.appid = ''
        self.secret_key = ''
        self.api_url = 'https://fanyi-api.baidu.com/api/trans/vip/translate'

    def name(self) -> str:
        return "Baidu Translate"

    def configure(self, config: dict):
        self.appid = config.get('appid', '')
        self.secret_key = config.get('secret_key', '')

    def translate(self, text: str, src_lang: str = 'en', target_lang: str = 'zh') -> Optional[TranslationResult]:
        if not self.appid or not self.secret_key:
            return None

        salt = random.randint(32768, 65536)
        sign = self.appid + text + str(salt) + self.secret_key
        sign = hashlib.md5(sign.encode()).hexdigest()

        params = {
            'q': text,
            'from': src_lang,
            'to': target_lang,
            'appid': self.appid,
            'salt': salt,
            'sign': sign
        }

        try:
            response = requests.get(self.api_url, params=params)
            result = json.loads(response.text)
            if 'trans_result' in result:
                trans_text = '\n'.join([item['dst'] for item in result['trans_result']])
                return TranslationResult(text, trans_text, src_lang, target_lang)
        except Exception as e:
            print(f"Baidu translate error: {e}")
        
        return None