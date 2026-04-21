import sys
import cv2
import numpy as np
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QFileDialog
from .parameter_manager import ParameterManager
from api.touch_sensor import TouchSensor

class RangeSlider(QtWidgets.QWidget):
    """双端范围滑动条控件"""
    rangeChanged = pyqtSignal(int, int)  # 信号：范围改变时发出 (low, high)

    def __init__(self, minimum=0, maximum=100, parent=None):
        super().__init__(parent)
        self._minimum = minimum
        self._maximum = maximum
        self._low = minimum
        self._high = maximum
        self._pressed_handle = None  # 当前被按下的滑块: 'low', 'high', None
        
        self.setMinimumHeight(30)
        self.setMinimumWidth(200)
        
        # 样式参数
        self._groove_height = 6
        self._handle_radius = 8
        self._margin = self._handle_radius + 2
    
    def setRange(self, minimum, maximum):
        """设置范围"""
        self._minimum = minimum
        self._maximum = maximum
        self._low = max(self._low, minimum)
        self._high = min(self._high, maximum)
        self.update()
    
    def setLow(self, value):
        """设置低值"""
        value = max(self._minimum, min(value, self._high - 1))
        if self._low != value:
            self._low = value
            self.rangeChanged.emit(self._low, self._high)
            self.update()
    
    def setHigh(self, value):
        """设置高值"""
        value = max(self._low + 1, min(value, self._maximum))
        if self._high != value:
            self._high = value
            self.rangeChanged.emit(self._low, self._high)
            self.update()
    
    def low(self):
        return self._low
    
    def high(self):
        return self._high
    
    def _value_to_pos(self, value):
        """将值转换为位置"""
        available_width = self.width() - 2 * self._margin
        ratio = (value - self._minimum) / max(1, self._maximum - self._minimum)
        return int(self._margin + ratio * available_width)
    
    def _pos_to_value(self, pos):
        """将位置转换为值"""
        available_width = self.width() - 2 * self._margin
        ratio = (pos - self._margin) / max(1, available_width)
        ratio = max(0, min(1, ratio))
        return int(self._minimum + ratio * (self._maximum - self._minimum))
    
    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        # 绘制轨道背景
        groove_rect = QtCore.QRectF(
            self._margin,
            (self.height() - self._groove_height) / 2,
            self.width() - 2 * self._margin,
            self._groove_height
        )
        groove_color = self.palette().color(QtGui.QPalette.Mid)  # Align groove with default QSlider track
        painter.setBrush(groove_color)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(groove_rect, 3, 3)
        
        # 绘制选中范围
        low_pos = self._value_to_pos(self._low)
        high_pos = self._value_to_pos(self._high)
        selected_rect = QtCore.QRectF(
            low_pos,
            (self.height() - self._groove_height) / 2,
            high_pos - low_pos,
            self._groove_height
        )
        painter.setBrush(QtGui.QColor("#007bff"))
        painter.drawRoundedRect(selected_rect, 3, 3)
        
        # 绘制低值滑块
        painter.setBrush(QtGui.QColor("#fff"))
        painter.setPen(QtGui.QPen(QtGui.QColor("#007bff"), 2))
        painter.drawEllipse(
            QtCore.QPointF(low_pos, self.height() / 2),
            self._handle_radius, self._handle_radius
        )
        
        # 绘制高值滑块
        painter.drawEllipse(
            QtCore.QPointF(high_pos, self.height() / 2),
            self._handle_radius, self._handle_radius
        )
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = event.pos().x()
            low_pos = self._value_to_pos(self._low)
            high_pos = self._value_to_pos(self._high)
            
            # 判断点击了哪个滑块（优先选择更近的）
            dist_to_low = abs(pos - low_pos)
            dist_to_high = abs(pos - high_pos)
            
            if dist_to_low <= self._handle_radius + 5 and dist_to_low <= dist_to_high:
                self._pressed_handle = 'low'
            elif dist_to_high <= self._handle_radius + 5:
                self._pressed_handle = 'high'
            else:
                # 点击轨道中间，移动更近的滑块
                if dist_to_low < dist_to_high:
                    self._pressed_handle = 'low'
                else:
                    self._pressed_handle = 'high'
                self._move_handle(pos)
    
    def mouseMoveEvent(self, event):
        if self._pressed_handle:
            self._move_handle(event.pos().x())
    
    def mouseReleaseEvent(self, event):
        self._pressed_handle = None
    
    def _move_handle(self, pos):
        value = self._pos_to_value(pos)
        if self._pressed_handle == 'low':
            self.setLow(value)
        elif self._pressed_handle == 'high':
            self.setHigh(value)


class ParameterConfigDialog(QtWidgets.QDialog):
    """参数配置对话框"""
    
    def __init__(self, sensors, parent=None):
        super().__init__(parent)
        # 支持传入单个sensor或sensor列表
        if not isinstance(sensors, list):
            sensors = [sensors]
        self.sensors = sensors
        self.sensor = self.sensors[0]  # 保持向后兼容，默认使用第一个传感器

        # 直接将 sensor 对象中存好的绝对路径传给管理器
        sensor_path = getattr(self.sensor, 'config_path', None)
        self.param_manager = ParameterManager(config_file=sensor_path)

        self.param_manager.load_config()
        self.preview_timer = QtCore.QTimer(self)
        self.preview_timer.setInterval(50)  # 与主界面保持一致频率
        self.preview_timer.timeout.connect(self.update_raw_preview)
        self.raw_preview_enabled = False
        self.preview_angle = 0
        
        # 设置对话框属性
        self.setWindowTitle("超参数配置")
        self.setModal(True)
        self.resize(700, 600)
        
        # 创建界面
        self.setup_ui()
        self.load_current_values()

        # 仅在对话框显示时启动预览
        self.raw_preview_enabled = True
    
    def setup_ui(self):
        """设置用户界面"""
        layout = QtWidgets.QVBoxLayout()
        
        # 创建选项卡控件
        self.tab_widget = QtWidgets.QTabWidget()
        
        # 创建各个参数选项卡
        self.optical_flow_tab = self.create_optical_flow_tab()
        self.grid_tab = self.create_grid_tab()
        self.camera_tab = self.create_camera_tab()
        
        # 添加选项卡到控件
        self.tab_widget.addTab(self.grid_tab, "基本布局参数")
        self.tab_widget.addTab(self.optical_flow_tab, "光流参数")
        self.tab_widget.addTab(self.camera_tab, "相机参数")
        
        layout.addWidget(self.tab_widget)
        
        # 创建按钮区域
        button_layout = QtWidgets.QHBoxLayout()

        # 按钮创建和连接
        self.reset_btn = QtWidgets.QPushButton("重置默认参数")
        self.reset_btn.clicked.connect(self.reset_to_default)
        self.reset_btn.setStyleSheet("QPushButton { background-color: #ffa500; color: white; font-weight: bold; }")
        
        self.cancel_btn = QtWidgets.QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        self.cancel_btn.setStyleSheet("QPushButton { background-color: #6c757d; color: white; font-weight: bold; }")

        self.choose_btn = QtWidgets.QPushButton("加载权重文件")
        self.choose_btn.clicked.connect(self.choose_File)
        self.choose_btn.setStyleSheet("QPushButton { background-color: #dc3545; color: white; font-weight: bold; }")

        self.apply_btn = QtWidgets.QPushButton("应用")
        self.apply_btn.clicked.connect(self.apply_params)
        self.apply_btn.setStyleSheet("QPushButton { background-color: #28a745; color: white; font-weight: bold; }")
        
        self.save_btn = QtWidgets.QPushButton("保存并应用")
        self.save_btn.clicked.connect(self.save_config)
        self.save_btn.setStyleSheet("QPushButton { background-color: #007bff; color: white; font-weight: bold; }")
        
        # 添加按钮到布局
        button_layout.addWidget(self.reset_btn)
        button_layout.addWidget(self.cancel_btn)
        button_layout.addWidget(self.choose_btn)
        button_layout.addWidget(self.apply_btn)
        button_layout.addWidget(self.save_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def create_optical_flow_tab(self):
        """创建光流参数选项卡"""
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout()
        
        # 金字塔缩放因子
        pyr_scale_layout = QtWidgets.QHBoxLayout()
        pyr_scale_layout.addWidget(QtWidgets.QLabel("金字塔缩放因子:"))
        
        self.pyr_scale_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.pyr_scale_slider.setRange(3, 8)  # 0.3-0.8 映射到 30-80
        self.pyr_scale_slider.setValue(5)  # 默认0.5
        self.pyr_scale_slider.setSingleStep(1)
        
        self.pyr_scale_label = QtWidgets.QLabel("0.5")
        self.pyr_scale_slider.valueChanged.connect(
            lambda v: self.pyr_scale_label.setText(f"{v/10:.1f}")
        )
        
        pyr_scale_layout.addWidget(self.pyr_scale_slider)
        pyr_scale_layout.addWidget(self.pyr_scale_label)
        layout.addLayout(pyr_scale_layout)
        
        # 金字塔层数
        levels_layout = QtWidgets.QHBoxLayout()
        levels_layout.addWidget(QtWidgets.QLabel("金字塔层数:"))
        
        self.levels_spin = QtWidgets.QSpinBox()
        self.levels_spin.setRange(1, 10)
        self.levels_spin.setValue(4)
        
        levels_layout.addWidget(self.levels_spin)
        layout.addLayout(levels_layout)
        
        # 窗口大小
        winsize_layout = QtWidgets.QHBoxLayout()
        winsize_layout.addWidget(QtWidgets.QLabel("窗口大小:"))
        
        self.winsize_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.winsize_slider.setRange(1, 150)
        self.winsize_slider.setValue(61)
        
        self.winsize_label = QtWidgets.QLabel("61")
        self.winsize_slider.valueChanged.connect(
            lambda v: self.winsize_label.setText(str(v))
        )
        
        winsize_layout.addWidget(self.winsize_slider)
        winsize_layout.addWidget(self.winsize_label)
        layout.addLayout(winsize_layout)
        
        # 迭代次数
        iterations_layout = QtWidgets.QHBoxLayout()
        iterations_layout.addWidget(QtWidgets.QLabel("迭代次数:"))
        
        self.iterations_spin = QtWidgets.QSpinBox()
        self.iterations_spin.setRange(1, 10)
        self.iterations_spin.setValue(7)
        
        iterations_layout.addWidget(self.iterations_spin)
        layout.addLayout(iterations_layout)
        
        # 多项式邻域
        poly_n_layout = QtWidgets.QHBoxLayout()
        poly_n_layout.addWidget(QtWidgets.QLabel("多项式邻域:"))
        
        self.poly_n_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.poly_n_slider.setRange(1, 10)
        self.poly_n_slider.setValue(7)
        
        self.poly_n_label = QtWidgets.QLabel("7")
        self.poly_n_slider.valueChanged.connect(
            lambda v: self.poly_n_label.setText(str(v))
        )
        
        poly_n_layout.addWidget(self.poly_n_slider)
        poly_n_layout.addWidget(self.poly_n_label)
        layout.addLayout(poly_n_layout)
        
        # 高斯标准差
        poly_sigma_layout = QtWidgets.QHBoxLayout()
        poly_sigma_layout.addWidget(QtWidgets.QLabel("高斯标准差:"))
        
        self.poly_sigma_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.poly_sigma_slider.setRange(10, 20)  # 0.5-2.0 映射到 50-200
        self.poly_sigma_slider.setValue(11)  # 默认1.1
        
        self.poly_sigma_label = QtWidgets.QLabel("1.1")
        self.poly_sigma_slider.valueChanged.connect(
            lambda v: self.poly_sigma_label.setText(f"{v/10:.1f}")
        )
        
        poly_sigma_layout.addWidget(self.poly_sigma_slider)
        poly_sigma_layout.addWidget(self.poly_sigma_label)
        layout.addLayout(poly_sigma_layout)
        
        # 显示缩放因子
        scale_factor_layout = QtWidgets.QHBoxLayout()
        scale_factor_layout.addWidget(QtWidgets.QLabel("显示缩放因子:"))
        
        self.scale_factor_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.scale_factor_slider.setRange(0, 10)  # 0.0-1.0 映射到 0-10
        self.scale_factor_slider.setValue(5)  # 默认0.5
        
        self.scale_factor_label = QtWidgets.QLabel("0.5")
        self.scale_factor_slider.valueChanged.connect(
            lambda v: self.scale_factor_label.setText(f"{v/10:.1f}")
        )
        
        scale_factor_layout.addWidget(self.scale_factor_slider)
        scale_factor_layout.addWidget(self.scale_factor_label)
        layout.addLayout(scale_factor_layout)
        
        # 添加参数说明
        info_label = QtWidgets.QLabel("""
        参数说明：
        • 金字塔缩放因子：影响光流计算的精度，值越小精度越高但速度越慢
        • 金字塔层数：多尺度分析的层数，层数越多越精确但计算量越大
        • 窗口大小：光流计算的窗口大小，影响局部特征检测
        • 迭代次数：光流算法的迭代次数，影响收敛性
        • 多项式邻域：多项式展开的邻域大小
        • 高斯标准差：高斯滤波的标准差，影响平滑程度
        • 显示缩放因子：影响显示图像的缩放比例，值越小显示越精细但计算量越大
        """)
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: gray; font-size: 10px; background-color: #f8f9fa; padding: 10px; border-radius: 5px;")
        layout.addWidget(info_label)
        
        tab.setLayout(layout)
        return tab
    
    def create_grid_tab(self):
        """创建网格参数选项卡"""
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout()
        
        # 网格单元大小
        cell_size_layout = QtWidgets.QHBoxLayout()
        cell_size_layout.addWidget(QtWidgets.QLabel("网格单元大小:"))
        
        self.cell_size_spin = QtWidgets.QSpinBox()
        self.cell_size_spin.setRange(1, 50)
        self.cell_size_spin.setValue(1)
        
        cell_size_layout.addWidget(self.cell_size_spin)
        layout.addLayout(cell_size_layout)
        
        # 光流采样步长
        step_layout = QtWidgets.QHBoxLayout()
        step_layout.addWidget(QtWidgets.QLabel("光流采样步长:"))
        
        self.step_spin = QtWidgets.QSpinBox()
        self.step_spin.setRange(1, 100)
        self.step_spin.setValue(35)
        
        step_layout.addWidget(self.step_spin)
        layout.addLayout(step_layout)

        # 压力缩放系数
        pressure_scale_layout = QtWidgets.QHBoxLayout()
        pressure_scale_layout.addWidget(QtWidgets.QLabel("压力缩放系数:"))

        self.pressure_scale_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.pressure_scale_slider.setRange(1, 10)  # 1-10 映射到 1-10
        self.pressure_scale_slider.setValue(4)

        self.pressure_scale_label = QtWidgets.QLabel("4")
        self.pressure_scale_slider.valueChanged.connect(
            lambda v: self.pressure_scale_label.setText(str(v))
        )

        pressure_scale_layout.addWidget(self.pressure_scale_slider)
        pressure_scale_layout.addWidget(self.pressure_scale_label)
        layout.addLayout(pressure_scale_layout)

        # 压力图显示模式切换（灰度/彩色）
        pressure_form_switch_layout = QtWidgets.QHBoxLayout()
        pressure_form_switch_layout.addWidget(QtWidgets.QLabel("压力图显示模式:"))
        self.pressure_form_switch = QtWidgets.QComboBox()
        self.pressure_form_switch.addItem("灰度图")
        self.pressure_form_switch.addItem("热力图")
        self.pressure_form_switch.addItem("RGB图像")
        self.pressure_form_switch.setCurrentIndex(0)  # 默认灰度模式
        pressure_form_switch_layout.addWidget(self.pressure_form_switch)
        layout.addLayout(pressure_form_switch_layout)
        
        # === ROI区域设置组 ===
        roi_title = QtWidgets.QLabel("ROI区域设置 (感兴趣区域)")
        roi_title.setStyleSheet("font-weight: bold;")
        roi_section = QtWidgets.QVBoxLayout()
        roi_section.setContentsMargins(0, 0, 0, 0)
        roi_section.setSpacing(1)  # tighten spacing between title and sliders
        roi_section.addWidget(roi_title)
        roi_layout = QtWidgets.QVBoxLayout()
        
        # --- X方向范围滑动条 ---
        x_range_layout = QtWidgets.QHBoxLayout()
        x_range_layout.addWidget(QtWidgets.QLabel("X 范围:"))
        
        self.roi_x_slider = RangeSlider(0, 640)
        self.roi_x_slider.setLow(160)
        self.roi_x_slider.setHigh(540)
        x_range_layout.addWidget(self.roi_x_slider, stretch=1)
        
        # X1 SpinBox
        self.roi_x1_spin = QtWidgets.QSpinBox()
        self.roi_x1_spin.setRange(0, 640)
        self.roi_x1_spin.setValue(160)
        self.roi_x1_spin.setPrefix("X1: ")
        self.roi_x1_spin.setMinimumWidth(80)
        x_range_layout.addWidget(self.roi_x1_spin)
        
        # X2 SpinBox
        self.roi_x2_spin = QtWidgets.QSpinBox()
        self.roi_x2_spin.setRange(0, 640)
        self.roi_x2_spin.setValue(540)
        self.roi_x2_spin.setPrefix("X2: ")
        self.roi_x2_spin.setMinimumWidth(80)
        x_range_layout.addWidget(self.roi_x2_spin)
        
        roi_layout.addLayout(x_range_layout)
        
        # --- Y方向范围滑动条 ---
        y_range_layout = QtWidgets.QHBoxLayout()
        y_range_layout.addWidget(QtWidgets.QLabel("Y 范围:"))
        
        self.roi_y_slider = RangeSlider(0, 480)
        self.roi_y_slider.setLow(0)
        self.roi_y_slider.setHigh(430)
        y_range_layout.addWidget(self.roi_y_slider, stretch=1)
        
        # Y1 SpinBox
        self.roi_y1_spin = QtWidgets.QSpinBox()
        self.roi_y1_spin.setRange(0, 480)
        self.roi_y1_spin.setValue(0)
        self.roi_y1_spin.setPrefix("Y1: ")
        self.roi_y1_spin.setMinimumWidth(80)
        y_range_layout.addWidget(self.roi_y1_spin)
        
        # Y2 SpinBox
        self.roi_y2_spin = QtWidgets.QSpinBox()
        self.roi_y2_spin.setRange(0, 480)
        self.roi_y2_spin.setValue(430)
        self.roi_y2_spin.setPrefix("Y2: ")
        self.roi_y2_spin.setMinimumWidth(80)
        y_range_layout.addWidget(self.roi_y2_spin)
        
        roi_layout.addLayout(y_range_layout)
        
        # 连接滑动条和SpinBox的双向联动
        # X方向
        self.roi_x_slider.rangeChanged.connect(self._on_x_slider_changed)
        self.roi_x1_spin.valueChanged.connect(self._on_x1_spin_changed)
        self.roi_x2_spin.valueChanged.connect(self._on_x2_spin_changed)
        
        # Y方向
        self.roi_y_slider.rangeChanged.connect(self._on_y_slider_changed)
        self.roi_y1_spin.valueChanged.connect(self._on_y1_spin_changed)
        self.roi_y2_spin.valueChanged.connect(self._on_y2_spin_changed)
        
        # ROI尺寸显示标签
        self.roi_size_label = QtWidgets.QLabel("当前ROI尺寸: 381 x 431")
        self.roi_size_label.setStyleSheet("color: #007bff; font-weight: bold;")
        roi_layout.addWidget(self.roi_size_label)
        
        # 连接信号更新ROI尺寸显示
        self.roi_x1_spin.valueChanged.connect(self.update_roi_size_label)
        self.roi_x2_spin.valueChanged.connect(self.update_roi_size_label)
        self.roi_y1_spin.valueChanged.connect(self.update_roi_size_label)
        self.roi_y2_spin.valueChanged.connect(self.update_roi_size_label)
        
        roi_section.addLayout(roi_layout)
        layout.addLayout(roi_section)
        
        # === 3D压力图缩放系数 ===
        force_scale_title = QtWidgets.QLabel("3D压力图缩放系数")
        force_scale_title.setStyleSheet("font-weight: bold;")
        force_scale_section = QtWidgets.QVBoxLayout()
        force_scale_section.setContentsMargins(0, 0, 0, 0)
        force_scale_section.setSpacing(1)  # tighten spacing between title and sliders
        force_scale_section.addWidget(force_scale_title)
        force_scale_layout = QtWidgets.QVBoxLayout()
        
        # Fx缩放系数
        fx_scale_layout = QtWidgets.QHBoxLayout()
        fx_scale_layout.addWidget(QtWidgets.QLabel("Fx 缩放系数:"))
        
        self.fx_scale_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.fx_scale_slider.setRange(1, 100)  # 0.01-1.0 映射到 1-100
        self.fx_scale_slider.setValue(10)  # 默认0.1
        
        self.fx_scale_label = QtWidgets.QLabel("0.1")
        self.fx_scale_slider.valueChanged.connect(
            lambda v: self.fx_scale_label.setText(f"{v/100:.2f}")
        )
        
        fx_scale_layout.addWidget(self.fx_scale_slider)
        fx_scale_layout.addWidget(self.fx_scale_label)
        force_scale_layout.addLayout(fx_scale_layout)
        
        # Fy缩放系数
        fy_scale_layout = QtWidgets.QHBoxLayout()
        fy_scale_layout.addWidget(QtWidgets.QLabel("Fy 缩放系数:"))
        
        self.fy_scale_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.fy_scale_slider.setRange(1, 100)  # 0.01-1.0 映射到 1-100
        self.fy_scale_slider.setValue(10)  # 默认0.1
        
        self.fy_scale_label = QtWidgets.QLabel("0.1")
        self.fy_scale_slider.valueChanged.connect(
            lambda v: self.fy_scale_label.setText(f"{v/100:.2f}")
        )
        
        fy_scale_layout.addWidget(self.fy_scale_slider)
        fy_scale_layout.addWidget(self.fy_scale_label)
        force_scale_layout.addLayout(fy_scale_layout)
        
        # Fz缩放系数
        fz_scale_layout = QtWidgets.QHBoxLayout()
        fz_scale_layout.addWidget(QtWidgets.QLabel("Fz 缩放系数:"))
        
        self.fz_scale_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.fz_scale_slider.setRange(1, 100)  # 0.01-1.0 映射到 1-100
        self.fz_scale_slider.setValue(5)  # 默认0.05
        
        self.fz_scale_label = QtWidgets.QLabel("0.05")
        self.fz_scale_slider.valueChanged.connect(
            lambda v: self.fz_scale_label.setText(f"{v/100:.2f}")
        )
        
        fz_scale_layout.addWidget(self.fz_scale_slider)
        fz_scale_layout.addWidget(self.fz_scale_label)
        force_scale_layout.addLayout(fz_scale_layout)
        
        force_scale_section.addLayout(force_scale_layout)
        layout.addLayout(force_scale_section)
        
        # 原始画面预览（仅水平翻转）
        preview_group = QtWidgets.QGroupBox("摄像头原始画面预览")
        preview_layout = QtWidgets.QVBoxLayout()
        
        # 根据传感器数量创建预览窗口
        if len(self.sensors) == 1:
            # 单传感器模式
            self.raw_preview_label = QtWidgets.QLabel("预览初始化中...")
            self.raw_preview_label.setAlignment(Qt.AlignCenter)
            self.raw_preview_label.setStyleSheet("background-color: black; color: white;")
            self.raw_preview_label.setMinimumHeight(200)
            preview_layout.addWidget(self.raw_preview_label)
        else:
            # 双传感器模式 - 左右并排
            dual_preview_layout = QtWidgets.QHBoxLayout()
            
            # 传感器1预览
            sensor1_layout = QtWidgets.QVBoxLayout()
            sensor1_title = QtWidgets.QLabel("传感器1")
            sensor1_title.setAlignment(Qt.AlignCenter)
            sensor1_title.setStyleSheet("color: white; font-weight: bold;")
            sensor1_layout.addWidget(sensor1_title)
            self.raw_preview_label_1 = QtWidgets.QLabel("预览初始化中...")
            self.raw_preview_label_1.setAlignment(Qt.AlignCenter)
            self.raw_preview_label_1.setStyleSheet("background-color: black; color: white;")
            self.raw_preview_label_1.setMinimumHeight(200)
            sensor1_layout.addWidget(self.raw_preview_label_1)
            dual_preview_layout.addLayout(sensor1_layout)
            
            # 传感器2预览
            sensor2_layout = QtWidgets.QVBoxLayout()
            sensor2_title = QtWidgets.QLabel("传感器2")
            sensor2_title.setAlignment(Qt.AlignCenter)
            sensor2_title.setStyleSheet("color: white; font-weight: bold;")
            sensor2_layout.addWidget(sensor2_title)
            self.raw_preview_label_2 = QtWidgets.QLabel("预览初始化中...")
            self.raw_preview_label_2.setAlignment(Qt.AlignCenter)
            self.raw_preview_label_2.setStyleSheet("background-color: black; color: white;")
            self.raw_preview_label_2.setMinimumHeight(200)
            sensor2_layout.addWidget(self.raw_preview_label_2)
            dual_preview_layout.addLayout(sensor2_layout)
            
            preview_layout.addLayout(dual_preview_layout)

        # ... existing code ...

        angle_layout = QtWidgets.QVBoxLayout()
        angle_title_layout = QtWidgets.QHBoxLayout()
        angle_title_layout.addWidget(QtWidgets.QLabel("预览旋转角度:"))
        angle_layout.addLayout(angle_title_layout)

        self.preview_angle_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.preview_angle_slider.setRange(-180, 180)
        self.preview_angle_slider.setValue(0)
        self.preview_angle_slider.setSingleStep(1)
        self.preview_angle_slider.setMinimumWidth(180)
        self.preview_angle_spin = QtWidgets.QSpinBox()
        self.preview_angle_spin.setRange(-180, 180)
        self.preview_angle_spin.setValue(0)
        self.preview_angle_spin.setSuffix(" °")
        self.preview_angle_spin.setMinimumWidth(70)

        self.preview_angle_slider.valueChanged.connect(self.preview_angle_spin.setValue)
        self.preview_angle_spin.valueChanged.connect(self.preview_angle_slider.setValue)
        self.preview_angle_spin.valueChanged.connect(self.set_preview_angle)

        slider_layout = QtWidgets.QHBoxLayout()
        slider_layout.addWidget(self.preview_angle_slider)
        slider_layout.addWidget(self.preview_angle_spin)
        angle_layout.addLayout(slider_layout)

        auto_exposure_check = QtWidgets.QCheckBox("旋转 180°") #旋转选择
        auto_exposure_check.setChecked(False)
        self.original_preview_angle = 0
        # 保存 checkbox 引用以便后续访问
        self.rotation_180_checkbox = auto_exposure_check
        # 连接信号到槽函数
        auto_exposure_check.stateChanged.connect(self.on_rotation_180_changed)

        angle_layout.addWidget(auto_exposure_check)  # 将选择框添加到布局中

        preview_layout.addLayout(angle_layout)
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)
        
        tab.setLayout(layout)
        return tab

    def on_rotation_180_changed(self, state):
        """旋转 180° checkbox 状态变化处理"""
        if state == Qt.Checked:
            # 勾选时：在原有角度基础上 +180
            current_angle = self.preview_angle_slider.value()
            new_angle = current_angle + 180
            if new_angle > 180:
                new_angle -= 360
            self.preview_angle_slider.setValue(new_angle)
        else:
            # 取消勾选时：在原有角度基础上 -180
            current_angle = self.preview_angle_slider.value()
            new_angle = current_angle - 180
            if new_angle < -180:
                new_angle += 360
            self.preview_angle_slider.setValue(new_angle)

    def _on_x_slider_changed(self, low, high):
        """X滑动条变化时更新SpinBox"""
        self.roi_x1_spin.blockSignals(True)
        self.roi_x2_spin.blockSignals(True)
        self.roi_x1_spin.setValue(low)
        self.roi_x2_spin.setValue(high)
        self.roi_x1_spin.blockSignals(False)
        self.roi_x2_spin.blockSignals(False)
        self.update_roi_size_label()
    
    def _on_x1_spin_changed(self, value):
        """X1 SpinBox变化时更新滑动条"""
        self.roi_x_slider.blockSignals(True)
        self.roi_x_slider.setLow(value)
        self.roi_x_slider.blockSignals(False)
    
    def _on_x2_spin_changed(self, value):
        """X2 SpinBox变化时更新滑动条"""
        self.roi_x_slider.blockSignals(True)
        self.roi_x_slider.setHigh(value)
        self.roi_x_slider.blockSignals(False)
    
    def _on_y_slider_changed(self, low, high):
        """Y滑动条变化时更新SpinBox"""
        self.roi_y1_spin.blockSignals(True)
        self.roi_y2_spin.blockSignals(True)
        self.roi_y1_spin.setValue(low)
        self.roi_y2_spin.setValue(high)
        self.roi_y1_spin.blockSignals(False)
        self.roi_y2_spin.blockSignals(False)
        self.update_roi_size_label()
    
    def _on_y1_spin_changed(self, value):
        """Y1 SpinBox变化时更新滑动条"""
        self.roi_y_slider.blockSignals(True)
        self.roi_y_slider.setLow(value)
        self.roi_y_slider.blockSignals(False)
    
    def _on_y2_spin_changed(self, value):
        """Y2 SpinBox变化时更新滑动条"""
        self.roi_y_slider.blockSignals(True)
        self.roi_y_slider.setHigh(value)
        self.roi_y_slider.blockSignals(False)
    
    def update_roi_size_label(self):
        """更新ROI尺寸显示"""
        x1 = self.roi_x1_spin.value()
        x2 = self.roi_x2_spin.value()
        y1 = self.roi_y1_spin.value()
        y2 = self.roi_y2_spin.value()
        width = x2 - x1 + 1 if x2 > x1 else 0
        height = y2 - y1 + 1 if y2 > y1 else 0
        self.roi_size_label.setText(f"当前ROI尺寸: {width} x {height}")
        # 如果边界无效，显示警告颜色
        if x2 <= x1 or y2 <= y1:
            self.roi_size_label.setStyleSheet("color: red; font-weight: bold;")
        else:
            self.roi_size_label.setStyleSheet("color: #007bff; font-weight: bold;")

    def start_raw_preview(self):
        if not self.raw_preview_enabled:
            return
        if not hasattr(self.sensor, "cap") or self.sensor.cap is None:
            self.raw_preview_label.setText("摄像头不可用")
            return
        if not self.sensor.cap.isOpened():
            self.raw_preview_label.setText("摄像头未打开")
            return
        if not self.preview_timer.isActive():
            self.preview_timer.start()

    def stop_raw_preview(self):
        if self.preview_timer.isActive():
            self.preview_timer.stop()

    def showEvent(self, event):
        super().showEvent(event)
        self.start_raw_preview()

    def hideEvent(self, event):
        self.stop_raw_preview()
        super().hideEvent(event)

    def closeEvent(self, event):
        self.stop_raw_preview()
        super().closeEvent(event)

    def set_preview_angle(self, value):
        self.preview_angle = int(value)

    def update_raw_preview(self):
        if not self.raw_preview_enabled:
            return

        # 居中裁剪 + 缩放辅助函数（将任意分辨率图像居中裁剪到 4:3 比例，再缩放到 640x480）
        def center_crop_and_resize(img, target_size=(640, 480)):
            h, w = img.shape[:2]
            tw, th = target_size
            target_ratio = tw / th  # 4/3 ≈ 1.3333
            src_ratio = w / h
            if src_ratio > target_ratio:
                # 图像过宽，裁剪左右
                crop_w = int(h * target_ratio)
                crop_h = h
                start_x = (w - crop_w) // 2
                start_y = 0
            else:
                # 图像过高，裁剪上下
                crop_w = w
                crop_h = int(w / target_ratio)
                start_x = 0
                start_y = (h - crop_h) // 2
            cropped = img[start_y:start_y + crop_h, start_x:start_x + crop_w]
            resized = cv2.resize(cropped, target_size, interpolation=cv2.INTER_LINEAR)
            return resized

        # 循环更新所有传感器的预览
        for sensor_idx, sensor in enumerate(self.sensors):
            # 选择对应的预览label
            if len(self.sensors) == 1:
                preview_label = self.raw_preview_label
            else:
                preview_label = self.raw_preview_label_1 if sensor_idx == 0 else self.raw_preview_label_2

            try:
                if not hasattr(sensor, "cap") or sensor.cap is None:
                    preview_label.setText(f"传感器{sensor_idx + 1}摄像头不可用")
                    continue
                cap = sensor.cap
                if not cap.isOpened():
                    preview_label.setText(f"传感器{sensor_idx + 1}摄像头未打开")
                    continue

                ret, frame = cap.read()
                if not ret or frame is None:
                    preview_label.setText(f"传感器{sensor_idx + 1}读取画面失败")
                    continue

                # 1. 水平镜像（与主程序一致）
                frame = cv2.flip(frame, 1)
                # 2. 旋转180°（与主程序一致）
                frame = cv2.rotate(frame, cv2.ROTATE_180)

                # 3. 应用用户预览旋转角度（preview_angle）
                angle = -getattr(self, "preview_angle", 0)
                if angle != 0:
                    h, w = frame.shape[:2]
                    center = (w / 2.0, h / 2.0)
                    rot_mat = cv2.getRotationMatrix2D(center, angle, 1.0)
                    frame = cv2.warpAffine(
                        frame,
                        rot_mat,
                        (w, h),
                        flags=cv2.INTER_LINEAR,
                        borderMode=cv2.BORDER_CONSTANT,
                        borderValue=(0, 0, 0)
                    )

                # 4. 居中裁剪并缩放到 640x480（保持 4:3 比例，无拉伸）
                frame = center_crop_and_resize(frame, (640, 480))

                # 5. 转换为 RGB 用于 Qt 显示
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # 6. 叠加 ROI 矩形（坐标基于 640x480 图像）
                x1 = self.roi_x1_spin.value() if hasattr(self, "roi_x1_spin") else None
                x2 = self.roi_x2_spin.value() if hasattr(self, "roi_x2_spin") else None
                y1 = self.roi_y1_spin.value() if hasattr(self, "roi_y1_spin") else None
                y2 = self.roi_y2_spin.value() if hasattr(self, "roi_y2_spin") else None
                if None not in (x1, x2, y1, y2):
                    h, w, _ = frame_rgb.shape
                    x1 = max(0, min(int(x1), w - 1))
                    x2 = max(0, min(int(x2), w - 1))
                    y1 = max(0, min(int(y1), h - 1))
                    y2 = max(0, min(int(y2), h - 1))
                    if x2 > x1 and y2 > y1:
                        cv2.rectangle(frame_rgb, (x1, y1), (x2, y2), (0, 255, 0), 6)

                # 7. 转换为 QImage 并显示
                h, w, ch = frame_rgb.shape
                bytes_per_line = ch * w
                q_img = QtGui.QImage(frame_rgb.data, w, h, bytes_per_line, QtGui.QImage.Format_RGB888)
                pixmap = QtGui.QPixmap.fromImage(q_img)
                scaled = pixmap.scaled(
                    preview_label.width() if preview_label.width() > 0 else w,
                    preview_label.height() if preview_label.height() > 0 else h,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                preview_label.setPixmap(scaled)

            except Exception as e:
                preview_label.setText(f"传感器{sensor_idx + 1}预览出错: {e}")
    
    def create_camera_tab(self):
        """创建相机参数选项卡"""
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout()
        
        # === 色彩调整组 ===
        color_group = QtWidgets.QGroupBox("色彩调整")
        color_layout = QtWidgets.QVBoxLayout()
        
        # 色相
        hue_layout = QtWidgets.QHBoxLayout()
        hue_layout.addWidget(QtWidgets.QLabel("色相:"))
        hue_min_label = QtWidgets.QLabel("-180")
        hue_min_label.setMinimumWidth(40)
        hue_layout.addWidget(hue_min_label)
        
        self.hue_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.hue_slider.setRange(-180, 180)
        self.hue_slider.setValue(0)
        self.hue_slider.setMinimumWidth(200)
        
        hue_max_label = QtWidgets.QLabel("180")
        hue_max_label.setMinimumWidth(40)
        hue_layout.addWidget(hue_max_label)
        
        self.hue_spin = QtWidgets.QDoubleSpinBox()
        self.hue_spin.setRange(-180.0, 180.0)
        self.hue_spin.setValue(0.0)
        self.hue_spin.setSingleStep(1.0)
        self.hue_spin.setDecimals(1)
        self.hue_spin.setMinimumWidth(80)
        
        self.hue_slider.valueChanged.connect(
            lambda v: self.hue_spin.setValue(float(v))
        )
        self.hue_spin.valueChanged.connect(
            lambda v: self.hue_slider.setValue(int(v))
        )
        
        hue_layout.addWidget(self.hue_slider)
        hue_layout.addWidget(self.hue_spin)
        color_layout.addLayout(hue_layout)
        
        # 饱和度
        saturation_layout = QtWidgets.QHBoxLayout()
        saturation_layout.addWidget(QtWidgets.QLabel("饱和度:"))
        sat_min_label = QtWidgets.QLabel("0")
        sat_min_label.setMinimumWidth(40)
        saturation_layout.addWidget(sat_min_label)
        
        self.saturation_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.saturation_slider.setRange(0, 100)
        self.saturation_slider.setValue(64)
        self.saturation_slider.setMinimumWidth(200)
        
        sat_max_label = QtWidgets.QLabel("100")
        sat_max_label.setMinimumWidth(40)
        saturation_layout.addWidget(sat_max_label)
        
        self.saturation_spin = QtWidgets.QSpinBox()
        self.saturation_spin.setRange(0, 100)
        self.saturation_spin.setValue(64)
        self.saturation_spin.setMinimumWidth(80)
        
        self.saturation_slider.valueChanged.connect(self.saturation_spin.setValue)
        self.saturation_spin.valueChanged.connect(self.saturation_slider.setValue)
        
        saturation_layout.addWidget(self.saturation_slider)
        saturation_layout.addWidget(self.saturation_spin)
        color_layout.addLayout(saturation_layout)
        
        # 伽马值
        gamma_layout = QtWidgets.QHBoxLayout()
        gamma_layout.addWidget(QtWidgets.QLabel("伽马值:"))
        gamma_min_label = QtWidgets.QLabel("100")
        gamma_min_label.setMinimumWidth(40)
        gamma_layout.addWidget(gamma_min_label)
        
        self.gamma_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.gamma_slider.setRange(100, 500)
        self.gamma_slider.setValue(500)
        self.gamma_slider.setMinimumWidth(200)
        
        gamma_max_label = QtWidgets.QLabel("500")
        gamma_max_label.setMinimumWidth(40)
        gamma_layout.addWidget(gamma_max_label)
        
        self.gamma_spin = QtWidgets.QSpinBox()
        self.gamma_spin.setRange(100, 500)
        self.gamma_spin.setValue(500)
        self.gamma_spin.setSingleStep(10)
        self.gamma_spin.setMinimumWidth(80)
        
        self.gamma_slider.valueChanged.connect(self.gamma_spin.setValue)
        self.gamma_spin.valueChanged.connect(self.gamma_slider.setValue)
        
        gamma_layout.addWidget(self.gamma_slider)
        gamma_layout.addWidget(self.gamma_spin)
        color_layout.addLayout(gamma_layout)
        
        color_group.setLayout(color_layout)
        layout.addWidget(color_group)
        
        # === 曝光控制组 ===
        exposure_group = QtWidgets.QGroupBox("曝光控制")
        exposure_layout = QtWidgets.QVBoxLayout()
        
        # 自动曝光
        auto_exp_layout = QtWidgets.QHBoxLayout()
        self.auto_exposure_check = QtWidgets.QCheckBox("自动曝光")
        self.auto_exposure_check.setChecked(False)
        auto_exp_layout.addWidget(self.auto_exposure_check)
        exposure_layout.addLayout(auto_exp_layout)
        
        # 曝光值
        exposure_val_layout = QtWidgets.QHBoxLayout()
        exposure_val_layout.addWidget(QtWidgets.QLabel("曝光值:"))
        exp_min_label = QtWidgets.QLabel("-8")
        exp_min_label.setMinimumWidth(40)
        exposure_val_layout.addWidget(exp_min_label)
        
        self.exposure_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.exposure_slider.setRange(-8, 0)
        self.exposure_slider.setValue(-5)
        self.exposure_slider.setMinimumWidth(200)
        
        exp_max_label = QtWidgets.QLabel("0")
        exp_max_label.setMinimumWidth(40)
        exposure_val_layout.addWidget(exp_max_label)
        
        self.exposure_spin = QtWidgets.QDoubleSpinBox()
        self.exposure_spin.setRange(-8.0, 0.0)
        self.exposure_spin.setValue(-5.0)
        self.exposure_spin.setSingleStep(1)
        self.exposure_spin.setDecimals(1)
        self.exposure_spin.setMinimumWidth(80)
        
        self.exposure_slider.valueChanged.connect(
            lambda v: self.exposure_spin.setValue(float(v))
        )
        self.exposure_spin.valueChanged.connect(
            lambda v: self.exposure_slider.setValue(int(v))
        )
        
        exposure_val_layout.addWidget(self.exposure_slider)
        exposure_val_layout.addWidget(self.exposure_spin)
        exposure_layout.addLayout(exposure_val_layout)
        
        exposure_group.setLayout(exposure_layout)
        layout.addWidget(exposure_group)
        
        # === 图像质量组 ===
        quality_group = QtWidgets.QGroupBox("图像质量")
        quality_layout = QtWidgets.QVBoxLayout()
        
        # 对比度
        contrast_layout = QtWidgets.QHBoxLayout()
        contrast_layout.addWidget(QtWidgets.QLabel("对比度:"))
        contrast_min_label = QtWidgets.QLabel("0")
        contrast_min_label.setMinimumWidth(40)
        contrast_layout.addWidget(contrast_min_label)
        
        self.contrast_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.contrast_slider.setRange(0, 100)
        self.contrast_slider.setValue(50)
        self.contrast_slider.setMinimumWidth(200)
        
        contrast_max_label = QtWidgets.QLabel("100")
        contrast_max_label.setMinimumWidth(40)
        contrast_layout.addWidget(contrast_max_label)
        
        self.contrast_spin = QtWidgets.QSpinBox()
        self.contrast_spin.setRange(0, 100)
        self.contrast_spin.setValue(50)
        self.contrast_spin.setMinimumWidth(80)
        
        self.contrast_slider.valueChanged.connect(self.contrast_spin.setValue)
        self.contrast_spin.valueChanged.connect(self.contrast_slider.setValue)
        
        contrast_layout.addWidget(self.contrast_slider)
        contrast_layout.addWidget(self.contrast_spin)
        quality_layout.addLayout(contrast_layout)
        
        # 亮度
        brightness_layout = QtWidgets.QHBoxLayout()
        brightness_layout.addWidget(QtWidgets.QLabel("亮度:"))
        bright_min_label = QtWidgets.QLabel("-64")
        bright_min_label.setMinimumWidth(40)
        brightness_layout.addWidget(bright_min_label)
        
        self.brightness_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.brightness_slider.setRange(-64, 64)
        self.brightness_slider.setValue(5)
        self.brightness_slider.setMinimumWidth(200)
        
        bright_max_label = QtWidgets.QLabel("64")
        bright_max_label.setMinimumWidth(40)
        brightness_layout.addWidget(bright_max_label)
        
        self.brightness_spin = QtWidgets.QSpinBox()
        self.brightness_spin.setRange(-64, 64)
        self.brightness_spin.setValue(5)
        self.brightness_spin.setMinimumWidth(80)
        
        self.brightness_slider.valueChanged.connect(self.brightness_spin.setValue)
        self.brightness_spin.valueChanged.connect(self.brightness_slider.setValue)
        
        brightness_layout.addWidget(self.brightness_slider)
        brightness_layout.addWidget(self.brightness_spin)
        quality_layout.addLayout(brightness_layout)
        
        # 锐度
        sharpness_layout = QtWidgets.QHBoxLayout()
        sharpness_layout.addWidget(QtWidgets.QLabel("锐度:"))
        sharp_min_label = QtWidgets.QLabel("0")
        sharp_min_label.setMinimumWidth(40)
        sharpness_layout.addWidget(sharp_min_label)
        
        self.sharpness_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.sharpness_slider.setRange(0, 100)
        self.sharpness_slider.setValue(100)
        self.sharpness_slider.setMinimumWidth(200)
        
        sharp_max_label = QtWidgets.QLabel("100")
        sharp_max_label.setMinimumWidth(40)
        sharpness_layout.addWidget(sharp_max_label)
        
        self.sharpness_spin = QtWidgets.QSpinBox()
        self.sharpness_spin.setRange(0, 100)
        self.sharpness_spin.setValue(100)
        self.sharpness_spin.setMinimumWidth(80)
        
        self.sharpness_slider.valueChanged.connect(self.sharpness_spin.setValue)
        self.sharpness_spin.valueChanged.connect(self.sharpness_slider.setValue)
        
        sharpness_layout.addWidget(self.sharpness_slider)
        sharpness_layout.addWidget(self.sharpness_spin)
        quality_layout.addLayout(sharpness_layout)
        
        quality_group.setLayout(quality_layout)
        layout.addWidget(quality_group)
        
        # === 白平衡组 ===
        wb_group = QtWidgets.QGroupBox("白平衡")
        wb_layout = QtWidgets.QVBoxLayout()
        
        # 自动白平衡
        auto_wb_layout = QtWidgets.QHBoxLayout()
        self.auto_wb_check = QtWidgets.QCheckBox("自动白平衡")
        self.auto_wb_check.setChecked(False)
        auto_wb_layout.addWidget(self.auto_wb_check)
        wb_layout.addLayout(auto_wb_layout)
        
        # 白平衡色温
        wb_temp_layout = QtWidgets.QHBoxLayout()
        wb_temp_layout.addWidget(QtWidgets.QLabel("白平衡色温:"))
        wb_min_label = QtWidgets.QLabel("2000")
        wb_min_label.setMinimumWidth(40)
        wb_temp_layout.addWidget(wb_min_label)
        
        self.white_balance_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.white_balance_slider.setRange(2800, 6500)
        self.white_balance_slider.setValue(4600)
        self.white_balance_slider.setMinimumWidth(200)
        
        wb_max_label = QtWidgets.QLabel("6500")
        wb_max_label.setMinimumWidth(40)
        wb_temp_layout.addWidget(wb_max_label)
        
        self.white_balance_spin = QtWidgets.QSpinBox()
        self.white_balance_spin.setRange(2800, 6500)
        self.white_balance_spin.setValue(4600)
        self.white_balance_spin.setSingleStep(100)
        self.white_balance_spin.setMinimumWidth(80)
        
        self.white_balance_slider.valueChanged.connect(self.white_balance_spin.setValue)
        self.white_balance_spin.valueChanged.connect(self.white_balance_slider.setValue)
        
        wb_temp_layout.addWidget(self.white_balance_slider)
        wb_temp_layout.addWidget(self.white_balance_spin)
        wb_layout.addLayout(wb_temp_layout)
        
        wb_group.setLayout(wb_layout)
        layout.addWidget(wb_group)
        
        # === 参数说明 ===
        info_label = QtWidgets.QLabel("""
        参数说明：
        • 色相：调整图像的色相（色调），范围-180到180
        • 饱和度：颜色鲜艳程度，值越大颜色越鲜艳（0-100）
        • 伽马值：影响图像明暗曲线，调整图像整体明暗对比（100-1000）
        • 曝光值：控制图像亮度，值越小图像越暗（-20到20）
        • 对比度：影响图像对比度，值越大对比越强（0-100）
        • 亮度：整体图像亮度调整（-64到64）
        • 锐度：图像清晰度，值越大越清晰（0-100）
        • 白平衡色温：调整色温，适应不同光源环境（2800-6500K）
        """)
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: gray; font-size: 10px; background-color: #f8f9fa; padding: 10px; border-radius: 5px;")
        layout.addWidget(info_label)
        
        tab.setLayout(layout)
        return tab
    
    def load_current_values(self):
        """加载当前参数值到界面控件 - 从sensor对象读取实际运行参数"""
        # 从第一个sensor对象读取当前实际参数（双传感器共用配置）
        sensor = self.sensor
        optical_flow_params = getattr(sensor, 'params', {}) or {}
        camera_params = getattr(sensor, 'camera_params', {}) or {}
        
        # 光流参数 - 从sensor对象读取
        self.pyr_scale_slider.setValue(int(optical_flow_params.get('pyr_scale', 0.5) * 10))
        self.levels_spin.setValue(optical_flow_params.get('levels', 4))
        self.winsize_slider.setValue(optical_flow_params.get('winsize', 61))
        self.iterations_spin.setValue(optical_flow_params.get('iterations', 7))
        self.poly_n_slider.setValue(optical_flow_params.get('poly_n', 7))
        self.poly_sigma_slider.setValue(int(optical_flow_params.get('poly_sigma', 1.1) * 10))
        
        # 网格参数 - 从sensor对象读取
        self.cell_size_spin.setValue(getattr(sensor, 'cell_size', 1))
        self.step_spin.setValue(getattr(sensor, 'optical_flow_step', 35))
        self.pressure_scale_slider.setValue(int(getattr(sensor, 'pressure_scale', 4)))
        pressure_mode = int(getattr(sensor, 'pressure_form_switch', 0.0))
        if pressure_mode not in (0, 1, 2):
            pressure_mode = 0
        self.pressure_form_switch.setCurrentIndex(pressure_mode)
        
        # ROI参数 - 从sensor对象读取
        self.roi_x1_spin.setValue(getattr(sensor, 'roi_x1', 160))
        self.roi_x2_spin.setValue(getattr(sensor, 'roi_x2', 540))
        self.roi_y1_spin.setValue(getattr(sensor, 'roi_y1', 0))
        self.roi_y2_spin.setValue(getattr(sensor, 'roi_y2', 430))
        self.update_roi_size_label()
        
        # 显示参数 - 从sensor对象读取
        self.scale_factor_slider.setValue(int(getattr(sensor, 'scale_factor', 0.5) * 10))
        angle_val = int(getattr(sensor, 'display_angle', 0))
        self.preview_angle_spin.setValue(angle_val)
        self.set_preview_angle(angle_val)
        
        # 3D压力图缩放系数 - 从sensor对象读取
        self.fx_scale_slider.setValue(int(getattr(sensor, 'fx_scale', 0.1) * 100))
        self.fy_scale_slider.setValue(int(getattr(sensor, 'fy_scale', 0.1) * 100))
        self.fz_scale_slider.setValue(int(getattr(sensor, 'fz_scale', 0.05) * 100))
        
        # 相机参数 - 从sensor对象读取
        # 色彩调整组
        hue_val = camera_params.get('hue', 0.0)
        self.hue_slider.setValue(int(hue_val))
        self.hue_spin.setValue(float(hue_val))
        
        saturation_val = camera_params.get('saturation', 64)
        self.saturation_slider.setValue(int(saturation_val))
        self.saturation_spin.setValue(int(saturation_val))
        
        gamma_val = camera_params.get('gamma', 500)
        self.gamma_slider.setValue(int(gamma_val))
        self.gamma_spin.setValue(int(gamma_val))
        
        # 曝光控制组
        auto_exp = camera_params.get('auto_exposure', 0.0)
        self.auto_exposure_check.setChecked(auto_exp != 0.0)
        
        exposure_val = camera_params.get('exposure', -5.0)
        self.exposure_slider.setValue(int(exposure_val))
        self.exposure_spin.setValue(float(exposure_val))
        
        # 图像质量组
        contrast_val = camera_params.get('contrast', 50)
        self.contrast_slider.setValue(int(contrast_val))
        self.contrast_spin.setValue(int(contrast_val))
        
        brightness_val = camera_params.get('brightness', 5)
        self.brightness_slider.setValue(int(brightness_val))
        self.brightness_spin.setValue(int(brightness_val))
        
        sharpness_val = camera_params.get('sharpness', 100)
        self.sharpness_slider.setValue(int(sharpness_val))
        self.sharpness_spin.setValue(int(sharpness_val))
        
        # 白平衡组
        auto_wb = camera_params.get('auto_wb', 0.0)
        self.auto_wb_check.setChecked(auto_wb != 0.0)
        
        wb_val = camera_params.get('white_balance_blue', 4600)
        self.white_balance_slider.setValue(int(wb_val))
        self.white_balance_spin.setValue(int(wb_val))
    
    def get_current_parameters(self):
        """获取当前界面上的参数值"""
        pressure_mode = self.pressure_form_switch.currentIndex()
        # 确保压力模式值合法
        if pressure_mode not in (0, 1, 2):
            pressure_mode = 0
        return {
            'optical_flow': {
                'pyr_scale': self.pyr_scale_slider.value()/10.0,
                'levels': self.levels_spin.value(),
                'winsize': self.winsize_slider.value(),
                'iterations': self.iterations_spin.value(),
                'poly_n': self.poly_n_slider.value(),
                'poly_sigma': self.poly_sigma_slider.value() /10.0
            },
            'grid': {
                'cell_size': self.cell_size_spin.value(),
                'step': self.step_spin.value(),
                'pressure_scale': self.pressure_scale_slider.value(),
                'pressure_form_switch': float(self.pressure_form_switch.currentIndex())
            },
            'roi': {
                'x1': self.roi_x1_spin.value(),
                'x2': self.roi_x2_spin.value(),
                'y1': self.roi_y1_spin.value(),
                'y2': self.roi_y2_spin.value()
            },
            'display': {
                'scale_factor': self.scale_factor_slider.value() / 10.0,
                'display_angle': self.preview_angle_spin.value()
            },
            'force_scale': {
                'fx_scale': self.fx_scale_slider.value()/100.0,
                'fy_scale': self.fy_scale_slider.value()/100.0,
                'fz_scale': self.fz_scale_slider.value()/100.0
            },
            'camera': {
                # 色彩调整组
                'hue': self.hue_spin.value(),
                'saturation': self.saturation_spin.value(),
                'gamma': self.gamma_spin.value(),
                
                # 曝光控制组
                'auto_exposure': 0.25 if self.auto_exposure_check.isChecked() else 0.0,
                'exposure': self.exposure_spin.value(),
                
                # 图像质量组
                'contrast': self.contrast_spin.value(),
                'brightness': self.brightness_spin.value(),
                'sharpness': self.sharpness_spin.value(),
                
                # 白平衡组
                'auto_wb': 1.0 if self.auto_wb_check.isChecked() else 0.0,
                'white_balance_blue': self.white_balance_spin.value()
            }
        }

    def choose_File(self):
        """打开文件选择窗口，读取 YAML 配置并更新界面控件"""
        from PyQt5.QtWidgets import QFileDialog
        import yaml
        import os

        # 打开文件选择对话框
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择配置文件",
            "",
            "YAML 文件 (*.yaml *.yml);;所有文件 (*)"
        )

        # 如果用户选择了文件
        if file_path:
            try:
                # 直接读取 YAML 文件内容
                with open(file_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                # 根据读取的配置更新界面控件
                self._apply_config_to_ui(config)
                # 显示成功提示
                QtWidgets.QMessageBox.information(
                    self,
                    "配置加载成功",
                    f"✓ 已成功加载配置文件:\n{os.path.basename(file_path)}\n\n"
                    f"参数已更新到界面，您可以继续调整或直接应用。"
                )

                return config

            except Exception as e:
                import traceback
                error_detail = traceback.format_exc()
                print(f"错误详情：{error_detail}")
                QtWidgets.QMessageBox.critical(
                    self,
                    "错误",
                    f"读取配置文件失败:\n{str(e)}"
                )
                return None

        return None

    def _apply_config_to_ui(self, config):
        """将配置字典应用到 UI 控件"""
        # === 光流参数 ===
        if 'params' in config:
            params = config['params']
            if 'pyr_scale' in params:
                self.pyr_scale_slider.setValue(int(params['pyr_scale'] * 10))
            if 'levels' in params:
                self.levels_spin.setValue(params['levels'])
            if 'winsize' in params:
                self.winsize_slider.setValue(params['winsize'])
            if 'iterations' in params:
                self.iterations_spin.setValue(params['iterations'])
            if 'poly_n' in params:
                self.poly_n_slider.setValue(params['poly_n'])
            if 'poly_sigma' in params:
                self.poly_sigma_slider.setValue(int(params['poly_sigma'] * 10))

        # === 基本布局参数 ===
        if 'cell_size' in config:
            self.cell_size_spin.setValue(int(config['cell_size']))

        if 'optical_flow_step' in config:
            self.step_spin.setValue(int(config['optical_flow_step']))

        if 'pressure_scale' in config:
            self.pressure_scale_slider.setValue(int(config['pressure_scale']))

        if 'pressure_form_switch' in config:
            pressure_mode = int(config['pressure_form_switch'])
            combo_index = pressure_mode
            self.pressure_form_switch.setCurrentIndex(combo_index)

        if 'display_angle' in config:
            self.preview_angle_spin.setValue(int(config['display_angle']))

        if 'scale_factor' in config:
            self.scale_factor_slider.setValue(int(config['scale_factor'] * 10))

        # === ROI 区域参数 ===
        if 'roi_x1' in config:
            self.roi_x1_spin.setValue(int(config['roi_x1']))
        if 'roi_x2' in config:
            self.roi_x2_spin.setValue(int(config['roi_x2']))
        if 'roi_y1' in config:
            self.roi_y1_spin.setValue(int(config['roi_y1']))
        if 'roi_y2' in config:
            self.roi_y2_spin.setValue(int(config['roi_y2']))

        # 更新 ROI 尺寸标签
        self.update_roi_size_label()

        # === 3D 压力图缩放系数 ===
        if 'fx_scale' in config:
            self.fx_scale_slider.setValue(int(config['fx_scale'] * 100))
        if 'fy_scale' in config:
            self.fy_scale_slider.setValue(int(config['fy_scale'] * 100))
        if 'fz_scale' in config:
            self.fz_scale_slider.setValue(int(config['fz_scale'] * 100))

        # === 摄像头参数 ===
        if 'camera_params' in config:
            camera_params = config['camera_params']

            # 色彩调整组
            if 'hue' in camera_params:
                hue_val = float(camera_params['hue'])
                self.hue_slider.setValue(int(hue_val))
                self.hue_spin.setValue(hue_val)

            if 'saturation' in camera_params:
                sat_val = int(camera_params['saturation'])
                self.saturation_slider.setValue(sat_val)
                self.saturation_spin.setValue(sat_val)

            if 'gamma' in camera_params:
                gamma_val = int(camera_params['gamma'])
                self.gamma_slider.setValue(gamma_val)
                self.gamma_spin.setValue(gamma_val)

            # 曝光控制组
            if 'auto_exposure' in camera_params:
                self.auto_exposure_check.setChecked(camera_params['auto_exposure'] != 0.0)

            if 'exposure' in camera_params:
                exp_val = float(camera_params['exposure'])
                self.exposure_slider.setValue(int(exp_val))
                self.exposure_spin.setValue(exp_val)

            # 图像质量组
            if 'contrast' in camera_params:
                contrast_val = int(camera_params['contrast'])
                self.contrast_slider.setValue(contrast_val)
                self.contrast_spin.setValue(contrast_val)

            if 'brightness' in camera_params:
                brightness_val = int(camera_params['brightness'])
                self.brightness_slider.setValue(brightness_val)
                self.brightness_spin.setValue(brightness_val)

            if 'sharpness' in camera_params:
                sharpness_val = int(camera_params['sharpness'])
                self.sharpness_slider.setValue(sharpness_val)
                self.sharpness_spin.setValue(sharpness_val)

            # 白平衡组
            if 'auto_wb' in camera_params:
                self.auto_wb_check.setChecked(camera_params['auto_wb'] != 0.0)

            if 'white_balance_blue' in camera_params:
                wb_val = int(camera_params['white_balance_blue'])
                self.white_balance_slider.setValue(wb_val)
                self.white_balance_spin.setValue(wb_val)

        print("✓ 配置已应用到界面控件")

    def apply_params(self):
        """应用当前参数到所有传感器"""
        # 获取当前参数
        new_params = self.get_current_parameters()
        
        # 验证参数
        self.param_manager.current_params = new_params
        errors = self.param_manager.validate_parameters()
        
        if errors:
            error_msg = "参数验证失败:\n" + "\n".join(errors)
            QtWidgets.QMessageBox.warning(self, "参数错误", error_msg)
            return
        
        # 循环应用到所有传感器
        success_count = 0
        for idx, sensor in enumerate(self.sensors):
            if self.param_manager.apply_to_sensor(sensor):
                success_count += 1
                print(f"参数已应用到传感器{idx+1}")
        
        if success_count == len(self.sensors):
            QtWidgets.QMessageBox.information(self, "成功", f"参数已应用到所有{len(self.sensors)}个传感器！")
        elif success_count > 0:
            QtWidgets.QMessageBox.warning(self, "部分成功", f"参数已应用到{success_count}/{len(self.sensors)}个传感器")
        else:
            QtWidgets.QMessageBox.warning(self, "错误", "参数应用失败！")
    
    def save_config(self):
        """保存配置到文件并应用到所有传感器"""
        # 获取当前参数
        new_params = self.get_current_parameters()
        
        # 验证参数
        self.param_manager.current_params = new_params
        errors = self.param_manager.validate_parameters()
        
        if errors:
            error_msg = "参数验证失败:\n" + "\n".join(errors)
            QtWidgets.QMessageBox.warning(self, "参数错误", error_msg)
            return
        
        # 先保存到文件
        if self.param_manager.save_config():
            # 循环应用到所有传感器
            success_count = 0
            for idx, sensor in enumerate(self.sensors):
                 if self.param_manager.apply_to_sensor(sensor):
                    success_count += 1
                    print(f"参数已应用到传感器{idx+1}")
            
            if success_count == len(self.sensors):
                QtWidgets.QMessageBox.information(self, "成功", f"配置已保存并应用到所有{len(self.sensors)}个传感器！")
            elif success_count > 0:
                QtWidgets.QMessageBox.warning(self, "部分成功", f"配置已保存，但仅应用到{success_count}/{len(self.sensors)}个传感器")
            else:
                QtWidgets.QMessageBox.warning(self, "部分成功", "配置已保存，但应用到传感器失败！")
        else:
            QtWidgets.QMessageBox.warning(self, "错误", "配置保存失败！")
    
    def reset_to_default(self):
        """重置为默认参数"""
        self.param_manager.reset_to_default()
        for sensor in self.sensors:
            self.param_manager.apply_to_sensor(sensor)
        self.load_current_values()
        QtWidgets.QMessageBox.information(self, "成功", "参数已重置为默认值！")
