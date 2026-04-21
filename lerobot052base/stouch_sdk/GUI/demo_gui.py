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
from parameter_config.parameter_config_dialog import ParameterConfigDialog
from parameter_config.parameter_manager import ParameterManager
from usb_port.usb_port_selector import USBPortSelector
import time


def init_with_port(usb_port):
    """使用指定的USB端口初始化传感器"""
    global sensor
    sensor = TouchSensor(usb_id=usb_port, finger_id="usb_sensor", cap=None)

    # 利用 sensor 已经动态定位好的路径来初始化管理器
    param_manager = ParameterManager(config_file=sensor.config_path)

    param_manager.load_config()
    param_manager.apply_to_sensor(sensor)
    sensor.setCellSize(1)
    sensor.calibrate_base_matrix(5) # 在程序刚开始运行的时候跑一遍calibrate
    print(f"当前ROI: ({sensor.roi_x1}, {sensor.roi_y1}) 到 ({sensor.roi_x2}, {sensor.roi_y2})，宽度: {sensor.width} 高度: {sensor.height}")

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

        # ---------- 上区（左右横排） ----------
        upper_hbox = QtWidgets.QHBoxLayout()
        main_vbox.addLayout(upper_hbox, stretch=3)

        # 左：压力显示（2D QLabel / 3D 点云切换）
        self.pressure_stack = QtWidgets.QStackedWidget()
        self.pressure_view = QtWidgets.QLabel()
        self.pressure_view.setAlignment(QtCore.Qt.AlignCenter)
        self.pressure_view.setStyleSheet("background-color: black;")
        self.pressure_stack.addWidget(self.pressure_view)
        upper_hbox.addWidget(self.pressure_stack, stretch=2)

        # 右：切向力2D平面
        self.tangent_view = QtWidgets.QLabel()
        self.tangent_view.setAlignment(QtCore.Qt.AlignCenter)
        self.tangent_view.setStyleSheet("background-color: black;")
        upper_hbox.addWidget(self.tangent_view, stretch=2)

        # ---------- 下区：总力曲线 ----------
        self.max_hist_time = max_hist_time
        self.fps = fps
        self.hist_len = int(max_hist_time * fps)
        self.fx_hist = np.zeros(self.hist_len, dtype=np.float32)
        self.fy_hist = np.zeros(self.hist_len, dtype=np.float32)
        self.fz_hist = np.zeros(self.hist_len, dtype=np.float32)
        self.idx = 0
        self.time_axis = np.linspace(-max_hist_time, 0, self.hist_len)
        self.pgwin = pg.PlotWidget(title="Total Force (last {}s)".format(max_hist_time))
        self.pgwin.setBackground('w')  # 设置白色背景
        self.pgwin.setLabel('left', 'Force')
        self.pgwin.setLabel('bottom', 'Time (s)')
        self.pgwin.addLegend()
        self.pgwin.setYRange(-100, 100)
        self.fx_curve = self.pgwin.plot(self.time_axis, self.fx_hist, pen=pg.mkPen('r', width=4), name='Fx')
        self.fy_curve = self.pgwin.plot(self.time_axis, self.fy_hist, pen=pg.mkPen('g', width=4), name='Fy')
        self.fz_curve = self.pgwin.plot(self.time_axis, self.fz_hist, pen=pg.mkPen('b', width=4), name='Fz')
        main_vbox.addWidget(self.pgwin, stretch=2)
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

        # 新增：动态自适应开关与重置视图按钮布局
        align_layout = QtWidgets.QHBoxLayout()

        # 动态自适应开关按钮
        self.dynamic_range_enabled = False  # 初始状态为静态
        self.dynamic_range_btn = QtWidgets.QPushButton("Y轴自适应：关闭")
        self.dynamic_range_btn.clicked.connect(self.toggle_dynamic_range)
        self.dynamic_range_btn.setStyleSheet("""
            QPushButton { 
                background-color: #6f42c1; 
                color: white; 
                font-weight: bold; 
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #5a32a3; }
        """)

        self.reset_view_btn = QtWidgets.QPushButton("重置视图")
        self.reset_view_btn.clicked.connect(self.reset_view)
        self.reset_view_btn.setStyleSheet(
            "background-color: #6c757d; color: white; font-weight: bold; padding: 8px 16px; border-radius: 4px;")

        align_layout.addWidget(self.dynamic_range_btn)
        align_layout.addWidget(self.reset_view_btn)

        main_vbox.addLayout(button_layout)
        main_vbox.addLayout(align_layout)  # 将对齐布局加入主视图
        main_vbox.addWidget(self.pgwin, stretch=2)

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
            global sensor
            # 使用TouchSensor API进行校准
            sensor.calibrate_base_matrix(5)
            print("Calibration completed!")
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
            global sensor
            dialog = ParameterConfigDialog(sensor, self)
            result = dialog.exec_()

            if result == QtWidgets.QDialog.Accepted:
                print("参数配置已应用")
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

    def toggle_dynamic_range(self):
        """新增：切换动态自适应量程状态"""
        self.dynamic_range_enabled = not self.dynamic_range_enabled
        status_text = "开启" if self.dynamic_range_enabled else "关闭"
        self.dynamic_range_btn.setText(f"Y轴自适应：{status_text}")

        # 核心修改：点击开启时，单次执行 X 轴定位，将 0 刻度放到最右侧
        if self.dynamic_range_enabled:
            # 定位 X 轴：使用 float() 转换以避免 numpy 类型引起的 overflow 警告
            self.pgwin.getViewBox().setXRange(float(self.time_axis[0]), 0.0, padding=0)
            # 同时也执行一次单次的 Y 轴对齐，让画面立刻居中
            self.align_global_view()

        print(f"Y轴自适应已{status_text}")

    def align_global_view(self):
        """辅助：执行全局视角对准，确保正负方向最小量程均为 100"""
        # 合并所有历史数据
        all_data = np.concatenate([self.fx_hist, self.fy_hist, self.fz_hist])
        finite_data = all_data[np.isfinite(all_data)]
        if len(finite_data) == 0: return

        # 获取当前数据的实际极值
        data_min, data_max = np.min(finite_data), np.max(finite_data)

        # 核心逻辑：确保显示范围最小值不大于 -100，最大值不小于 100
        # 这样即使数据很小，视图也会维持在 [-100, 100]；如果数据超过 100，视图会继续扩大
        view_min = min(float(data_min), -100.0)
        view_max = max(float(data_max), 100.0)

        # 适当增加 10% 的边缘缓冲，防止曲线贴边
        margin = (view_max - view_min) * 0.1

        self.pgwin.getViewBox().setYRange(view_min - margin, view_max + margin, padding=0)

    def reset_view(self):
        """新增：重置视图到初始状态，同时关闭动态自适应"""
        # 如果当前是开启状态，先关闭它
        if self.dynamic_range_enabled:
            self.toggle_dynamic_range()

        view_box = self.pgwin.getViewBox()
        # 使用 float() 转换
        view_box.setXRange(float(self.time_axis[0]), 0.0, padding=0)
        view_box.setYRange(-100.0, 100.0, padding=0)
        print("视图已重置为默认范围 [-100, 100]")

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
        """定时器触发的数据处理方法 - 优化性能"""
        global sensor, prev_frame

        if self.should_exit:
            return

        try:
            # 使用TouchSensor API获取帧
            frame = sensor.preprocess_frame()
            if frame is None:
                self.quit_application()
                return

            # 获取压力矩阵
            pressure_matrix_raw = sensor.get_pressure_matrix(frame)
            pressure_matrix = np.clip(pressure_matrix_raw, 0, None)
            # 噪声过滤：如果平均色调小于1，认为是噪声，设为0
            pressure_matrix = np.where(pressure_matrix < 1, 0, pressure_matrix)

            # 归一化处理：将 (0, x) 映射到 (0, 255)
            # x = 20
            # pressure_matrix = np.clip(pressure_matrix, 0, x) * 255.0 / x
            pressure_scale = sensor.pressure_scale
            pressure_matrix = np.clip(pressure_matrix * pressure_scale, 0, 255)

            # 转为uint8灰度图
            gray_img = pressure_matrix.astype(np.uint8)
            flow_x, flow_y = sensor.get_flow_matrix(frame)

            pressure_mode = int(getattr(sensor, 'pressure_form_switch', 0.0))

            # 取消3D显示功能，强制使用2D显示模式
            if pressure_mode == 3:
                # 原3D模式，改为灰度图显示
                pressure_mode = 0

            self.pressure_stack.setCurrentIndex(0)   # 始终使用QLabel显示2D图像

            if pressure_mode == 0:  # 灰度
                display_img = cv2.cvtColor(gray_img, cv2.COLOR_GRAY2RGB)
            elif pressure_mode == 1:  # 热力
                display_img = cv2.applyColorMap(gray_img, cv2.COLORMAP_JET)
            else:  # pressure_mode == 2 或其他，显示原始BGR图像
                display_img = frame.copy()

            h, w, ch = display_img.shape
            bytes_per_line = ch * w
            q_img = QImage(display_img.data, w, h, bytes_per_line, QImage.Format_BGR888)
            pixmap = QPixmap.fromImage(q_img)
            scaled_pixmap = pixmap.scaled(
                self.pressure_view.width(),
                self.pressure_view.height(),
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.SmoothTransformation
            )
            self.pressure_view.setPixmap(scaled_pixmap)

            fx_total, fy_total, fz_total = sensor.get_total_force(
                pressure_matrix=pressure_matrix_raw,
                flow_x=flow_x,
                flow_y=flow_y
            )

            self.update_tangential_field(flow_x, flow_y)  # 显示光流可视化图像（黑底箭头）
            fx_sum = fx_total * 1
            fy_sum = fy_total * 1
            fz_sum = fz_total * 0.01
            # fz_sum = np.where(fz_sum < 0, 0, fz_sum)
            self.update_force_history(fx_sum, fy_sum, fz_sum)
            prev_frame = frame.copy()

            # # 打印最大压力
            # print(pressure_matrix.max())

            # 计算FPS
            self.frame_counts += 1

            if self.frame_counts % 30 == 0:
                now = time.time()
                duration = now - self.fps_start_times
                if duration > 0:
                    fps = 30.0 / duration
                    print(f"Sensor {0} FPS: {fps:.2f}")
                self.fps_start_times = now

            # # 打印pressure矩阵的行数和列数
            # print(f"pressure_matrix shape: {pressure_matrix.shape[0]} rows, {pressure_matrix.shape[1]} cols")

        except Exception as e:
            print(f"数据处理出错: {e}")
            # 出错时不退出，继续运行

    def update_force_history(self, fx_sum, fy_sum, fz_sum):
        self.fx_hist[self.idx] = fx_sum
        self.fy_hist[self.idx] = fy_sum
        self.fz_hist[self.idx] = fz_sum
        idx = self.idx
        fx_disp = np.roll(self.fx_hist, -idx)
        fy_disp = np.roll(self.fy_hist, -idx)
        fz_disp = np.roll(self.fz_hist, -idx)
        self.fx_curve.setData(self.time_axis, fx_disp)
        self.fy_curve.setData(self.time_axis, fy_disp)
        self.fz_curve.setData(self.time_axis, fz_disp)
        self.idx = (self.idx + 1) % self.hist_len

        # 实时动态量程调整逻辑：仅对 Y 轴进行持续调整，使三条线始终在视野内
        if self.dynamic_range_enabled:
            self.align_global_view()

    def update_tangential_field(self, flow_x, flow_y):
        """更新显示光流可视化图像（黑底箭头）"""
        # 使用TouchSensor API获取光流可视化图像
        global sensor
        # flow_vis_img = sensor.visualize_flow()
        # frame_bgr = sensor.preprocess_frame()
        # flow_x, flow_y = self.update_data(frame_bgr)

        step = sensor.optical_flow_step
        h, w = flow_x.shape

        # 采样网格点
        grid_y, grid_x = np.mgrid[
                         step / 2:h:step,
                         step / 2:w:step
                         ].reshape(2, -1).astype(int)

        # 缩放显示
        sampled_fx = flow_x[grid_y, grid_x] * 4.5
        sampled_fy = flow_y[grid_y, grid_x] * 4.5

        # 黑底图像
        flow_vis_img = np.zeros((h, w, 3), dtype=np.uint8)

        # 绘制箭头
        for (x, y, dx, dy) in zip(grid_x, grid_y, sampled_fx, sampled_fy):
            end_point = (int(x + dx), int(y + dy))
            cv2.arrowedLine(flow_vis_img, (x, y), end_point, (255, 255, 255), 2, tipLength=0.3)

        if flow_vis_img is None:
            return

        # 将 OpenCV BGR 图像转为 QImage
        frame_rgb = cv2.cvtColor(flow_vis_img, cv2.COLOR_BGR2RGB)
        h, w, ch = frame_rgb.shape
        bytes_per_line = ch * w
        q_img = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)

        # 缩放图像以适应窗口大小
        pixmap = QPixmap.fromImage(q_img)
        scaled_pixmap = pixmap.scaled(
            self.tangent_view.width(),
            self.tangent_view.height(),
            QtCore.Qt.KeepAspectRatio,
            QtCore.Qt.SmoothTransformation
        )
        self.tangent_view.setPixmap(scaled_pixmap)


# 主循环
if __name__ == "__main__":
    # 创建Qt应用程序
    app = QtWidgets.QApplication([])

    # 显示USB端口选择对话框
    port_selector = USBPortSelector()
    if port_selector.exec_() != QtWidgets.QDialog.Accepted:
        print("用户取消了USB端口选择")
        sys.exit(0)

    # 获取选中的USB端口
    selected_port = port_selector.get_selected_port()
    if selected_port is None:
        print("未选择USB端口")
        sys.exit(1)

    print(f"已选择USB端口: {selected_port}")

    # 使用选中的端口初始化传感器
    global sensor
    init_with_port(selected_port)

    # 使用TouchSensor API获取第一帧
    prev_frame = sensor.preprocessed_frame

    # 使用API中的网格参数
    surf_win = Force3DSurfaceApp((sensor.grid_rows, sensor.grid_cols), max_hist_time=10, fps=30)
    surf_win.show()

    print("按q退出，按c重新校准压力，或点击Quit按钮退出。")

    # 使用Qt的事件循环，让定时器处理数据更新
    app.exec_()

    # release(cap)
    app.quit()