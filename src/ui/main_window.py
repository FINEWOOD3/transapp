import os
from pathlib import Path
from PyQt5.QtWidgets import (QMainWindow, QFileDialog, QMessageBox, 
                            QProgressBar, QTextEdit, QPushButton, QComboBox)
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.uic import loadUiType

from src.core.pdf_parser import PDFParser
from src.core.pdf_generator import PDFGenerator
from src.core.translation import TranslationEngine

# 加载UI文件
UI_FILE = Path(__file__).parent / "main_window.ui"
WindowUI, WindowBase = loadUiType(str(UI_FILE))

class TranslationThread(QThread):
    """翻译线程"""
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, engine, file_path, src_lang, target_lang):
        super().__init__()
        self.engine = engine
        self.file_path = file_path
        self.src_lang = src_lang
        self.target_lang = target_lang

    def run(self):
        try:
            result = self.engine.translate_pdf(
                self.file_path,
                self.src_lang,
                self.target_lang,
                progress_callback=self.progress.emit
            )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))

class PDFGenerationThread(QThread):
    """PDF生成线程"""
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, generator, file_path, output_path):
        super().__init__()
        self.generator = generator
        self.file_path = file_path
        self.output_path = output_path

    def run(self):
        try:
            success = self.generator.generate_pdf(
                self.file_path,
                self.output_path,
                title="Translated Document"
            )
            if success:
                self.finished.emit(self.output_path)
            else:
                self.error.emit("PDF generation failed")
        except Exception as e:
            self.error.emit(str(e))

class MainWindow(WindowBase, WindowUI):
    """主窗口类"""
    
    def __init__(self, translation_engine: TranslationEngine):
        super().__init__()
        self.setupUi(self)
        
        # 初始化核心组件
        self.translation_engine = translation_engine
        self.pdf_parser = PDFParser()
        self.pdf_generator = PDFGenerator()
        self.current_file = None
        
        # 设置UI初始状态
        self.init_ui()
        
        # 连接信号槽
        self.connect_signals()

    def init_ui(self):
        """初始化UI状态"""
        self.setWindowTitle('学术文献翻译工具')
        self.progress_bar.setVisible(False)
        self.export_pdf_btn.setEnabled(False)
        
        # 初始化语言选择
        self.src_lang_combo.addItems(['en', 'zh', 'ja', 'fr'])
        self.target_lang_combo.addItems(['zh', 'en'])
        
        # 设置默认值
        self.src_lang_combo.setCurrentText('en')
        self.target_lang_combo.setCurrentText('zh')

    def connect_signals(self):
        """连接信号与槽"""
        self.open_pdf_btn.clicked.connect(self.on_open_pdf)
        self.translate_btn.clicked.connect(self.on_translate)
        self.save_btn.clicked.connect(self.on_save_txt)
        self.export_pdf_btn.clicked.connect(self.on_export_pdf)

    def on_open_pdf(self):
        """打开PDF文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择PDF文件", "", "PDF文件 (*.pdf)")
        
        if file_path:
            try:
                # 解析PDF并显示基本信息
                elements = self.pdf_parser.parse_and_store(file_path)
                self.input_text.setPlainText(
                    f"已加载PDF文件: {Path(file_path).name}\n\n"
                    f"总页数: {len(set(e.page_num for e in elements))}\n"
                    f"元素总数: {len(elements)}\n"
                    f"文本块: {len([e for e in elements if e.element_type == 'text'])}\n"
                    f"图片: {len([e for e in elements if e.element_type == 'figure'])}"
                )
                self.current_file = file_path
                self.statusBar().showMessage(f"已加载文件: {Path(file_path).name}")
                self.export_pdf_btn.setEnabled(True)
            except Exception as e:
                QMessageBox.critical(self, "错误", f"无法解析PDF文件:\n{str(e)}")

    def on_translate(self):
        """执行翻译"""
        if not self.current_file:
            QMessageBox.warning(self, "警告", "请先打开PDF文件")
            return
            
        self.set_buttons_enabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.statusBar().showMessage("正在翻译...")
        
        self.translation_thread = TranslationThread(
            self.translation_engine,
            self.current_file,
            self.src_lang_combo.currentText(),
            self.target_lang_combo.currentText()
        )
        self.translation_thread.progress.connect(self.progress_bar.setValue)
        self.translation_thread.finished.connect(self.on_translation_finished)
        self.translation_thread.error.connect(self.on_translation_error)
        self.translation_thread.start()

    def on_export_pdf(self):
        """导出翻译结果为PDF"""
        if not self.current_file:
            QMessageBox.warning(self, "警告", "请先打开PDF文件")
            return
            
        default_name = Path(self.current_file).stem + "_translated.pdf"
        output_path, _ = QFileDialog.getSaveFileName(
            self, "导出PDF", str(default_name), "PDF文件 (*.pdf)")
        
        if output_path:
            self.set_buttons_enabled(False)
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.statusBar().showMessage("正在生成PDF...")
            
            self.pdf_thread = PDFGenerationThread(
                self.pdf_generator,
                self.current_file,
                output_path
            )
            self.pdf_thread.finished.connect(self.on_pdf_generated)
            self.pdf_thread.error.connect(self.on_pdf_error)
            self.pdf_thread.start()

    def on_translation_finished(self, result):
        """翻译完成处理"""
        self.output_text.setPlainText(result)
        self.set_buttons_enabled(True)
        self.progress_bar.setVisible(False)
        self.statusBar().showMessage("翻译完成", 3000)

    def on_translation_error(self, error_msg):
        """翻译错误处理"""
        QMessageBox.critical(self, "错误", f"翻译失败:\n{error_msg}")
        self.set_buttons_enabled(True)
        self.progress_bar.setVisible(False)
        self.statusBar().showMessage("翻译出错", 3000)

    def on_pdf_generated(self, output_path):
        """PDF生成成功处理"""
        QMessageBox.information(self, "成功", f"PDF已保存到:\n{output_path}")
        self.statusBar().showMessage("PDF导出完成", 3000)
        self.progress_bar.setVisible(False)
        self.set_buttons_enabled(True)

    def on_pdf_error(self, error_msg):
        """PDF生成错误处理"""
        QMessageBox.critical(self, "错误", f"PDF导出失败:\n{error_msg}")
        self.statusBar().showMessage("PDF导出失败", 3000)
        self.progress_bar.setVisible(False)
        self.set_buttons_enabled(True)

    def on_save_txt(self):
        """保存翻译结果为TXT"""
        if not self.output_text.toPlainText():
            QMessageBox.warning(self, "警告", "没有可保存的内容")
            return
            
        default_name = Path(self.current_file).stem + "_translated.txt" if self.current_file else "translation.txt"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存文本文件", str(default_name), "文本文件 (*.txt)")
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.output_text.toPlainText())
                QMessageBox.information(self, "成功", "文本文件已保存")
                self.statusBar().showMessage(f"文件已保存: {file_path}", 3000)
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存失败:\n{str(e)}")

    def set_buttons_enabled(self, enabled):
        """设置按钮启用状态"""
        self.open_pdf_btn.setEnabled(enabled)
        self.translate_btn.setEnabled(enabled)
        self.save_btn.setEnabled(enabled)
        self.export_pdf_btn.setEnabled(enabled)

if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    engine = TranslationEngine()  # 需要实际初始化你的翻译引擎
    window = MainWindow(engine)
    window.show()
    sys.exit(app.exec_())