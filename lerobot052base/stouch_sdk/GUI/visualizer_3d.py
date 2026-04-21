import cv2
import numpy as np
import pyqtgraph as pg
import pyqtgraph.opengl as gl


class Finger3DVisualizer(gl.GLViewWidget):
    """
    3D手指点云可视化器 - 使用胶囊体形状（带穹顶的半圆柱）
    
    几何模型：
    - 指腹部分(v < dome_ratio)：标准半圆柱
    - 指尖部分(v >= dome_ratio)：逐渐收拢的球形穹顶
    
    坐标系：
    - X: 横向（左右）
    - Y: 纵向（指根→指尖）
    - Z: 深度（朝向观察者）
    """
    def __init__(self, rows, cols, radius=None, y_scale=1, point_size=4, 
                 dome_ratio=0, parent=None):
        """
        Args:
            rows: 压力矩阵行数（纵向）
            cols: 压力矩阵列数（横向）
            radius: 半圆柱半径，默认为 cols/2
            y_scale: Y方向缩放因子
            point_size: 点云大小
            dome_ratio: 穹顶起始位置 (0-1)，默认0.4表示最后40%为穹顶
        """
        super().__init__(parent=parent)
        self.rows = int(rows)
        self.cols = int(cols)
        self.radius = float(radius) if radius is not None else max(1.0, self.cols / 2.0)
        self.y_scale = float(y_scale)
        self.point_size = int(point_size)
        self.dome_ratio = float(dome_ratio)

        self.setBackgroundColor('k')

        self._pos = self._build_positions()
        self._surface_grid = self._pos.reshape(self.rows, self.cols, 3).copy()
        self._scatter = gl.GLScatterPlotItem(
            pos=self._pos,
            size=self.point_size,
            pxMode=True
        )
        self.addItem(self._scatter)

        # 相机居中于胶囊体中心，俯视角度
        center_x = -(self.rows - 1) * self.y_scale / 2.0
        self.opts['center'] = pg.Vector(center_x, 0, 0)
        self.setCameraPosition(distance=self.radius * 4.0, elevation=90, azimuth=0)

        # 构建JET颜色查找表
        ramp = np.arange(256, dtype=np.uint8).reshape(-1, 1)
        jet_bgr = cv2.applyColorMap(ramp, cv2.COLORMAP_JET)
        jet_rgb = cv2.cvtColor(jet_bgr, cv2.COLOR_BGR2RGB).reshape(256, 3)
        alpha = np.full((256, 1), 255, dtype=np.uint8)
        self.lut = np.concatenate((jet_rgb, alpha), axis=1)

        # 光流采样驱动点云的缓存
        # 这些缓存确保在 step/分辨率不变时不重复重建采样点。
        self._flow_grid_x = None
        self._flow_grid_y = None
        self._flow_h = None
        self._flow_w = None
        self._flow_step = None
        self._sample_rows = None
        self._sample_cols = None
        self._base_sample_pos = None

        self._longitudinal_scale = 1.0
        self._lateral_scale = 1.0
        self._init_motion_scales()

    def _build_positions(self):
        """
        构建胶囊体形状的3D坐标：
        - 指腹区域：标准半圆柱
        - 指尖区域：球形穹顶，半径逐渐收拢，同时Z向上凸起
        - 最后进行镜像+旋转90度变换
        """
        R = self.radius
        positions = np.zeros((self.rows * self.cols, 3), dtype=np.float32)
        
        # 横向角度分布
        theta = np.linspace(-np.pi / 2.0, np.pi / 2.0, self.cols)
        
        # 穹顶部分的基准Z偏移（使穹顶平滑过渡）
        dome_base_y = self.dome_ratio * (self.rows - 1) * self.y_scale
        
        for row in range(self.rows):
            v = row / max(1, self.rows - 1)  # 归一化位置 [0, 1]
            y_base = v * (self.rows - 1) * self.y_scale
            
            if v < self.dome_ratio:
                # 指腹区域：标准半圆柱
                local_radius = R
                y = y_base
            else:
                # 指尖穹顶区域 - 真正的半球，与半圆柱相切
                t = (v - self.dome_ratio) / (1.0 - self.dome_ratio)  # [0, 1]
                phi = t * np.pi / 2.0  # 仰角从0到π/2
                local_radius = R * np.cos(phi)  # 纬度圈半径
                y = dome_base_y + R * np.sin(phi)  # 沿Y方向延伸
                y = y * 1.5  # 穹顶部分适当拉伸，增强视觉效果
            
            # 计算这一行所有点的坐标
            x = local_radius * np.sin(theta)
            z = local_radius * np.cos(theta)
            
            start_idx = row * self.cols
            end_idx = start_idx + self.cols
            positions[start_idx:end_idx, 0] = x
            positions[start_idx:end_idx, 1] = y
            positions[start_idx:end_idx, 2] = z
        
        # 变换：先镜像+旋转90度，再整体旋转180度
        # 组合：new_x = -old_y, new_y = old_x
        old_x = positions[:, 0].copy()
        old_y = positions[:, 1].copy()
        positions[:, 0] = -old_y  # new_x = -old_y
        positions[:, 1] = old_x   # new_y = old_x
        
        return positions

    def _init_motion_scales(self):
        # 将“像素级光流”换算到“胶囊曲面坐标”时使用的经验比例。
        x_extent = float(self._surface_grid[..., 0].max() - self._surface_grid[..., 0].min())
        y_extent = float(self._surface_grid[..., 1].max() - self._surface_grid[..., 1].min())
        self._longitudinal_scale = x_extent / max(1.0, float(self.rows - 1))
        self._lateral_scale = y_extent / max(1.0, float(self.cols - 1))

    def _ensure_flow_sampling(self, flow_shape, flow_step):
        flow_h, flow_w = int(flow_shape[0]), int(flow_shape[1])
        step = max(1, int(flow_step))
        rebuild = (
            self._flow_grid_x is None
            or self._flow_h != flow_h
            or self._flow_w != flow_w
            or self._flow_step != step
        )
        if not rebuild:
            return

        # 与2D光流显示使用同一采样公式，确保两个视图点位一一对应。
        grid_y, grid_x = np.mgrid[
            step / 2:flow_h:step,
            step / 2:flow_w:step
        ].reshape(2, -1).astype(np.int32)

        if grid_x.size == 0:
            self._flow_grid_x = np.array([flow_w // 2], dtype=np.int32)
            self._flow_grid_y = np.array([flow_h // 2], dtype=np.int32)
        else:
            self._flow_grid_x = np.clip(grid_x, 0, max(0, flow_w - 1))
            self._flow_grid_y = np.clip(grid_y, 0, max(0, flow_h - 1))

        self._flow_h = flow_h
        self._flow_w = flow_w
        self._flow_step = step
        self._rebuild_base_sample_positions()

    def _rebuild_base_sample_positions(self):
        # 把光流像素坐标映射到压力网格索引，再取对应胶囊曲面点作为基准点位。
        row_idx = np.rint(
            self._flow_grid_y.astype(np.float32) * (self.rows - 1) / max(1, self._flow_h - 1)
        ).astype(np.int32)
        col_idx = np.rint(
            self._flow_grid_x.astype(np.float32) * (self.cols - 1) / max(1, self._flow_w - 1)
        ).astype(np.int32)
        row_idx = np.clip(row_idx, 0, self.rows - 1)
        col_idx = np.clip(col_idx, 0, self.cols - 1)

        self._sample_rows = row_idx
        self._sample_cols = col_idx
        self._base_sample_pos = self._surface_grid[row_idx, col_idx].copy()
        self._scatter.setData(pos=self._base_sample_pos)

    # def update_pressure(self, pressure_matrix):
    #     if pressure_matrix is None:
    #         return

    #     if pressure_matrix.shape != (self.rows, self.cols):
    #         pressure_matrix = cv2.resize(
    #             pressure_matrix,
    #             (self.cols, self.rows),
    #             interpolation=cv2.INTER_NEAREST
    #         )

    #     # 旋转180度
    #     # pressure_matrix = np.rot90(pressure_matrix, 2)
    #     pressure_matrix = np.flip(pressure_matrix, axis=0)

    #     values = np.clip(pressure_matrix, 0, 255).astype(np.uint8).ravel()
    #     colors = self.lut[values]

    #     if colors.shape[1] == 3:
    #         alpha = np.full((colors.shape[0], 1), 255, dtype=colors.dtype)
    #         colors = np.concatenate((colors, alpha), axis=1)

    #     colors = colors.astype(np.float32) / 255.0
    #     self._scatter.setData(color=colors)

    def update_with_flow(self, pressure_matrix, flow_x, flow_y, flow_step=5, flow_disp_scale=0.1):
        if pressure_matrix is None or flow_x is None or flow_y is None:
            return

        self._ensure_flow_sampling(flow_x.shape, flow_step)
        if self._base_sample_pos is None:
            return

        pressure_for_color = pressure_matrix
        if pressure_for_color.shape != (self.rows, self.cols):
            pressure_for_color = cv2.resize(
                pressure_for_color,
                (self.cols, self.rows),
                interpolation=cv2.INTER_NEAREST
            )
        pressure_for_color = np.flip(pressure_for_color, axis=0)
        pressure_u8 = np.clip(pressure_for_color, 0, 255).astype(np.uint8)
        # 每个采样点的颜色由其映射到的压力网格单元决定。
        values = pressure_u8[self._sample_rows, self._sample_cols]
        colors = self.lut[values].astype(np.float32) / 255.0

        sampled_fx = flow_x[self._flow_grid_y, self._flow_grid_x].astype(np.float32)
        sampled_fy = flow_y[self._flow_grid_y, self._flow_grid_x].astype(np.float32)

        # 2D光流(dx, dy) -> 3D局部切向位移：
        # 胶囊几何中 longitudinal 对应 x，lateral 对应 y。
        disp_x = -sampled_fy * self._longitudinal_scale * float(flow_disp_scale)
        disp_y = sampled_fx * self._lateral_scale * float(flow_disp_scale)
        # disp_x = -sampled_fy * self._longitudinal_scale * 0.1
        # disp_y = sampled_fx * self._lateral_scale * 0.1
        displaced = self._base_sample_pos.copy()
        displaced[:, 0] += disp_x
        displaced[:, 1] += disp_y

        self._scatter.setData(pos=displaced, color=colors)
