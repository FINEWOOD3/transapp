#!/usr/bin/env python3
import sys
import logging
from pathlib import Path
from configparser import ConfigParser
from PyQt5.QtWidgets import QApplication, QMessageBox
from src.core.translation import TranslationEngine

# 初始化日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('translation_app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def load_config(config_path: str = 'config/config.ini') -> ConfigParser:
    """
    加载配置文件
    :param config_path: 配置文件路径
    :return: ConfigParser 对象
    :raises: FileNotFoundError 当配置文件不存在时
    """
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_file.absolute()}")

    config = ConfigParser()
    try:
        config.read(config_file, encoding='utf-8')
        logger.info(f"成功加载配置文件: {config_file}")
        return config
    except Exception as e:
        logger.error(f"配置文件解析失败: {str(e)}")
        raise

def setup_translation_engine(config: ConfigParser) -> 'TranslationEngine':
    """
    初始化翻译引擎
    :param config: 配置对象
    :return: 配置好的TranslationEngine实例
    """
    from core.translation import TranslationEngine
    from src.services.baidu_trans import BaiduTranslator
    
    engine = TranslationEngine()
    
    # 百度翻译配置
    if config.has_section('baidu'):
        try:
            baidu_cfg = {
                'appid': config.get('baidu', 'appid'),
                'secret_key': config.get('baidu', 'secret_key')
            }
            baidu_trans = BaiduTranslator()
            baidu_trans.configure(baidu_cfg)
            engine.add_translator(baidu_trans.name(), baidu_trans)
            logger.info("百度翻译引擎初始化成功")
        except Exception as e:
            logger.warning(f"百度翻译配置失败: {str(e)}")
            # 可以继续运行，只是没有百度翻译功能
    
    # 添加其他翻译引擎...
    # if config.has_section('google'):
    #     ...
    
    if not engine.get_available_translators():
        logger.warning("没有可用的翻译引擎！")
    
    return engine

def show_error_dialog(message: str):
    """显示错误对话框"""
    app = QApplication.instance() or QApplication(sys.argv)
    QMessageBox.critical(
        None,
        "应用程序错误",
        message,
        QMessageBox.Ok
    )

def main():
    try:
        app = QApplication(sys.argv)
        
        # 设置应用程序信息
        app.setApplicationName("学术文献翻译工具")
        app.setApplicationVersion("1.0.0")
        app.setStyle('Fusion')  # 使用Fusion风格，跨平台一致
        
        # 加载配置
        try:
            config = load_config()
        except FileNotFoundError as e:
            logger.error(str(e))
            show_error_dialog(f"配置文件加载失败:\n{str(e)}\n请确保config.ini存在")
            return 1
        
        # 初始化翻译引擎
        try:
            engine = setup_translation_engine(config)
        except Exception as e:
            logger.error(f"翻译引擎初始化失败: {str(e)}")
            show_error_dialog(f"翻译引擎初始化失败:\n{str(e)}")
            return 1
        
        # 创建主窗口
        from src.ui.main_window import MainWindow
        try:
            window = MainWindow(engine)
            window.show()
            logger.info("应用程序启动成功")
            return app.exec_()
        except Exception as e:
            logger.error(f"窗口创建失败: {str(e)}")
            show_error_dialog(f"主窗口初始化失败:\n{str(e)}")
            return 1
            
    except Exception as e:
        logger.critical(f"未处理的异常: {str(e)}", exc_info=True)
        show_error_dialog(f"致命错误:\n{str(e)}")
        return 1
    finally:
        logger.info("应用程序退出")

if __name__ == "__main__":
    sys.exit(main())