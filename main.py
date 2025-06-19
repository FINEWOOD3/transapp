import sys
from configparser import ConfigParser
from PyQt5.QtWidgets import QApplication
from src.ui.main_window import MainWindow
from core.translation import TranslationEngine
from src.services.baidu_trans import BaiduTranslator

def load_config():
    config = ConfigParser()
    config.read('config/config.ini')
    return config

def setup_translation_engine(config):
    engine = TranslationEngine()
    
    # 百度翻译
    if config.has_section('baidu'):
        baidu_trans = BaiduTranslator()
        baidu_trans.configure(dict(config['baidu']))
        engine.add_translator(baidu_trans.name(), baidu_trans)
    
    return engine

def main():
    app = QApplication(sys.argv)
    
    try:
        config = load_config()
        engine = setup_translation_engine(config)
        
        window = MainWindow(engine)
        window.show()
        sys.exit(app.exec_())
    except Exception as e:
        print(f"Application error: {e}")

if __name__ == "__main__":
    main()