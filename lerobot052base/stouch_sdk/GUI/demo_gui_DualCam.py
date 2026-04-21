import cv2
import os
import sys
import numpy as np
import pyqtgraph as pg
from PyQt5 import QtWidgets
from PyQt5.QtGui import QImage, QPixmap
from PyQt5 import QtCore
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from api import TouchSensor
from api.sensor_manager import MultiSensorManager
from parameter_config.parameter_config_dialog import ParameterConfigDialog
from parameter_config.parameter_manager import ParameterManager
from usb_port.usb_port_selector import USBPortSelector
import time

def init_with_ports(usb_ports):
    """使用指定的USB端口初始化双传感器管理器
    Args:
        usb_ports: 包含5个端口号的列表 [port1, port2, None, None, None]
    """
    global manager
    param_manager = ParameterManager()
    param_manager.load_config()
    
    # 过滤None值，只保留实际的端口号
    active_ports = [p for p in usb_ports[:2] if p is not None]
    
    # 创建双传感器管理器
    manager = MultiSensorManager(
        usb_ids=active_ports,
        finger_ids=[f"Sensor{i+1}" for i in range(len(active_ports))],
        param_apply_fn=param_manager.apply_to_sensor  # 共用配置
    )
    
    # 设置网格大小并校准
    for idx in range(manager.count()):
        sensor = manager.get_sensor(idx)
        # sensor.setCellSize(1)
    
    # 批量校准两个传感器
    manager.calibrate_all(frames=5)
    
    # 打印两个传感器的ROI信息
    for idx in range(manager.count()):
        sensor = manager.get_sensor(idx)
        print(f"传感器{idx+1} ROI: ({sensor.roi_x1}, {sensor.roi_y1}) 到 ({sensor.roi_x2}, {sensor.roi_y2})，宽度: {sensor.width} 高度: {sensor.height}")

class Force3DSurfaceApp(QtWidgets.QWidget):
    def __init__(self, grid_shape, max_hist_time=10, fps=30, cap=None):
        super().__init__()
        self.setWindowTitle("3D Pressure Surface + Tangential Force Field + Total Force History")
        self.resize(1440, 900)
        main_vbox = QtWidgets.QVBoxLayout()
        self.setLayout(main_vbox)

        # 自动摄像头旋转设置
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.rotate_camera)
        self.camera_rotation_active = False # 禁止自动旋转

        # ---------- 上区（左右横排）：双传感器压力图+光流 ----------
        upper_hbox = QtWidgets.QHBoxLayout()
        main_vbox.addLayout(upper_hbox, stretch=3)

        # 左：传感器1压力图+光流叠加
        sensor1_vbox = QtWidgets.QVBoxLayout()
        sensor1_label = QtWidgets.QLabel("传感器1 (压力图+光流箭头)")
        sensor1_label.setAlignment(QtCore.Qt.AlignCenter)
        sensor1_label.setStyleSheet("color: white; font-weight: bold;")
        sensor1_vbox.addWidget(sensor1_label)
        self.pressure_view_1 = QtWidgets.QLabel()
        self.pressure_view_1.setAlignment(QtCore.Qt.AlignCenter)
        self.pressure_view_1.setStyleSheet("background-color: black;")
        sensor1_vbox.addWidget(self.pressure_view_1, stretch=1)
        upper_hbox.addLayout(sensor1_vbox, stretch=1)

        # 右：传感器2压力图+光流叠加
        sensor2_vbox = QtWidgets.QVBoxLayout()
        sensor2_label = QtWidgets.QLabel("传感器2 (压力图+光流箭头)")
        sensor2_label.setAlignment(QtCore.Qt.AlignCenter)
        sensor2_label.setStyleSheet("color: white; font-weight: bold;")
        sensor2_vbox.addWidget(sensor2_label)
        self.pressure_view_2 = QtWidgets.QLabel()
        self.pressure_view_2.setAlignment(QtCore.Qt.AlignCenter)
        self.pressure_view_2.setStyleSheet("background-color: black;")
        sensor2_vbox.addWidget(self.pressure_view_2, stretch=1)
        upper_hbox.addLayout(sensor2_vbox, stretch=1)

        # ---------- 下区：双传感器力曲线 ----------
        self.max_hist_time = max_hist_time
        self.fps = fps
        self.hist_len = int(max_hist_time * fps)
        
        # 为两个传感器各自创建历史数据数组
        self.fx_hist = [np.zeros(self.hist_len, dtype=np.float32) for _ in range(2)]
        self.fy_hist = [np.zeros(self.hist_len, dtype=np.float32) for _ in range(2)]
        self.fz_hist = [np.zeros(self.hist_len, dtype=np.float32) for _ in range(2)]
        self.idx = [0, 0]  # 两个传感器各自的索引
        self.time_axis = np.linspace(-max_hist_time, 0, self.hist_len)
        
        lower_hbox = QtWidgets.QHBoxLayout()
        main_vbox.addLayout(lower_hbox, stretch=2)
        
        # 传感器1力曲线
        self.pgwin_1 = pg.PlotWidget(title="传感器1 - 力曲线 (last {}s)".format(max_hist_time))
        self.pgwin_1.setLabel('left', 'Force')
        self.pgwin_1.setLabel('bottom', 'Time (s)')
        self.pgwin_1.addLegend()
        self.pgwin_1.setYRange(-100, 100)
        self.fx_curve_1 = self.pgwin_1.plot(self.time_axis, self.fx_hist[0], pen=pg.mkPen('r', width=2), name='Fx')
        self.fy_curve_1 = self.pgwin_1.plot(self.time_axis, self.fy_hist[0], pen=pg.mkPen('g', width=2), name='Fy')
        self.fz_curve_1 = self.pgwin_1.plot(self.time_axis, self.fz_hist[0], pen=pg.mkPen('b', width=2), name='Fz')
        lower_hbox.addWidget(self.pgwin_1, stretch=1)
        
        # 传感器2力曲线
        self.pgwin_2 = pg.PlotWidget(title="传感器2 - 力曲线 (last {}s)".format(max_hist_time))
        self.pgwin_2.setLabel('left', 'Force')
        self.pgwin_2.setLabel('bottom', 'Time (s)')
        self.pgwin_2.addLegend()
        self.pgwin_2.setYRange(-100, 100)
        self.fx_curve_2 = self.pgwin_2.plot(self.time_axis, self.fx_hist[1], pen=pg.mkPen('r', width=2), name='Fx')
        self.fy_curve_2 = self.pgwin_2.plot(self.time_axis, self.fy_hist[1], pen=pg.mkPen('g', width=2), name='Fy')
        self.fz_curve_2 = self.pgwin_2.plot(self.time_axis, self.fz_hist[1], pen=pg.mkPen('b', width=2), name='Fz')
        lower_hbox.addWidget(self.pgwin_2, stretch=1)
        self.frame_counts = 0
        self.fps_start_times = time.time()

        # 添加按钮区域
        button_layout = QtWidgets.QHBoxLayout()
        
        # 添加校准按钮
        self.calibrate_btn = QtWidgets.QPushButton("Calibrate (Press C)")
        self.calibrate_btn.clicked.connect(self.calibrate)
        self.calibrate_btn.setStyleSheet("""
            QPushButton { 
                background-color: #28a745; 
                color: white; 
                font-weight: bold; 
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #218838; }
            QPushButton:pressed { background-color: #1e7e34; }
        """)
        button_layout.addWidget(self.calibrate_btn)
        
        # 参数配置按钮
        self.config_btn = QtWidgets.QPushButton("参数配置")
        self.config_btn.clicked.connect(self.open_parameter_config)
        self.config_btn.setStyleSheet("""
            QPushButton { 
                background-color: #17a2b8; 
                color: white; 
                font-weight: bold; 
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #138496; }
            QPushButton:pressed { background-color: #117a8b; }
        """)
        button_layout.addWidget(self.config_btn)
        
        # 添加退出按钮
        self.quit_btn = QtWidgets.QPushButton("Quit")
        self.quit_btn.clicked.connect(self.quit_application)
        self.quit_btn.setStyleSheet("""
            QPushButton { 
                background-color: #ff6b6b; 
                color: white; 
                font-weight: bold; 
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #ff5252; }
            QPushButton:pressed { background-color: #ff4444; }
        """)
        button_layout.addWidget(self.quit_btn)
        
        main_vbox.addLayout(button_layout)
        
        # 设置键盘事件处理
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.keyPressEvent = self.handle_key_press
        
        # 初始化退出标志
        self.should_exit = False
        
        # 按钮防抖标志
        self.button_processing = False
        
        # 添加数据处理定时器 - 降低频率减少CPU占用
        self.data_timer = QtCore.QTimer()
        self.data_timer.timeout.connect(self.update_data)
        self.data_timer.start(5)  # max 200fps

    def rotate_camera(self):
        pass  # 已不再使用 glv 相关内容

    def toggle_camera_rotation(self, event):
        pass  # 已不再使用 glv 相关内容

    def calibrate(self):
        """校准按钮处理 - 添加防抖"""
        if self.button_processing:
            return
        self.button_processing = True
        
        try:
            global manager
            # 使用MultiSensorManager批量校准
            manager.calibrate_all(frames=5)
            print("所有传感器校准完成！")
        except Exception as e:
            print(f"校准出错: {e}")
        finally:
            # 延迟重置防抖标志
            QtCore.QTimer.singleShot(1000, lambda: setattr(self, 'button_processing', False))
    
    def open_parameter_config(self):
        """打开参数配置对话框 - 添加防抖"""
        if self.button_processing:
            return
        self.button_processing = True
        
        try:
            global manager
            # 传入所有传感器用于双摄像头预览
            sensors = [manager.get_sensor(0), manager.get_sensor(1)]
            dialog = ParameterConfigDialog(sensors, self)
            result = dialog.exec_()
            
            if result == QtWidgets.QDialog.Accepted:
                # 重新加载配置并应用到所有传感器
                param_manager = ParameterManager()
                param_manager.load_config()
                for idx in range(manager.count()):
                    sensor = manager.get_sensor(idx)
                    param_manager.apply_to_sensor(sensor)
                    print(f"参数已应用到传感器{idx+1}")
                print("参数配置已应用到所有传感器")
            else:
                print("参数配置已取消")
        except Exception as e:
            print(f"参数配置出错: {e}")
        finally:
            # 延迟重置防抖标志
            QtCore.QTimer.singleShot(500, lambda: setattr(self, 'button_processing', False))
    
    def quit_application(self):
        """退出应用程序 - 立即响应"""
        print("退出应用程序...")
        self.close()
        # 设置退出标志
        self.should_exit = True
        QtWidgets.QApplication.quit()
    
    def handle_key_press(self, event):
        """处理键盘事件"""
        if event.key() == QtCore.Qt.Key_Q:
            print("按Q键退出")
            self.quit_application()
        elif event.key() == QtCore.Qt.Key_C:
            print("按C键重新校准")
            self.calibrate()
        else:
            super().keyPressEvent(event)
    
    def update_data(self):
        """定时器触发的数据处理方法 - 处理双传感器"""
        global manager

        if self.should_exit:
            return

        try:
            # 循环处理两个传感器
            for sensor_idx in range(2):
                sensor = manager.get_sensor(sensor_idx)
                
                # 使用TouchSensor API获取帧
                frame = sensor.preprocess_frame()
                if frame is None:
                    continue

                # 获取压力矩阵
                pressure_matrix_raw = sensor.get_pressure_matrix(frame)
                pressure_matrix = np.clip(pressure_matrix_raw, 0, None)
                # 噪声过滤
                pressure_matrix = np.where(pressure_matrix < 1, 0, pressure_matrix)

                # 归一化处理
                pressure_scale = sensor.pressure_scale
                pressure_matrix = np.clip(pressure_matrix * pressure_scale, 0, 255)

                # 转为uint8灰度图
                gray_img = pressure_matrix.astype(np.uint8)
                
                # 根据 pressure_form_switch 选择显示模式
                if hasattr(sensor, 'pressure_form_switch') and sensor.pressure_form_switch != 0.0:
                    # 彩色热力图显示模式
                    display_img = cv2.applyColorMap(gray_img, cv2.COLORMAP_JET)
                else:
                    # 灰度图显示模式（默认）
                    display_img = cv2.cvtColor(gray_img, cv2.COLOR_GRAY2RGB)

                # 获取光流并叠加箭头到压力图上
                flow_x, flow_y = sensor.get_flow_matrix(frame)
                
                # 在压力图上绘制光流箭头
                step = sensor.optical_flow_step
                h_flow, w_flow = flow_x.shape
                
                # 采样网格点
                grid_y, grid_x = np.mgrid[
                                 step / 2:h_flow:step,
                                 step / 2:w_flow:step
                                 ].reshape(2, -1).astype(int)
                
                # 缩放显示
                sampled_fx = flow_x[grid_y, grid_x] * 4.5
                sampled_fy = flow_y[grid_y, grid_x] * 4.5
                
                # 在压力图上绘制箭头（白色箭头，带黑色边框）
                for (x, y, dx, dy) in zip(grid_x, grid_y, sampled_fx, sampled_fy):
                    end_point = (int(x + dx), int(y + dy))
                    # 绘制黑色边框增强对比度
                    cv2.arrowedLine(display_img, (x, y), end_point, (0, 0, 0), 3, tipLength=0.3)
                    # 绘制白色箭头
                    cv2.arrowedLine(display_img, (x, y), end_point, (255, 255, 255), 2, tipLength=0.3)

                # 更新对应的QLabel显示
                h, w, ch = display_img.shape
                bytes_per_line = ch * w
                q_img = QImage(display_img.data, w, h, bytes_per_line, QImage.Format_BGR888)
                pixmap = QPixmap.fromImage(q_img)
                
                # 根据sensor_idx选择对应的view
                target_view = self.pressure_view_1 if sensor_idx == 0 else self.pressure_view_2
                scaled_pixmap = pixmap.scaled(
                    target_view.width(),
                    target_view.height(),
                    QtCore.Qt.KeepAspectRatio,
                    QtCore.Qt.SmoothTransformation
                )
                target_view.setPixmap(scaled_pixmap)

                # 计算总力
                fx_total, fy_total, fz_total = sensor.get_total_force(
                    pressure_matrix=pressure_matrix_raw,
                    flow_x=flow_x,
                    flow_y=flow_y
                )
                
                fx_sum = fx_total * 1
                fy_sum = fy_total * 1
                fz_sum = fz_total * 0.01
                
                # 更新对应传感器的力曲线
                self.update_force_history(sensor_idx, fx_sum, fy_sum, fz_sum)
        
        except Exception as e:
            print(f"数据处理出错: {e}")
            # 出错时不退出，继续运行


    def update_force_history(self, sensor_idx, fx_sum, fy_sum, fz_sum):
        """更新指定传感器的力曲线历史数据
        
        Args:
            sensor_idx: 传感器索引 (0或1)
            fx_sum, fy_sum, fz_sum: 三轴力值
        """
        idx = self.idx[sensor_idx]
        self.fx_hist[sensor_idx][idx] = fx_sum
        self.fy_hist[sensor_idx][idx] = fy_sum
        self.fz_hist[sensor_idx][idx] = fz_sum
        
        fx_disp = np.roll(self.fx_hist[sensor_idx], -idx)
        fy_disp = np.roll(self.fy_hist[sensor_idx], -idx)
        fz_disp = np.roll(self.fz_hist[sensor_idx], -idx)
        
        # 根据sensor_idx选择对应的curve
        if sensor_idx == 0:
            self.fx_curve_1.setData(self.time_axis, fx_disp)
            self.fy_curve_1.setData(self.time_axis, fy_disp)
            self.fz_curve_1.setData(self.time_axis, fz_disp)
        else:
            self.fx_curve_2.setData(self.time_axis, fx_disp)
            self.fy_curve_2.setData(self.time_axis, fy_disp)
            self.fz_curve_2.setData(self.time_axis, fz_disp)
        
        self.idx[sensor_idx] = (self.idx[sensor_idx] + 1) % self.hist_len


# 主循环
if __name__ == "__main__":
    # 创建Qt应用程序
    app = QtWidgets.QApplication([])
    
    # 单次弹出多端口选择窗口
    print("请选择传感器USB端口...")
    port_selector = USBPortSelector()
    if port_selector.exec_() != QtWidgets.QDialog.Accepted:
        print("用户取消了USB端口选择")
        sys.exit(0)
    
    # 获取选中的所有端口 [port1, port2, None, None, None]
    selected_ports = port_selector.get_selected_ports()
    
    # 检查是否至少选择了一个端口
    if selected_ports[0] is None and selected_ports[1] is None:
        print("未选择任何端口")
        sys.exit(1)
    
    print(f"已选择端口: {selected_ports}")
    
    # 使用选中的端口初始化双传感器管理器
    global manager
    init_with_ports(selected_ports)
    
    # 使用第一个传感器的网格参数（两个传感器共用配置，参数相同）
    sensor1 = manager.get_sensor(0)
    surf_win = Force3DSurfaceApp((sensor1.grid_rows, sensor1.grid_cols), max_hist_time=10, fps=30)
    surf_win.show()
    
    print("按q退出，按c重新校准压力，或点击Quit按钮退出。")
    
    # 使用Qt的事件循环，让定时器处理数据更新
    app.exec_()

    # 释放资源
    manager.release_all()
    app.quit()
