import yaml
import os
from datetime import datetime
import cv2
import os
import sys

def resource_path(relative_path):
    """获取资源绝对路径（兼容开发和打包环境）"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base_path, relative_path)

class ParameterManager:
    """参数管理类，负责超参数的存储、加载、保存和应用"""
    
    def __init__(self, config_file=None):
        # 默认参数定义
        self.default_params = {
            'optical_flow': {
                'pyr_scale': 0.5,      # 金字塔缩放因子
                'levels': 4,            # 金字塔层数
                'winsize': 61,         # 窗口大小
                'iterations': 7,       # 迭代次数
                'poly_n': 7,           # 多项式邻域大小
                'poly_sigma': 1.1,      # 高斯标准差
                'flags': 4  # 光流计算标志
            },
            'grid': {
                'cell_size': 1,       # 网格单元大小
                'step': 35,            # 光流采样步长
                'pressure_scale': 4,   # 压力缩放系数
                'pressure_form_switch': 0.0  # 压力图显示模式（0=灰度，1=彩色，2=3D指尖视图，3=3D点云视图）
            },
            'roi': {
                'x1': 160,            # ROI左边界
                'x2': 540,            # ROI右边界
                'y1': 0,              # ROI上边界
                'y2': 430             # ROI下边界
            },
            'display': {
                'scale_factor': 0.5,   # 显示缩放因子
                'display_angle': 0     # 显示旋转角度（度）
            },
            'force_scale': {
                'fx_scale': 0.1,      # X方向力缩放系数
                'fy_scale': 0.1,      # Y方向力缩放系数
                'fz_scale': 0.05      # Z方向力缩放系数
            },
            'camera': {
                'hue': 0.0,
                'auto_exposure': 0.0,
                'exposure': -6.0,
                'contrast': 32.0,
                'auto_wb': 0.0,
                'white_balance_blue': 2800.0,
                'saturation': 64.0,
                'brightness': 0.0,
                'sharpness': 0.0,
                'gamma': 100
            }
        }
        
        # 当前参数（用户调整后的参数）
        self.current_params = self.default_params.copy()

        # 如果传入了路径就用传入的，否则用默认的路径
        if config_file:
            self.config_file = config_file
        else:
            self.config_file = "./Parameters.yaml"

    def load_config(self):
        """从YAML文件加载配置"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    yaml_data = yaml.safe_load(f)
                    # 从yaml格式转换为内部参数结构
                    loaded_params = self._yaml_to_params(yaml_data)
                    # 合并加载的参数，保持默认参数结构
                    self.current_params = self._merge_params(self.default_params, loaded_params)
                print("配置加载成功")
                return True
            else:
                print("配置文件不存在，使用默认参数")
                self.current_params = self.default_params.copy()
                return False
        except yaml.YAMLError as e:
            print(f"配置文件格式错误: {e}，使用默认参数")
            self.current_params = self.default_params.copy()
            return False
        except Exception as e:
            print(f"加载配置时出错: {e}，使用默认参数")
            self.current_params = self.default_params.copy()
            return False
    
    def save_config(self):
        """保存配置到YAML文件，保留原有注释"""
        try:
            # 读取原文件内容
            if not os.path.exists(self.config_file):
                print("配置文件不存在，无法保存")
                return False
            
            with open(self.config_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # 定义需要更新的参数映射（行前缀 -> 新值）
            params = self.current_params
            updates = {
                # 光流参数（带缩进）
                '  pyr_scale:': params['optical_flow']['pyr_scale'],
                '  levels:': params['optical_flow']['levels'],
                '  winsize:': params['optical_flow']['winsize'],
                '  iterations:': params['optical_flow']['iterations'],
                '  poly_n:': params['optical_flow']['poly_n'],
                '  poly_sigma:': params['optical_flow']['poly_sigma'],
                # 网格参数（无缩进）
                'cell_size:': params['grid']['cell_size'],
                'optical_flow_step:': params['grid']['step'],
                'pressure_scale:': params['grid']['pressure_scale'],
                'pressure_form_switch:': params['grid']['pressure_form_switch'],
                'display_angle:': params['display']['display_angle'],
                # 显示参数
                'scale_factor:': params['display']['scale_factor'],
            }
            
            # ROI参数（无缩进）
            if 'roi' in params:
                roi = params['roi']
                roi_updates = {
                    'roi_x1:': roi.get('x1', 160),
                    'roi_x2:': roi.get('x2', 540),
                    'roi_y1:': roi.get('y1', 0),
                    'roi_y2:': roi.get('y2', 430),
                }
                updates.update(roi_updates)
            
            # 3D压力图缩放系数（无缩进）
            if 'force_scale' in params:
                force = params['force_scale']
                force_updates = {
                    'fx_scale:': force.get('fx_scale', 0.1),
                    'fy_scale:': force.get('fy_scale', 0.1),
                    'fz_scale:': force.get('fz_scale', 0.05),
                }
                updates.update(force_updates)
            
            # 相机参数（带缩进，在camera_params下）
            if 'camera' in params:
                camera = params['camera']
                camera_updates = {
                    '  hue:': camera.get('hue', 0.0),
                    '  saturation:': camera.get('saturation', 64),
                    '  gamma:': camera.get('gamma', 500),
                    '  auto_exposure:': camera.get('auto_exposure', 0.0),
                    '  exposure:': camera.get('exposure', -5.0),
                    '  contrast:': camera.get('contrast', 50),
                    '  brightness:': camera.get('brightness', 5),
                    '  sharpness:': camera.get('sharpness', 100),
                    '  auto_wb:': camera.get('auto_wb', 0.0),
                    '  white_balance_blue:': camera.get('white_balance_blue', 4600),
                }
                updates.update(camera_updates)
            
            # 逐行处理，保留注释
            new_lines = []
            for line in lines:
                new_line = line
                for prefix, value in updates.items():
                    if line.strip().startswith(prefix.strip()):
                        # 提取注释部分
                        comment = ''
                        if '#' in line:
                            comment_idx = line.index('#')
                            comment = line[comment_idx:].rstrip('\n')
                        
                        # 构建新行：前缀 + 值 + 注释
                        indent = len(line) - len(line.lstrip())
                        key = prefix.strip().rstrip(':')
                        if comment:
                            # 计算注释对齐位置
                            new_line = f"{' ' * indent}{key}: {value}".ljust(20) + f" {comment}\n"
                        else:
                            new_line = f"{' ' * indent}{key}: {value}\n"
                        break
                new_lines.append(new_line)
            
            # 写回文件
            with open(self.config_file, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
            
            print("配置保存成功")
            return True
        except Exception as e:
            print(f"配置保存失败: {e}")
            return False
    
    def apply_to_sensor(self, sensor):
        """将参数应用到传感器对象"""
        try:
            # 更新光流参数（排除flags，保持sensor原有的cv2常量值）
            if hasattr(sensor, 'params'):
                sensor.params.update(self.current_params['optical_flow'])
            
            # 更新网格参数
            if hasattr(sensor, 'cell_size'):
                sensor.cell_size = self.current_params['grid']['cell_size']
                if hasattr(sensor, 'setCellSize') and sensor.width is not None and sensor.height is not None:
                    sensor.setCellSize(sensor.cell_size)

            # 更新光流采样步长
            if hasattr(sensor, 'optical_flow_step'):
                sensor.optical_flow_step = self.current_params['grid']['step']

            # 更新压力缩放系数
            if hasattr(sensor, 'pressure_scale'):
                sensor.pressure_scale = self.current_params['grid'].get('pressure_scale', 4)
            
            # 更新压力图显示模式
            if hasattr(sensor, 'pressure_form_switch'):
                sensor.pressure_form_switch = self.current_params['grid'].get('pressure_form_switch', 0.0)
            
            # 更新ROI参数
            if 'roi' in self.current_params and hasattr(sensor, 'setRoi'):
                roi = self.current_params['roi']
                old_roi = (sensor.roi_x1, sensor.roi_x2, sensor.roi_y1, sensor.roi_y2)
                new_roi = (roi['x1'], roi['x2'], roi['y1'], roi['y2'])
                
                sensor.setRoi(roi['x1'], roi['x2'], roi['y1'], roi['y2'])
                # ROI更新后需要重新计算网格尺寸
                if hasattr(sensor, 'setCellSize'):
                    sensor.setCellSize(sensor.cell_size)
                
                # 如果ROI发生变化，重置光流状态并重新校准
                if old_roi != new_roi:
                    sensor.last_flow = None  # 重置光流缓存
                    sensor.calibrate_base_matrix(5)  # 重新校准
                    print(f"ROI已更改: {old_roi} -> {new_roi}，已自动重新校准")
            
            # 更新显示参数
            if hasattr(sensor, 'scale_factor'):
                old_scale_factor = getattr(sensor, 'scale_factor', None)
                sensor.scale_factor = self.current_params['display']['scale_factor']
                if hasattr(sensor, 'setScaleFactor'):
                    sensor.setScaleFactor(sensor.scale_factor)
                if old_scale_factor is None or old_scale_factor != sensor.scale_factor:
                    sensor.last_flow = None
                    if hasattr(sensor, 'preprocessed_frame'):
                        try:
                            frame = sensor.preprocessed_frame
                            sensor.first_frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                        except Exception as e:
                            print(f"更新首帧灰度图失败: {e}")
            if hasattr(sensor, 'display_angle'):
                sensor.display_angle = self.current_params['display'].get('display_angle', 0)
            
            # 更新3D压力图缩放系数
            if 'force_scale' in self.current_params:
                force = self.current_params['force_scale']
                if hasattr(sensor, 'fx_scale'):
                    sensor.fx_scale = force.get('fx_scale', 0.1)
                if hasattr(sensor, 'fy_scale'):
                    sensor.fy_scale = force.get('fy_scale', 0.1)
                if hasattr(sensor, 'fz_scale'):
                    sensor.fz_scale = force.get('fz_scale', 0.05)
            
            # 更新相机参数
            if 'camera' in self.current_params:
                # 过滤掉 width/height（不在动态参数中）
                camera_params = {k: v for k, v in
                                self.current_params['camera'].items()
                                if k not in ['frame_width', 'frame_height']}
                if camera_params and hasattr(sensor, 'apply_camera_params'):
                    sensor.apply_camera_params(camera_params)
            
            # 更新全局变量（为了兼容现有代码）
            self._update_global_variables()
            sensor.calibrate_base_matrix(5)  # 应用参数后重新校准基线
            
            print("参数已应用到传感器")
            return True
        except Exception as e:
            print(f"应用参数时出错: {e}")
            return False
    
    def reset_to_default(self):
        """重置为默认参数"""
        self.current_params = self.default_params.copy()
        print("参数已重置为默认值")
    
    def get_parameter(self, category, key):
        """获取特定参数值"""
        try:
            return self.current_params[category][key]
        except KeyError:
            print(f"参数不存在: {category}.{key}")
            return None
    
    def set_parameter(self, category, key, value):
        """设置特定参数值"""
        try:
            if category not in self.current_params:
                self.current_params[category] = {}
            self.current_params[category][key] = value
            return True
        except Exception as e:
            print(f"设置参数时出错: {e}")
            return False
    
    def validate_parameters(self):
        """验证参数的有效性"""
        errors = []
        
        # 验证光流参数
        optical_flow = self.current_params['optical_flow']
        if not (0.1 <= optical_flow['pyr_scale'] <= 1.0):
            errors.append("pyr_scale 必须在 0.1-1.0 范围内")
        if not (1 <= optical_flow['levels'] <= 10):
            errors.append("levels 必须在 1-10 范围内")
        if not (5 <= optical_flow['winsize'] <= 150):
            errors.append("winsize 必须在 5-150 范围内")
        if not (1 <= optical_flow['iterations'] <= 10):
            errors.append("iterations 必须在 1-10 范围内")
        if not (1 <= optical_flow['poly_n'] <= 10):
            errors.append("poly_n 必须在 1-10 范围内")
        if not (0.5 <= optical_flow['poly_sigma'] <= 2.0):
            errors.append("poly_sigma 必须在 0.5-2.0 范围内")
        
        # 验证网格参数
        grid = self.current_params['grid']
        if not (1 <= grid['cell_size'] <= 50):
            errors.append("cell_size 必须在 1-50 范围内")
        if not (1 <= grid['step'] <= 100):
            errors.append("step 必须在 1-100 范围内")
        if not (1 <= grid.get('pressure_scale', 4) <= 20):
            errors.append("pressure_scale 必须在 1-20 范围内")
        
        # 验证显示参数
        display = self.current_params['display']
        if not (0.01 <= display['scale_factor'] <= 1.0):
            errors.append("scale_factor 必须在 0.01-1.0 范围内")
        if not (-180 <= display.get('display_angle', 0) <= 180):
            errors.append("display_angle 必须在 -180 到 180 范围内")
        
        # 验证ROI参数
        if 'roi' in self.current_params:
            roi = self.current_params['roi']
            if not (0 <= roi['x1'] < roi['x2'] <= 640):
                errors.append("ROI X坐标无效: 必须满足 0 <= x1 < x2 <= 640")
            if not (0 <= roi['y1'] < roi['y2'] <= 480):
                errors.append("ROI Y坐标无效: 必须满足 0 <= y1 < y2 <= 480")
        
        return errors
    
    def _merge_params(self, default_params, loaded_params):
        """合并参数，保持默认参数结构"""
        import copy
        merged = copy.deepcopy(default_params)
        
        for category, params in loaded_params.items():
            if category in merged and isinstance(params, dict):
                for key, value in params.items():
                    if key in merged[category]:
                        merged[category][key] = value
            elif category not in merged and isinstance(params, dict):
                # 支持新增的参数类别（如roi）
                merged[category] = params.copy()
        
        return merged
    
    def _yaml_to_params(self, yaml_data):
        """将YAML数据转换为内部参数结构"""
        params = {
            'optical_flow': {},
            'grid': {},
            'display': {},
            'camera': {}
        }
        
        # 光流参数 (从yaml的params字段读取)
        if 'params' in yaml_data and isinstance(yaml_data['params'], dict):
            yaml_params = yaml_data['params']
            params['optical_flow'] = {
                'pyr_scale': yaml_params.get('pyr_scale', 0.5),
                'levels': yaml_params.get('levels', 4),
                'winsize': yaml_params.get('winsize', 61),
                'iterations': yaml_params.get('iterations', 7),
                'poly_n': yaml_params.get('poly_n', 7),
                'poly_sigma': yaml_params.get('poly_sigma', 1.1)
            }
        
        # 网格参数
        params['grid'] = {
            'cell_size': yaml_data.get('cell_size', 1),
            'step': yaml_data.get('optical_flow_step', 35),
            'pressure_scale': yaml_data.get('pressure_scale', 4),
            'pressure_form_switch': yaml_data.get('pressure_form_switch', 0.0)
        }
        
        # 显示参数
        params['display'] = {
            'scale_factor': yaml_data.get('scale_factor', 0.5),
            'display_angle': yaml_data.get('display_angle', 0)
        }
        
        # ROI参数
        params['roi'] = {
            'x1': yaml_data.get('roi_x1', 160),
            'x2': yaml_data.get('roi_x2', 540),
            'y1': yaml_data.get('roi_y1', 0),
            'y2': yaml_data.get('roi_y2', 430)
        }
        
        # 3D压力图缩放系数
        params['force_scale'] = {
            'fx_scale': yaml_data.get('fx_scale', 0.1),
            'fy_scale': yaml_data.get('fy_scale', 0.1),
            'fz_scale': yaml_data.get('fz_scale', 0.05)
        }
        
        # 相机参数
        if 'camera_params' in yaml_data and isinstance(yaml_data['camera_params'], dict):
            params['camera'] = yaml_data['camera_params'].copy()
        
        return params
    
    def _update_global_variables(self):
        """更新全局变量（为了兼容现有代码）"""
        try:
            # 导入全局变量
            import sys
            current_module = sys.modules[__name__]
            
            # 更新全局变量
            if hasattr(current_module, 'params'):
                current_module.params.update(self.current_params['optical_flow'])
            if hasattr(current_module, 'CELL_SIZE'):
                current_module.CELL_SIZE = self.current_params['grid']['cell_size']
        except Exception as e:
            print(f"更新全局变量时出错: {e}")
    
    def get_all_parameters(self):
        """获取所有当前参数"""
        return self.current_params.copy()
    
    def set_all_parameters(self, params):
        """设置所有参数"""
        try:
            self.current_params = params.copy()
            return True
        except Exception as e:
            print(f"设置所有参数时出错: {e}")
            return False
