from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QTextEdit, QPushButton, QFileDialog, 
    QMessageBox, QFrame, QGroupBox, QProgressBar
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QIcon
from pathlib import Path
from core.translation import TranslationEngine
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY
import os
import time

# PDF字体设置（保留原始PDF生成功能）
pdfmetrics.registerFont(TTFont('SimSun', 'SimSun.ttf'))
styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name='Chinese', 
                        fontName='SimSun',
                        fontSize=12,
                        leading=14,
                        alignment=TA_JUSTIFY))

class TranslationThread(QThread):
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

class MainWindow(QMainWindow):
    def __init__(self, translation_engine: TranslationEngine):
        super().__init__()
        self.translation_engine = translation_engine
        self.init_ui()
        self.translation_thread = None
        
    def init_ui(self):
        self.setWindowTitle('学术文献翻译工具')
        self.setGeometry(100, 100, 1000, 800)
        
        # 设置窗口图标
        if os.path.exists('icon.png'):
            self.setWindowIcon(QIcon('icon.png'))
        
        # 中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        
        # 顶部控制面板
        control_panel = QGroupBox("翻译设置")
        control_panel.setStyleSheet("""
            QGroupBox {
                font-size: 14px;
                font-weight: bold;
                border: 1px solid #ddd;
                border-radius: 5px;
                margin-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px;
            }
        """)
        
        control_layout = QHBoxLayout()
        control_layout.setContentsMargins(10, 20, 10, 10)
        
        # 翻译服务选择
        service_group = QWidget()
        service_layout = QVBoxLayout(service_group)
        service_layout.setContentsMargins(0, 0, 0, 0)
        service_layout.addWidget(QLabel('翻译服务:'))
        self.service_combo = QComboBox()
        self.service_combo.addItems(self.translation_engine.get_available_translators())
        self.service_combo.setStyleSheet("""
            QComboBox {
                padding: 5px;
                border: 1px solid #ccc;
                border-radius: 3px;
                min-width: 150px;
            }
        """)
        service_layout.addWidget(self.service_combo)
        control_layout.addWidget(service_group)
        
        # 语言选择
        lang_group = QWidget()
        lang_layout = QVBoxLayout(lang_group)
        lang_layout.setContentsMargins(0, 0, 0, 0)
        lang_layout.addWidget(QLabel('源语言:'))
        self.src_lang_combo = QComboBox()
        self.src_lang_combo.addItems(['en', 'zh', 'ja', 'fr'])
        self.src_lang_combo.setCurrentText('en')
        self.src_lang_combo.setStyleSheet("""
            QComboBox {
                padding: 5px;
                border: 1px solid #ccc;
                border-radius: 3px;
                min-width: 100px;
            }
        """)
        lang_layout.addWidget(self.src_lang_combo)
        control_layout.addWidget(lang_group)
        
        lang_group2 = QWidget()
        lang_layout2 = QVBoxLayout(lang_group2)
        lang_layout2.setContentsMargins(0, 0, 0, 0)
        lang_layout2.addWidget(QLabel('目标语言:'))
        self.target_lang_combo = QComboBox()
        self.target_lang_combo.addItems(['zh', 'en'])
        self.target_lang_combo.setCurrentText('zh')
        self.target_lang_combo.setStyleSheet("""
            QComboBox {
                padding: 5px;
                border: 1px solid #ccc;
                border-radius: 3px;
                min-width: 100px;
            }
        """)
        lang_layout2.addWidget(self.target_lang_combo)
        control_layout.addWidget(lang_group2)
        
        # 按钮组
        btn_group = QWidget()
        btn_layout = QHBoxLayout(btn_group)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(10)
        
        self.open_pdf_btn = QPushButton('打开PDF')
        self.open_pdf_btn.setStyleSheet(self.get_button_style())
        self.open_pdf_btn.clicked.connect(self.on_open_pdf)
        btn_layout.addWidget(self.open_pdf_btn)
        
        self.translate_btn = QPushButton('翻译')
        self.translate_btn.setStyleSheet(self.get_button_style("#4CAF50"))
        self.translate_btn.clicked.connect(self.on_translate)
        btn_layout.addWidget(self.translate_btn)
        
        control_layout.addWidget(btn_group)
        
        # 导出按钮组
        export_btn_group = QWidget()
        export_btn_layout = QHBoxLayout(export_btn_group)
        export_btn_layout.setContentsMargins(0, 0, 0, 0)
        export_btn_layout.setSpacing(10)
        
        self.save_btn = QPushButton('保存为TXT')
        self.save_btn.setStyleSheet(self.get_button_style("#2196F3"))
        self.save_btn.clicked.connect(self.on_save)
        export_btn_layout.addWidget(self.save_btn)
        
        self.export_pdf_btn = QPushButton('导出为PDF')
        self.export_pdf_btn.setStyleSheet(self.get_button_style("#FF9800"))
        self.export_pdf_btn.clicked.connect(self.on_export_pdf)
        export_btn_layout.addWidget(self.export_pdf_btn)
        
        control_layout.addWidget(export_btn_group)
        
        control_panel.setLayout(control_layout)
        main_layout.addWidget(control_panel)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ddd;
                border-radius: 3px;
                text-align: center;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                width: 10px;
            }
        """)
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)
        
        # 文本编辑区域
        text_edit_panel = QWidget()
        text_edit_layout = QHBoxLayout(text_edit_panel)
        text_edit_layout.setContentsMargins(0, 0, 0, 0)
        text_edit_layout.setSpacing(15)
        
        # 输入文本区域
        input_group = QGroupBox("原文")
        input_layout = QVBoxLayout()
        self.input_text = QTextEdit()
        self.input_text.setPlaceholderText("输入文本或打开PDF文件...")
        self.input_text.setStyleSheet(self.get_textedit_style())
        input_layout.addWidget(self.input_text)
        input_group.setLayout(input_layout)
        text_edit_layout.addWidget(input_group)
        
        # 输出文本区域
        output_group = QGroupBox("译文")
        output_layout = QVBoxLayout()
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setPlaceholderText("翻译结果将显示在这里...")
        self.output_text.setStyleSheet(self.get_textedit_style())
        output_layout.addWidget(self.output_text)
        output_group.setLayout(output_layout)
        text_edit_layout.addWidget(output_group)
        
        main_layout.addWidget(text_edit_panel)
        
        # 状态栏
        self.statusBar().showMessage("就绪")
        
        # 初始化状态
        if self.translation_engine.get_available_translators():
            self.translation_engine.set_current_translator(
                self.translation_engine.get_available_translators()[0])
    
    def get_button_style(self, color="#607D8B"):
        """生成按钮样式表"""
        return f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                padding: 8px 16px;
                text-align: center;
                text-decoration: none;
                font-size: 14px;
                margin: 4px 2px;
                border-radius: 4px;
                min-width: 100px;
            }}
            QPushButton:hover {{
                background-color: {self.darken_color(color)};
            }}
            QPushButton:pressed {{
                background-color: {self.darken_color(color, 20)};
            }}
            QPushButton:disabled {{
                background-color: #cccccc;
                color: #666666;
            }}
        """
    
    def get_textedit_style(self):
        """生成文本编辑框样式表"""
        return """
            QTextEdit {
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 8px;
                font-size: 14px;
                background-color: white;
            }
            QScrollBar:vertical {
                border: none;
                background: #f1f1f1;
                width: 10px;
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:vertical {
                background: #888;
                min-height: 20px;
                border-radius: 4px;
            }
            QScrollBar::add-line:vertical {
                border: none;
                background: none;
            }
            QScrollBar::sub-line:vertical {
                border: none;
                background: none;
            }
        """
    
    def darken_color(self, hex_color, amount=10):
        """使颜色变暗"""
        hex_color = hex_color.lstrip('#')
        rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        darkened = tuple(max(0, x - amount) for x in rgb)
        return '#%02x%02x%02x' % darkened
    
    def on_open_pdf(self):
        """打开PDF文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择PDF文件", "", "PDF文件 (*.pdf)")
        
        if file_path:
            try:
                with open(file_path, 'rb') as f:
                    self.input_text.setPlainText(f"已加载PDF文件: {Path(file_path).name}")
                    self.current_file = file_path
                    self.statusBar().showMessage(f"已加载文件: {Path(file_path).name}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"无法打开文件:\n{str(e)}")
    
    def on_translate(self):
        if not hasattr(self, 'current_file'):
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
    
    def on_translation_finished(self, result):
        """翻译完成处理"""
        self.output_text.setPlainText(result)
        self.set_buttons_enabled(True)
        self.progress_bar.setVisible(False)
        self.statusBar().showMessage("翻译完成", 3000)
        QMessageBox.information(self, "完成", "翻译已完成")
        
    def on_translation_error(self, error_msg):
        """翻译错误处理"""
        QMessageBox.critical(self, "错误", f"翻译失败:\n{error_msg}")
        self.set_buttons_enabled(True)
        self.progress_bar.setVisible(False)
        self.statusBar().showMessage("翻译出错", 3000)
        
    def set_buttons_enabled(self, enabled):
        """统一设置按钮状态"""
        self.open_pdf_btn.setEnabled(enabled)
        self.translate_btn.setEnabled(enabled)
        self.save_btn.setEnabled(enabled)
        self.export_pdf_btn.setEnabled(enabled)
        
    def on_save(self):
        """保存翻译结果"""
        if not self.output_text.toPlainText():
            QMessageBox.warning(self, "警告", "没有可保存的内容")
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存文件", "", "文本文件 (*.txt);;所有文件 (*.*)")
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.output_text.toPlainText())
                QMessageBox.information(self, "成功", "文件已保存")
                self.statusBar().showMessage(f"文件已保存到: {file_path}", 3000)
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存失败:\n{str(e)}")
                
    def on_export_pdf(self):
        """将翻译结果导出为PDF"""
        if not self.output_text.toPlainText():
            QMessageBox.warning(self, "警告", "没有可导出的内容")
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出PDF", "", "PDF文件 (*.pdf);;所有文件 (*.*)")
        
        if file_path:
            try:
                self.generate_pdf(file_path, 
                               self.input_text.toPlainText(),
                               self.output_text.toPlainText())
                QMessageBox.information(self, "成功", "PDF导出成功")
                self.statusBar().showMessage(f"PDF已导出到: {file_path}", 3000)
            except Exception as e:
                QMessageBox.critical(self, "错误", f"PDF导出失败:\n{str(e)}")
    
    def generate_pdf(self, file_path, original_text, translated_text):
        """生成PDF文件"""
        doc = SimpleDocTemplate(file_path, pagesize=letter,
                              rightMargin=72, leftMargin=72,
                              topMargin=72, bottomMargin=18)
        
        # 准备PDF内容
        story = []
        
        # 添加标题
        title = "<b>学术文献翻译结果</b>"
        story.append(Paragraph(title, styles["Chinese"]))
        story.append(Spacer(1, 12))
        
        # 添加翻译文本
        story.append(Paragraph("<b>译文:</b>", styles["Chinese"]))
        story.append(Spacer(1, 6))
        story.append(Paragraph(translated_text.replace('\n', '<br/>'), styles["Chinese"]))
        
        # 生成PDF
        doc.build(story)