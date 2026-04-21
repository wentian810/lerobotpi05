import cv2
import os
import sys
import numpy as np
import math
import yaml

class TouchSensor():

    def __init__(self, usb_id=None, finger_id=None, cap=None):
        """
        Initialize touch sensor with camera and finger ID.

        Args:
            usb_id: USB ID of the camera device
            finger_id: Unique identifier for this finger sensor
            cap: Optional external video capture object (MODIFIED: 添加外部视频捕获对象支持)
        """
        self.usb_id = usb_id
        self.finger_id = finger_id
        self.cap = cap  # MODIFIED: 支持外部传入的cap对象
        self.calibration_hue = None
        # self.CAMERA_SETTINGS_FILE = 'camera_settings.txt'
        self.first_frame_gray = None
        self.width = None
        self.height = None
        self.grid_cols = None
        self.grid_rows = None
        self.cell_size = None
        self.scale_factor = None
        self.display_angle = None
        self.last_flow = None
        self.optical_flow_step = None
        self.roi_x1 = None
        self.roi_y1 = None
        self.roi_x2 = None
        self.roi_y2 = None
        self.fx_scale = None
        self.fy_scale = None
        self.fz_scale = None
        self.pressure_threshold = None
        self.pressure_scale = None
        self.pressure_form_switch = None  # 压力图显示模式（0=灰度，1=彩色，2=3D指尖视图，3=3D点云视图）
        self.threshold2D = 7 ##TODO: need calibrate
        self.threshold3D = 7  ##TODO: need calibrate
        # 触摸状态机相关
        self.contact_threshold = None
        self.release_threshold = None
        self.slide_threshold = None
        self.slide_force_std_threshold = None
        self.current_status = "IDLE"
        self.fz_history = []
        self.preprocessed_frame = None
        self.flow_max = None
        self.flow_min = None


        self.params = {
            'pyr_scale': None,  # 金字塔缩放因子
            'levels': None,  # 金字塔层数
            'winsize': None,  # 窗口大小
            'iterations': None,  # 迭代次数
            'poly_n': None,  # 多项式邻域大小
            'poly_sigma': None,  # 高斯标准差
            'flags': None
        }
        # 相机参数（动态参数，排除frame_width和frame_height）
        self.camera_params = {
            'hue': None,
            'auto_exposure': None,
            'exposure': None,
            'contrast': None,
            'auto_wb': None,
            'white_balance_blue': None,
            'saturation': None,
            'brightness': None,
            'sharpness': None,
            'gamma': None
        }
        # self.debug_level = 1 # 1 is verbose, 2 only report error msg, 3 is silent. Default is 1

        # 从配置文件加载参数（覆盖默认值）


        # Initialize camera

        #--------------------------------#
        # MODIFIED: 只有在没有外部cap对象时才初始化摄像头
        if self.cap is None:
            self.camera_init()
        else:
            # MODIFIED: 如果已经有cap对象，设置ROI为视频尺寸
            if self.cap.isOpened():
                self.roi_x2 = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                self.roi_y2 = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                self.scale_factor = 0.5  # MODIFIED: 设置缩放因子
                # 自动赋值 width 和 height，避免 NoneType 错误
                self.setRoi(self.roi_x1, self.roi_x2, self.roi_y1, self.roi_y2)
        #--------------------------------#

    def load_config(self, config_path=None):
        """
        从YAML文件加载配置参数（增强版：支持任意工作目录启动及打包环境）
        """
        if config_path is None:
            # 1. 获取程序运行的基础目录
            if getattr(sys, 'frozen', False):
                # 如果是 PyInstaller 打包后的路径 (.exe)
                base_dir = os.path.dirname(sys.executable)
            else:
                # 如果是源码运行，先获取当前文件 touch_sensor.py 所在的 api 目录
                # 再取其上一级，即 SDK 根目录
                api_dir = os.path.dirname(os.path.abspath(__file__))
                base_dir = os.path.normpath(os.path.join(api_dir, ".."))

            # 2. 拼接配置文件的绝对路径
            # 默认假设配置文件在 SDK 根目录下
            config_path = os.path.join(base_dir, "parameters.yaml")

            # 备选方案：如果根目录没找到，去 GUI 目录下找
            if not os.path.exists(config_path):
                gui_config_path = os.path.join(base_dir, "api", "parameters.yaml")
                if os.path.exists(gui_config_path):
                    config_path = gui_config_path

                # 【核心修改点】：将找到的路径永久保存在实例属性中
        self.config_path = os.path.abspath(config_path)
        print(f"--- 配置文件路径已锁定: {self.config_path} ---")

        # 3. 打印最终确定的绝对路径，方便调试
        print(f"--- 配置文件加载中 ---")
        print(f"搜索路径: {os.path.abspath(config_path)}")

        # 4. 健壮性检查
        if not os.path.exists(config_path):
            error_msg = (
                f"\n[错误] 找不到配置文件！"
                f"\n当前尝试路径: {os.path.abspath(config_path)}"
                f"\n请确认 'params_config_repair.yaml' 文件是否存在于该位置。"
            )
            print(error_msg)
            # 为了防止程序崩溃，这里可以根据需求选择 raise 或 return
            raise FileNotFoundError(error_msg)

        # 5. 执行加载
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            print("--- 配置文件加载成功 ---")

            # 以下为您原有的赋值逻辑
            for key, value in config.items():
                if key == 'params':
                    self.params.update(value)
                elif key == 'camera_params':
                    self.camera_params.update(value)
                elif isinstance(value, dict):
                    for k, v in value.items():
                        if hasattr(self, k) and getattr(self, k) is None:
                            setattr(self, k, v)
                elif hasattr(self, key) and getattr(self, key) is None:
                    setattr(self, key, value)

        except Exception as e:
            print(f"解析配置文件时出错: {e}")
            raise e


    def camera_init(self, camera_params=None):
        """初始化摄像头并完成传感器基础配置。

        本方法会：
        1) 从 YAML 加载默认参数（光流/ROI/缩放/相机参数等）
        2) 根据操作系统选择合适的 VideoCapture 后端并打开摄像头
        3) 设置分辨率并应用动态相机参数
        4) 依据 ROI 计算 width/height，并据此初始化网格与缩放参数
        5) 执行一次基准校准（calibrate_base_matrix）

        Args:
            camera_params: dict | None，可选的相机参数配置（会过滤 frame_width/frame_height）。
                若为 None，则使用 YAML/默认加载到 self.camera_params 的参数。
        """

        self.load_config()

        # 跨平台摄像头后端选择
        if sys.platform.startswith('win'):
            # Windows系统 - 使用DirectShow后端
            print("检测到Windows系统，使用MSMF后端")
            self.cap = cv2.VideoCapture(self.usb_id, cv2.CAP_MSMF)
        elif sys.platform.startswith('linux'):
            # Linux系统 - 使用V4L2后端
            print("检测到Linux系统，使用V4L2后端")
            self.cap = cv2.VideoCapture(self.usb_id, cv2.CAP_V4L2)
        elif sys.platform == 'darwin':
            # macOS系统 - 使用AVFoundation后端
            print("检测到macOS系统，使用AVFoundation后端")
            self.cap = cv2.VideoCapture(self.usb_id, cv2.CAP_AVFOUNDATION)
        else:
            print(f"未知系统: {sys.platform}, 使用默认后端")
            self.cap = cv2.VideoCapture(self.usb_id)

        # 检查摄像头是否成功打开
        if not self.cap.isOpened():
            print(f"错误: 无法打开摄像头 USB ID {self.usb_id}")
            print("尝试使用默认后端...")
            self.cap = cv2.VideoCapture(self.usb_id)
            if not self.cap.isOpened():
                print(f"错误: 摄像头初始化失败 USB ID {self.usb_id}")
                exit(1)

        # 预热摄像头 - 跳过前几帧
        for _ in range(5):
            ret, frame = self.cap.read()
            if not ret:
                print("警告: 摄像头预热时无法读取帧")

        # # 设置摄像头参数（仅在Windows下容易失败）
        # if sys.platform.startswith('win'):
        #     print("Windows系统下尝试设置摄像头参数...")
        #     try:
        #         # 设置分辨率
        #         self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        #         self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        #         # 设置帧率
        #         self.cap.set(cv2.CAP_PROP_FPS, 30)
        #         # 设置自动曝光
        #         self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
        #         print("摄像头参数设置完成")
        #     except Exception as e:
        #         print(f"摄像头参数设置失败: {e}")
        #         print("继续使用默认参数...")

        # 设置分辨率（单独处理，不在动态参数中）
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640.0)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480.0)

        # 应用动态相机参数（使用传入参数或默认值）
        if camera_params is None:
            # 使用默认参数
            camera_params = self.camera_params.copy()
        else:
            # 过滤掉 width/height，更新存储的参数
            filtered_params = {k: v for k, v in camera_params.items()
                             if k not in ['frame_width', 'frame_height']}
            self.camera_params.update(filtered_params)
            camera_params = filtered_params

        # 调用统一方法应用动态参数
        self.apply_camera_params(camera_params)



        # 读取第一帧进行ROI检测
        ret, frame = self.cap.read()
        if not ret:
            print(f"错误: ID: {self.finger_id} 无法获取视频流 USB ID {self.usb_id}")
            exit(1)

        # 使用已加载的配置值设置 ROI
        self.setRoi(self.roi_x1, self.roi_x2, self.roi_y1, self.roi_y2)
        self.setCellSize(self.cell_size)
        self.setScaleFactor(self.scale_factor)

        # 进行校准
        print("开始传感器校准...")
        self.calibrate_base_matrix(5)
        print("传感器初始化完成")


    def setRoi(self, x_left, x_right, y_top, y_bottom):
        """设置 ROI 并同步更新派生尺寸。

        ROI 坐标用于裁剪输入图像并决定后续矩阵尺寸。本函数除了保存 roi_x*/roi_y*
        外，还会自动计算并更新：
        - width  = roi_x2 - roi_x1 + 1
        - height = roi_y2 - roi_y1 + 1

        注意：width/height 会被 setCellSize()、光流 resize、以及多处力计算逻辑依赖。
        因此 ROI 变化后应重新调用 setRoi()，再调用 setCellSize() 以保持网格一致。

        Args:
            x_left: ROI 左边界（像素）
            x_right: ROI 右边界（像素）
            y_top: ROI 上边界（像素）
            y_bottom: ROI 下边界（像素）
        """
        self.roi_x1 = x_left
        self.roi_y1 = y_top
        self.roi_x2 = x_right
        self.roi_y2 = y_bottom
        # 自动计算并赋值 width 和 height
        # self.width = self.roi_x2 - self.roi_x1 + 1
        # self.height = self.roi_y2 - self.roi_y1 + 1
        self.width = self.roi_x2 - self.roi_x1
        self.height = self.roi_y2 - self.roi_y1


    def setCellSize(self, cell_size):
        self.cell_size = cell_size
        self.grid_cols = self.width // cell_size
        self.grid_rows = self.height // cell_size


    def setScaleFactor(self, scale_factor):
        self.scale_factor = scale_factor


    def apply_camera_params(self, camera_params):
        """
        应用相机参数到底层硬件

        Args:
            camera_params: dict, 相机参数配置（排除frame_width/frame_height）

        Returns:
            bool: 是否成功应用
        """
        if not self.cap or not self.cap.isOpened():
            return False

        # 参数名到CAP_PROP常量的映射
        param_map = {
            'hue': cv2.CAP_PROP_HUE,
            'auto_exposure': cv2.CAP_PROP_AUTO_EXPOSURE,
            'exposure': cv2.CAP_PROP_EXPOSURE,
            'contrast': cv2.CAP_PROP_CONTRAST,
            'auto_wb': cv2.CAP_PROP_AUTO_WB,
            'white_balance_blue': cv2.CAP_PROP_WHITE_BALANCE_BLUE_U,
            'saturation': cv2.CAP_PROP_SATURATION,
            'brightness': cv2.CAP_PROP_BRIGHTNESS,
            'sharpness': cv2.CAP_PROP_SHARPNESS,
            'gamma': cv2.CAP_PROP_GAMMA
        }

        # 更新存储的参数
        self.camera_params.update(camera_params)

        # 应用到底层硬件
        for param_name, value in camera_params.items():
            if param_name in param_map:
                status = self.cap.set(param_map[param_name], value)
                # print(f"设置相机参数 {param_name} = {value} : {'成功' if status else '失败'}")

        return True

    def center_crop_and_resize(self, frame, target_size=(640, 480)):
        """
        将任意分辨率的图像居中裁剪到 target_size 比例，再缩放到 target_size
        """
        h, w = frame.shape[:2]
        target_w, target_h = target_size
        target_ratio = target_w / target_h  # 4/3 ≈ 1.333

        src_ratio = w / h
        if src_ratio > target_ratio:
            # 原始图像更宽，需要水平裁剪
            crop_w = int(h * target_ratio)
            crop_h = h
            start_x = (w - crop_w) // 2
            start_y = 0
        else:
            # 原始图像更高，需要垂直裁剪
            crop_w = w
            crop_h = int(w / target_ratio)
            start_x = 0
            start_y = (h - crop_h) // 2

        cropped = frame[start_y:start_y + crop_h, start_x:start_x + crop_w]
        resized = cv2.resize(cropped, target_size, interpolation=cv2.INTER_LINEAR)
        return resized


    def preprocess_frame(self, frame=None):
        """Read and preprocess a frame from camera"""
        if not self.cap:
            print("Error: No camera found.")
            exit(-1)

        ret, frame = self.cap.read()
        frame = self.center_crop_and_resize(frame, (640, 480))
        frame = cv2.resize(frame, (640, 480))
        if not ret:
            print("Error: Can't fetch video stream")
            exit(-1)
        frame = cv2.flip(frame, 1)
        frame = cv2.rotate(frame, cv2.ROTATE_180)

        tmp_blue = frame[:, :, 0].copy().astype(np.float32)
        tmp_blue = (tmp_blue - 10) * 0.95
        tmp_blue = np.clip(tmp_blue, 0, 255).astype(np.uint8)
        frame[:, :, 0] = tmp_blue

        # 仿射变换
        angle = -getattr(self, 'display_angle', 0)
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

        self.preprocessed_frame = frame[self.roi_y1:self.roi_y2, self.roi_x1:self.roi_x2,:]

        return self.preprocessed_frame


    def calibrate_base_matrix(self, calibration_frames=5):
        """Calibrate the base matrix for pressure sensing"""
        if not self.cap:
            print("Error: Camera not initialized")
            exit(-1)

        # 先读取帧信息，将base_matrix的尺寸与hsv匹配
        # 如果 preprocessed_frame 为 None，先读取一帧
        if self.preprocessed_frame is None:
            print("警告: preprocessed_frame 为 None，正在读取初始帧...")
            self.preprocess_frame()

        frame = self.preprocessed_frame
        if frame is None:
            print("错误: 无法获取预处理帧，校准失败")
            exit(-1)

        base_matrix = np.zeros(frame.shape[:2], dtype=np.float32)

        # base_matrix = np.zeros((self.roi_y2 - self.roi_y1, self.roi_x2 - self.roi_x1), dtype=np.float32)
        print("Starting calibration... Please ensure no pressure on sensor")

        for i in range(calibration_frames):
            frame = self.preprocessed_frame
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            base_matrix += hsv[:, :, 0]

        base_matrix /= calibration_frames
        self.calibration_hue = base_matrix
        self.first_frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        # 更改pressure_threshold为校准值的平均值 + 5
        self.pressure_threshold = np.mean(self.calibration_hue) + 5
        # self.last_flow = None
        print("ID: {self.id} calibration completed! Baseline values saved")
        return base_matrix, frame


    def get_pressure_matrix(self, frame):
        """
        获取压力矩阵（优化版本）
        使用向量化操作替代循环，大幅提升性能
        """
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        hue = hsv[:, :, 0].astype(np.float32)

        if self.calibration_hue is not None:
            # ==================================
            if hue.shape != self.calibration_hue.shape:
                self.calibration_hue = None  # 丢弃错误的旧底图
                self.calibrate_base_matrix(5)  # 立即触发一次最新的校准
                return np.zeros(hue.shape, dtype=np.float32)  # 当前帧返回全0，避免崩溃
            # ================================================
            hue = hue - self.calibration_hue

        cell_size = self.cell_size
        h, w = hue.shape

        # 计算实际可以完整分割的行数和列数
        rows = h // cell_size
        cols = w // cell_size

        # 裁剪到可以完整分割的尺寸
        hue_cropped = hue[:rows * cell_size, :cols * cell_size]

        # 使用 reshape 和 mean 进行向量化的降采样
        # 将图像分成 cell_size x cell_size 的块，然后对每个块求均值
        # 方法：reshape 成 (rows, cell_size, cols, cell_size)，然后在第1和第3维度求均值
        hue_reshaped = hue_cropped.reshape(rows, cell_size, cols, cell_size)
        pressure_matrix = hue_reshaped.mean(axis=(1, 3))  # 对第1和第3维度求均值

        # 噪声过滤：如果平均色调小于1，认为是噪声，设为0
        pressure_matrix = np.where(pressure_matrix < 5, 0, pressure_matrix)

        # 如果输出尺寸小于 grid_rows x grid_cols，用0填充
        if pressure_matrix.shape[0] < self.grid_rows or pressure_matrix.shape[1] < self.grid_cols:
            padded = np.zeros((self.grid_rows, self.grid_cols), dtype=np.float32)
            padded[:pressure_matrix.shape[0], :pressure_matrix.shape[1]] = pressure_matrix
            pressure_matrix = padded
        # 如果输出尺寸大于 grid_rows x grid_cols，裁剪
        elif pressure_matrix.shape[0] > self.grid_rows or pressure_matrix.shape[1] > self.grid_cols:
            pressure_matrix = pressure_matrix[:self.grid_rows, :self.grid_cols]

        return pressure_matrix


    def get_flow_matrix(self, frame):
        """
        Compute tangential optical flow field between frames.
        Returns:
            flow_x (np.ndarray): X方向光流分量矩阵
            flow_y (np.ndarray): Y方向光流分量矩阵
        """
        # frame_gray = cv2.cvtColor(cv2.UMat(frame), cv2.COLOR_BGR2GRAY)
        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # 缩放加速
        scale = self.scale_factor
        prev_small = cv2.resize(self.first_frame_gray, None, fx=scale, fy=scale)
        curr_small = cv2.resize(frame_gray, None, fx=scale, fy=scale)

        params = self.params.copy()

        if self.last_flow is not None:
            # flow 合法，flag 保持原有
            # print("1")
            pass
        else:
            # print("2")
            self.last_flow = None
            # 去掉 USE_INITIAL_FLOW flag
            params['flags'] = params.get('flags', 0) & ~cv2.OPTFLOW_USE_INITIAL_FLOW

        # 计算光流
        flow_small = cv2.calcOpticalFlowFarneback(
            prev=prev_small,
            next=curr_small,
            flow=self.last_flow,
            **params)
        # ).get()

        self.last_flow = flow_small

        # 恢复到原图尺寸
        flow_full = cv2.resize(flow_small, (self.width, self.height))

        # 分离 x/y 分量
        flow_x = flow_full[..., 0]
        flow_y = flow_full[..., 1]
        # flow_x = flow_small[..., 0]
        # flow_y = flow_small[..., 1]

        # return flow_x, flow_y #, curr_small
        return flow_x, flow_y


    def visualize_pressure(self):
        """
        Visualize the pressure matrix on a black background (only integer labels).
        Args:
            pressure_matrix (np.ndarray): 来自 get_pressure_matrix() 的压力矩阵
        Returns:
            np.ndarray: 可显示的 BGR 图像（黑底 + 压力数值）
        """
        # 创建黑底图像
        frame_bgr = self.preprocessed_frame
        pressure_matrix = self.get_pressure_matrix(frame_bgr)
        height = self.grid_rows * self.cell_size
        width = self.grid_cols * self.cell_size
        vis_img = np.zeros((height, width, 3), dtype=np.uint8)

        for row in range(self.grid_rows):
            for col in range(self.grid_cols):
                y1, y2 = row * self.cell_size, (row + 1) * self.cell_size
                x1, x2 = col * self.cell_size, (col + 1) * self.cell_size
                cx, cy = (x1 + x2) // 2, (y1 + y2) // 2

                # 取整数显示（去掉小数点）
                pressure_value = int(pressure_matrix[row, col])

                # 绘制数字
                cv2.putText(
                    vis_img,
                    str(pressure_value),
                    (int(cx - 15), int(cy + 5)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.4,
                    (255, 255, 255),  # 白色字体
                    1
                )

        return vis_img


    def get_total_force(self, frame=None, pressure_matrix=None, flow_x=None, flow_y=None):
        """
        计算总力，支持两种调用方式：
        1. get_total_force(frame) - 传入frame，内部计算pressure_matrix和flow
        2. get_total_force(pressure_matrix=pm, flow_x=fx, flow_y=fy) - 直接使用已计算的数据

        Args:
            frame: 可选的输入帧
            pressure_matrix: 可选的已计算压力矩阵
            flow_x: 可选的已计算X方向光流
            flow_y: 可选的已计算Y方向光流

        Returns:
            tuple: (fx_total, fy_total, fz_total)
        """
        # 如果提供了已计算的数据，直接使用
        if pressure_matrix is not None and flow_x is not None and flow_y is not None:
            return self._calculate_total_force_from_data(pressure_matrix, flow_x, flow_y)

        # 如果没有提供frame，则读取新帧
        if frame is None:
            frame = self.preprocessed_frame
            # cv2.imshow('frame', frame)  # MODIFIED: 注释掉调试窗口，避免显示额外的frame界面

        # 计算压力矩阵和光流
        pressure_matrix = self.get_pressure_matrix(frame)
        flow_x, flow_y = self.get_flow_matrix(frame)

        return self._calculate_total_force_from_data(pressure_matrix, flow_x, flow_y)


    def _calculate_total_force_from_data(self, pressure_matrix, flow_x, flow_y):
        """
        从已计算的数据计算总力（内部方法）

        Args:
            pressure_matrix: 压力矩阵
            flow_x: X方向光流
            flow_y: Y方向光流

        Returns:
            tuple: (fx_total, fy_total, fz_total)
        """
        step = self.optical_flow_step
        h, w = flow_x.shape

        # 采样网格点
        grid_y, grid_x = np.mgrid[
                         step / 2:h:step,
                         step / 2:w:step
                         ].reshape(2, -1).astype(int)

        # 缩放显示
        sampled_fx = flow_x[grid_y, grid_x] * 4.5
        sampled_fy = flow_y[grid_y, grid_x] * 4.5

        # fx_total = np.sum(sampled_fx)
        # fy_total = np.sum(sampled_fy)
        # fz_total = np.sum(pressure_matrix)
        #
        # fx_total = fx_total * 0.1
        # fy_total = -fy_total * 0.1
        # fz_total = fz_total * 0.05
        fx_varient = np.std(sampled_fx)
        fy_varient = np.std(sampled_fy)
        fx_compensation = np.exp(0.3 - fx_varient) * sampled_fx
        fy_compensation = np.exp(0.3 - fy_varient) * sampled_fy

        # print(f"fx_varient: {fx_varient:.2f}\tfy_varient: {fy_varient:.2f}")
        # fx_total = np.sum(sampled_fx);    fy_total = np.sum(sampled_fy)
        fx_total = np.sum(sampled_fx - fx_compensation);
        fy_total = np.sum(sampled_fy - fy_compensation)
        fz_total = np.sum(pressure_matrix)
        fz_total = np.where(fz_total < 0, 0, fz_total)

        bias_judge = 10 * np.abs(fy_total) / np.abs(fy_varient - 0.2)
        # print("bias_judge: {:.2f}".format(bias_judge))
        # if (fy_varient < 0.4 and np.abs(fy_total) > 5):
        #     self.calibrate_base_matrix(5)

        # if (fx_varient < 0.4 and np.abs(fx_total) > 5):
        #     self.calibrate_base_matrix(5)

        fx_total = fx_total * self.fx_scale
        fy_total = -fy_total * self.fy_scale
        fz_total = fz_total * self.fz_scale
        return fx_total, fy_total, fz_total


    def get_force_angle2D(self, frame=None, flow_x=None, flow_y=None):
        if flow_x is None and flow_y is None:
            if frame is None:
                frame = self.preprocessed_frame
            flow_x, flow_y = self.get_flow_matrix(frame)
        step = self.optical_flow_step
        h, w = flow_x.shape

        # 采样网格点
        grid_y, grid_x = np.mgrid[
                         step / 2:h:step,
                         step / 2:w:step
                         ].reshape(2, -1).astype(int)

        # 缩放显示
        sampled_fx = flow_x[grid_y, grid_x] * 4.5
        sampled_fy = flow_y[grid_y, grid_x] * 4.5
        fx_varient = np.std(sampled_fx)
        fy_varient = np.std(sampled_fy)
        fx_compensation = np.exp(0.3 - fx_varient) * sampled_fx
        fy_compensation = np.exp(0.3 - fy_varient) * sampled_fy

        # print(f"fx_varient: {fx_varient:.2f}\tfy_varient: {fy_varient:.2f}")
        # fx_total = np.sum(sampled_fx);    fy_total = np.sum(sampled_fy)
        fx_total = np.sum(sampled_fx - fx_compensation);
        fy_total = np.sum(sampled_fy - fy_compensation)

        bias_judge = 10 * np.abs(fy_total) / np.abs(fy_varient - 0.2)
        # print("bias_judge: {:.2f}".format(bias_judge))
        if (fy_varient < 0.4 and np.abs(fy_total) > 5):
            self.calibrate_base_matrix(5)

        if (fx_varient < 0.4 and np.abs(fx_total) > 5):
            self.calibrate_base_matrix(5)

        fx_total = fx_total * 0.1
        fy_total = -fy_total * 0.1

        magnitude = math.sqrt(fx_total ** 2 + fy_total ** 2)

        angle_rad = math.atan2(fy_total, fx_total)
        angle_deg = math.degrees(angle_rad)
        # print(f"计算角度: {angle_deg:.2f}°")  # 注释掉调试打印
        return magnitude, angle_deg


    def get_force_angle3D(self, frame=None, fx_total=None, fy_total=None, fz_total=None):
        if fx_total is None and fy_total is None and fz_total is None:
            if frame is None:
                frame = self.preprocessed_frame
            fx_total, fy_total, fz_total = self.get_total_force(frame=frame)
        magnitude = math.sqrt(fx_total ** 2 + fy_total ** 2 + fz_total ** 2)

        # 计算方位角 (azimuth) - 在xy平面内与+x轴的夹角
        azimuth_rad = math.atan2(fy_total, fx_total)
        azimuth_deg = math.degrees(azimuth_rad)

        # 计算俯仰角 (elevation) - 与xy平面的夹角
        xy_magnitude = math.sqrt(fx_total ** 2 + fy_total ** 2)
        elevation_rad = math.atan2(fz_total, xy_magnitude)
        elevation_deg = math.degrees(elevation_rad)
        return magnitude, azimuth_deg, elevation_deg


    def get_cell_area(self, frame=None, pressure_matrix=None):
        if pressure_matrix is None:
            if frame is None:
                frame = self.preprocessed_frame
            pressure_matrix = self.get_pressure_matrix(frame)
        # 使用校准矩阵的平均值 + 5 作为动态阈值
        return len(pressure_matrix[pressure_matrix > self.pressure_threshold])


    def get_center_of_gravity(self, frame=None, pressure_matrix=None):
        if pressure_matrix is None:
            if frame is None:
                frame = self.preprocessed_frame
            pressure_matrix = self.get_pressure_matrix(frame)

        pressure_matrix = np.where(pressure_matrix < 0, 0, pressure_matrix)
        M = cv2.moments(pressure_matrix)

        # 计算质心
        if M['m00'] != 0:
            cx = M['m10'] / M['m00']
            cy = M['m01'] / M['m00']
            return cx, cy
        else:
            return -1, -1


    def get_maximum_force(self, frame=None, pressure_matrix=None):
        if pressure_matrix is None:
            if frame is None:
                frame = self.preprocessed_frame
            pressure_matrix = self.get_pressure_matrix(frame)
        max_index = np.argmax(pressure_matrix)
        max_row, max_col = np.unravel_index(max_index, pressure_matrix.shape)
        max_value = pressure_matrix[max_row, max_col]
        return max_value, max_row, max_col


    def get_pressure_histogram(self, pressure_matrix, bins=256):
        """
        将压力矩阵转换为固定长度的直方图统计数组
        Args:
            pressure_matrix: 压力矩阵（来自 get_pressure_matrix）
            bins: 直方图的区间数量，默认256

        Returns:
            np.ndarray: 长度为bins的数组，表示每个压力值区间的频次统计
        """
        pressure_values = pressure_matrix.flatten()
        hist, _ = np.histogram(pressure_values, bins=bins, range=(0, 255))
        return hist.astype(np.float32)


    def get_touch_status(self, frame=None, contact_threshold=None, release_threshold=None, slide_threshold=None):
        """
        检测触摸状态

        Args:
            frame: 可选的当前帧（不提供则自动读取）
            contact_threshold: 可选的接触阈值
            release_threshold: 可选的释放阈值
            slide_threshold: 可选的滑动阈值

        Returns:
            tuple: (当前状态, fx_total, fy_total, fz_total, ft)
        """
        # 更新阈值
        if contact_threshold is not None:
            self.contact_threshold = contact_threshold
        if release_threshold is not None:
            self.release_threshold = release_threshold
        if slide_threshold is not None:
            self.slide_threshold = slide_threshold

        # 获取力值
        fx_total, fy_total, fz_total = self.get_total_force(frame=frame)
        ft = math.sqrt(fx_total ** 2 + fy_total ** 2)
        self.fz_history.append(fz_total)
        fz_std = np.std(self.fz_history) if len(self.fz_history) > 1 else 0.0

        # 状态转换逻辑
        if self.current_status == "IDLE":
            if fz_total > self.contact_threshold:
                self.current_status = "CONTACT"

        elif self.current_status == "CONTACT":
            if (
                fz_total > self.contact_threshold
                and ft > self.slide_threshold
                and fz_std >= self.slide_force_std_threshold
            ):
                self.current_status = "SLIDING"
            elif fz_total < self.release_threshold:
                self.current_status = "RELEASED"

        elif self.current_status == "SLIDING":
            if (
                fz_total > self.contact_threshold
                and (ft <= self.slide_threshold or fz_std < self.slide_force_std_threshold)
            ):
                self.current_status = "CONTACT"
            elif fz_total < self.release_threshold:
                self.current_status = "RELEASED"

        elif self.current_status == "RELEASED":
            if fz_total >= self.contact_threshold:
                self.current_status = "CONTACT"
            elif fz_total <= self.release_threshold:
                self.current_status = "IDLE"
                fx_total = 0.0
                fy_total = 0.0
                fz_total = 0.0
                ft = 0.0

        return self.current_status, fx_total, fy_total, fz_total, ft, fz_std


    def get_contact_shape(self, pressure_matrix=None, threshold=None, min_area=15, ratio_threshold=2.5):
        """根据压力矩阵判定接触形状并返回mask与旋转矩形"""
        if pressure_matrix is None:
            frame = self.preprocessed_frame
            pressure_matrix = self.get_pressure_matrix(frame)
        if threshold is None:
            threshold = self.pressure_threshold

        mask = (pressure_matrix > threshold).astype(np.uint8) * 255
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return "UNKNOWN", mask, None

        largest = max(contours, key=cv2.contourArea)
        if cv2.contourArea(largest) < min_area:
            return "UNKNOWN", mask, None

        cxcy, wh, angle = cv2.minAreaRect(largest)
        w, h = wh
        if w == 0 or h == 0:
            return "UNKNOWN", mask, None

        ratio = (w / h) if w >= h else (h / w)
        label = "FACE" if ratio <= ratio_threshold else "EDGE"
        box = cv2.boxPoints((cxcy, wh, angle))
        box = box.astype(np.int32)
        return label, mask, box

    
    def get_tactile_rgb(self, pressure_matrix=None, flow_matrix=None, pressure_max=50, flow_max=10, flow_min=-10, target_size=None):
        """根据压力矩阵和光流矩阵生成触觉RGB图像。
        
        Args:
            pressure_matrix: 压力矩阵，若为None则从preprocessed_frame计算
            flow_matrix: 光流矩阵，若为None则从preprocessed_frame计算
            pressure_max: 压力最大值，用于归一化到255
            flow_max: 光流最大值，用于归一化到255
            flow_min: 光流最小值，用于归一化到255
            target_size: 目标输出尺寸 (width, height)，若为None则不进行resize
        """
        if pressure_matrix is None:
            frame = self.preprocessed_frame
            pressure_matrix = self.get_pressure_matrix(frame)
        if flow_matrix is None:
            flow_matrix = self.get_flow_matrix(self.preprocessed_frame)

        # get_flow_matrix 返回 (flow_x, flow_y) tuple；兼容旧的 HxWx2 数组输入
        if isinstance(flow_matrix, tuple):
            flow_x, flow_y = flow_matrix
        else:
            flow_x = flow_matrix[:, :, 0]
            flow_y = flow_matrix[:, :, 1]

        # 使用固定参数进行缩放，直接映射到 [0, 255]
        # 压力矩阵: [0, pressure_max] -> [0, 255]
        pressure_scaled = np.clip(pressure_matrix / pressure_max * 255, 0, 255)

        # 光流矩阵 X分量: [flow_min, flow_max] -> [0, 255]
        flow_x_scaled = np.clip((flow_x - flow_min) / (flow_max - flow_min) * 255, 0, 255)
        # 光流矩阵 Y分量: [flow_min, flow_max] -> [0, 255]
        flow_y_scaled = np.clip((flow_y - flow_min) / (flow_max - flow_min) * 255, 0, 255)

        # 将压力和光流信息映射到RGB通道
        tactile_rgb = np.zeros((pressure_matrix.shape[0], pressure_matrix.shape[1], 3), dtype=np.uint8)
        tactile_rgb[:, :, 0] = pressure_scaled.astype(np.uint8)  # Red channel
        tactile_rgb[:, :, 1] = flow_x_scaled.astype(np.uint8)  # Green channel
        tactile_rgb[:, :, 2] = flow_y_scaled.astype(np.uint8)  # Blue channel

        # 如果指定了目标尺寸，则resize到目标尺寸
        if target_size is not None:
            target_w, target_h = target_size
            if tactile_rgb.shape[1] != target_w or tactile_rgb.shape[0] != target_h:
                tactile_rgb = cv2.resize(tactile_rgb, (target_w, target_h), interpolation=cv2.INTER_LINEAR)

        return tactile_rgb


    def release(self):
        """Release camera resources"""
        if self.cap is not None:
            self.cap.release()


    '''
    def visualize_flow(self):
        """
            Visualize flow vectors on a black background.

            Returns:
                np.ndarray: BGR 图像，绘制了光流箭头
            """
        frame_bgr = self.preprocessed_frame
        flow_x, flow_y = self.get_flow_matrix(frame_bgr)

        step = self.optical_flow_step
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
        vector_vis = np.zeros((h, w, 3), dtype=np.uint8)

        # 绘制箭头
        for (x, y, dx, dy) in zip(grid_x, grid_y, sampled_fx, sampled_fy):
            end_point = (int(x + dx), int(y + dy))
            cv2.arrowedLine(vector_vis, (x, y), end_point, (255, 255, 255), 2, tipLength=0.3)
        return vector_vis
    '''


    '''
    def update_parameters(self, new_params):
        """更新传感器参数"""
        try:
            # 更新光流参数
            if 'optical_flow' in new_params:
                self.params.update(new_params['optical_flow'])

            # 更新网格参数
            if 'grid' in new_params:
                if 'cell_size' in new_params['grid']:
                    self.setCellSize(new_params['grid']['cell_size'])

            # 更新显示参数
            if 'display' in new_params:
                if 'scale_factor' in new_params['display']:
                    self.setScaleFactor(new_params['display']['scale_factor'])

            # 更新相机参数
            if 'camera' in new_params:
                # 过滤掉 width/height（不在动态参数中）
                camera_params = {k: v for k, v in new_params['camera'].items()
                            if k not in ['frame_width', 'frame_height']}
                if camera_params:  # 如果有动态参数
                    self.apply_camera_params(camera_params)
                    print("11111111111")

            print("传感器参数已更新")
            return True
        except Exception as e:
            print(f"更新传感器参数时出错: {e}")
            return False
    '''


    '''
    def print_settings_results(self, results):
        """Print camera settings application results"""
        print("\nID: {self.id} Camera Settings Results:")
        print("-" * 65)
        print(f"{'Property':<30} {'Target':<10} {'Actual':<10} {'Status':<5}")
        print("-" * 65)
        for prop_name, target, actual, status in results:
            print(f"{prop_name:<30} {target:<10.2f} {actual:<10.2f} {status:<5}")
    '''


    '''
    def auto_detect_roi(self, frame):
        """
        自动检测图像中的白斑并确定最佳ROI区域
        参数:
            frame: 摄像头原始输入图像
        返回:
            roi_coords: ROI坐标 (x1, y1, x2, y2)
        """
        hue_matrix = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)[:, :, 0]
        _, thresh = cv2.threshold(hue_matrix, 50, 255, cv2.THRESH_BINARY)
        kernel = np.ones((31, 31), np.uint8)
        thresh = cv2.dilate(thresh, kernel)

        x_val = np.sum(thresh, axis=0)
        y_val = np.sum(thresh, axis=1)

        h, w = thresh.shape

        x_left = x_right = x_mid = int(w / 2)
        y_top = y_bottom = y_mid = int(h / 2)

        loss_iter = (6400 + x_val[x_mid]) / 640.0
        for i in range(x_mid - 1, -1, -1):
            loss_ = (6400 + x_val[i]) / (abs(i - x_mid) + 640.0)
            if (loss_ < loss_iter):
                x_left = i
                loss_iter = loss_

        loss_iter = (6400 + x_val[x_mid]) / 640.0
        for i in range(x_mid + 1, w):
            loss_ = (6400 + x_val[i]) / (abs(i - x_mid) + 640.0)
            if (loss_ < loss_iter):
                x_right = i
                loss_iter = loss_

        loss_iter = (4800 + y_val[y_mid]) / 480.0
        for i in range(y_mid - 1, -1, -1):
            loss_ = (4800 + y_val[i]) / (abs(i - y_mid) + 480.0)
            if (loss_ < loss_iter):
                y_top = i
                loss_iter = loss_

        loss_iter = (4800 + y_val[y_mid]) / 480.0
        for i in range(y_mid + 1, h):
            loss_ = (4800 + y_val[i]) / (abs(i - y_mid) + 480.0)
            if (loss_ < loss_iter):
                y_bottom = i
                loss_iter = loss_

        return x_left, x_right, y_top, y_bottom
    '''


    '''
    def load_camera_settings(self, file_path):
        """Load camera settings from configuration file"""
        settings = {}
        try:
            with open(file_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and ':' in line:
                        key, value = line.split(':', 1)
                        key = key.strip()
                        value = value.strip()
                        if hasattr(cv2, key):
                            settings[getattr(cv2, key)] = float(value)
        except Exception as e:
            print(f"Runtime error loading configuration file: {e}")
        return settings
    '''


    '''
    def apply_camera_settings(self, settings):
        """Apply camera settings and return results"""
        if not self.cap:
            return []

        results = []
        for prop_id, target_value in settings.items():
            success = self.cap.set(prop_id, target_value)
            actual_value = self.cap.get(prop_id)
            status = "✓" if success else "✗"
            prop_name = [k for k, v in vars(cv2).items()
                         if v == prop_id and k.startswith('CAP_PROP')]
            prop_name = prop_name[0] if prop_name else f"ID_{prop_id}"
            results.append((prop_name, target_value, actual_value, status))
        return results
    '''


    '''
    def hue_to_pressure(self, avg_hue):
        """
        将色调值转换为压力值

        Args:
            avg_hue: float, 平均色调值（相对于校准基准的差值）

        Returns:
            float: 转换后的压力值
        """
        # 噪声过滤：如果平均色调小于1，认为是噪声，设为0
        avg_hue = 0 if avg_hue < 1 else avg_hue

        # 将色调值转换为压力值（通过经验缩放因子）
        # 系数 (370.0 / 90.0) * 1.17 ≈ 4.81
        pressure_value = avg_hue * (370.0 / 90.0) * 1.17

        return pressure_value
    '''



