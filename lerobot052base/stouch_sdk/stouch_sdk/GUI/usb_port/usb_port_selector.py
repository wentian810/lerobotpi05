import sys
import cv2
import numpy as np
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QImage, QPixmap
from .usb_port_scanner import USBPortScanner, PortInfo
import json
import os
from datetime import datetime

class USBPortSelector(QtWidgets.QDialog):
    """USB端口选择对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scanner = USBPortScanner()
        self.current_port_info = None
        self.preview_timer = QTimer()
        self.preview_timer.timeout.connect(self.update_preview)
        # 配置文件始终保存在当前目录下
        self.config_file = "./usb_port.json"
        
        # 设置对话框属性
        self.setWindowTitle("USB端口选择")
        self.setModal(True)
        self.resize(800, 600)
        
        # 创建界面
        self.setup_ui()
        
        # 扫描可用端口
        self.scan_ports()
    
    def setup_ui(self):
        """设置用户界面"""
        layout = QtWidgets.QVBoxLayout()
        
        # 标题
        title_label = QtWidgets.QLabel("请选择传感器USB端口")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # 主内容区域
        main_layout = QtWidgets.QHBoxLayout()
        
        # 左侧：端口选择区域
        left_layout = QtWidgets.QVBoxLayout()
        
        # 端口选择
        port_layout = QtWidgets.QHBoxLayout()
        port_layout.addWidget(QtWidgets.QLabel("选择端口:"))
        
        self.port_combo = QtWidgets.QComboBox()
        self.port_combo.currentTextChanged.connect(self.on_port_selected)
        port_layout.addWidget(self.port_combo)
        
        # 重新扫描按钮
        self.rescan_btn = QtWidgets.QPushButton("重新扫描")
        self.rescan_btn.clicked.connect(self.scan_ports)
        self.rescan_btn.setStyleSheet("QPushButton { background-color: #3498db; color: white; font-weight: bold; }")
        port_layout.addWidget(self.rescan_btn)
        
        left_layout.addLayout(port_layout)
        
        # 端口信息显示
        self.port_info_label = QtWidgets.QLabel("请选择端口查看信息")
        self.port_info_label.setStyleSheet("""
            QLabel {
                background-color: #ecf0f1;
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                padding: 10px;
                font-family: monospace;
            }
        """)
        self.port_info_label.setWordWrap(True)
        left_layout.addWidget(self.port_info_label)
        
        # 测试连接按钮
        self.test_btn = QtWidgets.QPushButton("测试连接")
        self.test_btn.clicked.connect(self.test_connection)
        self.test_btn.setStyleSheet("QPushButton { background-color: #27ae60; color: white; font-weight: bold; }")
        self.test_btn.setEnabled(False)
        left_layout.addWidget(self.test_btn)
        
        # 连接状态
        self.status_label = QtWidgets.QLabel("状态: 未连接")
        self.status_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
        left_layout.addWidget(self.status_label)
        
        left_layout.addStretch()
        main_layout.addLayout(left_layout, 1)
        
        # 右侧：预览区域
        right_layout = QtWidgets.QVBoxLayout()
        
        # 预览标题
        preview_title = QtWidgets.QLabel("摄像头预览")
        preview_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #2c3e50;")
        preview_title.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(preview_title)
        
        # 预览区域
        self.preview_label = QtWidgets.QLabel("选择端口后开始预览")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("""
            QLabel {
                background-color: #2c3e50;
                color: #ecf0f1;
                border: 2px solid #34495e;
                border-radius: 10px;
                font-size: 14px;
                min-height: 300px;
            }
        """)
        right_layout.addWidget(self.preview_label)
        
        # 预览控制
        preview_control_layout = QtWidgets.QHBoxLayout()
        
        self.start_preview_btn = QtWidgets.QPushButton("开始预览")
        self.start_preview_btn.clicked.connect(self.start_preview)
        self.start_preview_btn.setStyleSheet("QPushButton { background-color: #e67e22; color: white; font-weight: bold; }")
        self.start_preview_btn.setEnabled(False)
        preview_control_layout.addWidget(self.start_preview_btn)
        
        self.stop_preview_btn = QtWidgets.QPushButton("停止预览")
        self.stop_preview_btn.clicked.connect(self.stop_preview)
        self.stop_preview_btn.setStyleSheet("QPushButton { background-color: #e74c3c; color: white; font-weight: bold; }")
        self.stop_preview_btn.setEnabled(False)
        preview_control_layout.addWidget(self.stop_preview_btn)
        
        right_layout.addLayout(preview_control_layout)
        main_layout.addLayout(right_layout, 2)
        
        layout.addLayout(main_layout)
        
        # 按钮区域
        button_layout = QtWidgets.QHBoxLayout()
        
        # 加载上次配置
        self.load_last_config_btn = QtWidgets.QPushButton("加载上次配置")
        self.load_last_config_btn.clicked.connect(self.load_last_config)
        self.load_last_config_btn.setStyleSheet("QPushButton { background-color: #9b59b6; color: white; font-weight: bold; }")
        button_layout.addWidget(self.load_last_config_btn)
        
        button_layout.addStretch()
        
        # 确定和取消按钮
        self.cancel_btn = QtWidgets.QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        self.cancel_btn.setStyleSheet("QPushButton { background-color: #95a5a6; color: white; font-weight: bold; }")
        button_layout.addWidget(self.cancel_btn)
        
        self.ok_btn = QtWidgets.QPushButton("确定")
        self.ok_btn.clicked.connect(self.accept)
        self.ok_btn.setStyleSheet("QPushButton { background-color: #27ae60; color: white; font-weight: bold; }")
        self.ok_btn.setEnabled(False)
        button_layout.addWidget(self.ok_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def scan_ports(self):
        """扫描可用端口"""
        self.rescan_btn.setEnabled(False)
        self.rescan_btn.setText("扫描中...")
        
        # 清空现有端口
        self.port_combo.clear()
        self.scanner.release_all_ports()
        
        # 扫描端口
        available_ports = self.scanner.scan_available_ports()
        
        if available_ports:
            for port_info in available_ports:
                self.port_combo.addItem(port_info.get_info_string(), port_info.port)
            
            # 选择第一个可用端口
            self.port_combo.setCurrentIndex(0)
            self.on_port_selected(self.port_combo.currentText())
        else:
            self.port_combo.addItem("未找到可用端口")
            self.port_info_label.setText("未找到可用的USB摄像头端口")
            self.status_label.setText("状态: 未找到设备")
            self.status_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
        
        self.rescan_btn.setEnabled(True)
        self.rescan_btn.setText("重新扫描")
    
    def on_port_selected(self, text):
        """端口选择处理"""
        if not text or "未找到" in text:
            return
        
        # 获取选中的端口号
        port = self.port_combo.currentData()
        if port is None:
            return
        
        # 获取端口信息
        self.current_port_info = self.scanner.get_port_by_number(port)
        if self.current_port_info:
            self.update_port_info()
            self.test_btn.setEnabled(True)
            self.start_preview_btn.setEnabled(True)
        else:
            self.port_info_label.setText("端口信息获取失败")
            self.test_btn.setEnabled(False)
            self.start_preview_btn.setEnabled(False)
    
    def update_port_info(self):
        """更新端口信息显示"""
        if not self.current_port_info:
            return
        
        info_text = f"""
端口信息:
• 端口号: {self.current_port_info.port}
• 名称: {self.current_port_info.name}
• 分辨率: {self.current_port_info.resolution[0]}x{self.current_port_info.resolution[1]}
• 帧率: {self.current_port_info.fps:.1f} fps
• 状态: {self.current_port_info.status}
• 可用性: {'是' if self.current_port_info.is_available else '否'}
        """.strip()
        
        self.port_info_label.setText(info_text)
    
    def test_connection(self):
        """测试端口连接"""
        if not self.current_port_info:
            return
        
        self.test_btn.setEnabled(False)
        self.test_btn.setText("测试中...")
        
        success, message = self.current_port_info.test_connection()
        
        if success:
            self.status_label.setText("状态: 连接成功")
            self.status_label.setStyleSheet("color: #27ae60; font-weight: bold;")
            self.ok_btn.setEnabled(True)
        else:
            self.status_label.setText(f"状态: 连接失败 - {message}")
            self.status_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
            self.ok_btn.setEnabled(False)
        
        self.test_btn.setEnabled(True)
        self.test_btn.setText("测试连接")
        self.update_port_info()
    
    def start_preview(self):
        """开始预览"""
        if not self.current_port_info or not self.current_port_info.is_available:
            QtWidgets.QMessageBox.warning(self, "错误", "请先选择一个可用的端口")
            return
        
        try:
            # 确保摄像头连接
            if not self.current_port_info.cap or not self.current_port_info.cap.isOpened():
                self.current_port_info.cap = cv2.VideoCapture(self.current_port_info.port)
            
            if self.current_port_info.cap.isOpened():
                self.preview_timer.start(33)  # 30fps
                self.start_preview_btn.setEnabled(False)
                self.stop_preview_btn.setEnabled(True)
                self.status_label.setText("状态: 预览中")
                self.status_label.setStyleSheet("color: #f39c12; font-weight: bold;")
            else:
                QtWidgets.QMessageBox.warning(self, "错误", "无法打开摄像头预览")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "错误", f"启动预览时出错: {str(e)}")
    
    def stop_preview(self):
        """停止预览"""
        self.preview_timer.stop()
        self.start_preview_btn.setEnabled(True)
        self.stop_preview_btn.setEnabled(False)
        self.preview_label.setText("预览已停止")
        self.status_label.setText("状态: 预览已停止")
        self.status_label.setStyleSheet("color: #95a5a6; font-weight: bold;")
    
    def update_preview(self):
        """更新预览画面"""
        if not self.current_port_info or not self.current_port_info.cap:
            return
        
        try:
            ret, frame = self.current_port_info.cap.read()
            if ret and frame is not None:
                # 调整预览大小
                height, width = frame.shape[:2]
                max_width = 400
                max_height = 300
                
                if width > max_width or height > max_height:
                    scale = min(max_width / width, max_height / height)
                    new_width = int(width * scale)
                    new_height = int(height * scale)
                    frame = cv2.resize(frame, (new_width, new_height))
                
                # 转换为QImage
                rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb_image.shape
                bytes_per_line = ch * w
                qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
                
                # 显示预览
                pixmap = QPixmap.fromImage(qt_image)
                self.preview_label.setPixmap(pixmap)
            else:
                self.stop_preview()
                QtWidgets.QMessageBox.warning(self, "错误", "无法获取视频流")
        except Exception as e:
            self.stop_preview()
            QtWidgets.QMessageBox.critical(self, "错误", f"预览更新时出错: {str(e)}")
    
    def load_last_config(self):
        """加载上次配置"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                last_port = config.get('last_selected_port')
                if last_port is not None:
                    # 查找对应的端口
                    for i in range(self.port_combo.count()):
                        if self.port_combo.itemData(i) == last_port:
                            self.port_combo.setCurrentIndex(i)
                            self.on_port_selected(self.port_combo.currentText())
                            QtWidgets.QMessageBox.information(self, "成功", f"已加载上次配置: USB端口{last_port}")
                            return
                
                QtWidgets.QMessageBox.information(self, "提示", "未找到上次的端口配置")
            else:
                QtWidgets.QMessageBox.information(self, "提示", "没有找到配置文件")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "错误", f"加载配置时出错: {str(e)}")
    
    def save_config(self, selected_port):
        """保存配置"""
        try:
            config = {
                'last_selected_port': selected_port,
                'save_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'port_info': {
                    'port': selected_port,
                    'name': f'USB端口{selected_port}'
                }
            }
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            print(f"配置已保存: USB端口{selected_port}")
        except Exception as e:
            print(f"保存配置时出错: {e}")
    
    def get_selected_port(self):
        """获取选中的端口号"""
        if self.current_port_info:
            return self.current_port_info.port
        return None
    
    def accept(self):
        """确定按钮处理"""
        if not self.current_port_info:
            QtWidgets.QMessageBox.warning(self, "错误", "请先选择一个端口")
            return
        
        if not self.current_port_info.is_available:
            QtWidgets.QMessageBox.warning(self, "错误", "选中的端口不可用")
            return
        
        # 停止预览
        self.stop_preview()
        self.current_port_info.cap.release()
        
        # 保存配置
        selected_port = self.get_selected_port()
        if selected_port is not None:
            self.save_config(selected_port)
        
        # 释放其他端口资源
        for port_info in self.scanner.available_ports:
            if port_info.port != selected_port:
                port_info.release()
        
        super().accept()
    
    def reject(self):
        """取消按钮处理"""
        # 停止预览
        self.stop_preview()
        
        # 释放所有端口资源
        self.scanner.release_all_ports()
        
        super().reject()
    
    def closeEvent(self, event):
        """关闭事件处理"""
        # 停止预览
        self.stop_preview()
        
        # 释放所有端口资源
        self.scanner.release_all_ports()
        
        event.accept()
