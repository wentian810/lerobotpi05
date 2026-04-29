import cv2
import numpy as np
from typing import List, Dict, Optional, Tuple
import time

class PortInfo:
    """端口信息类"""
    
    def __init__(self, port: int, cap=None):
        self.port = port
        self.cap = cap
        self.name = f"USB端口{port}"
        self.resolution = (0, 0)
        self.fps = 0.0
        self.status = "未知"
        self.is_available = False
        self.last_test_time = None
        
        if cap and cap.isOpened():
            self._get_port_info()
    
    def _get_port_info(self):
        """获取端口详细信息"""
        try:
            if self.cap and self.cap.isOpened():
                # 获取分辨率
                width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                self.resolution = (width, height)
                
                # 获取帧率
                self.fps = self.cap.get(cv2.CAP_PROP_FPS)
                
                # 测试连接
                ret, frame = self.cap.read()
                if ret and frame is not None:
                    self.status = "已连接"
                    self.is_available = True
                else:
                    self.status = "连接失败"
                    self.is_available = False
            else:
                self.status = "无法打开"
                self.is_available = False
        except Exception as e:
            self.status = f"错误: {str(e)}"
            self.is_available = False
    
    def test_connection(self) -> Tuple[bool, str]:
        """测试端口连接"""
        try:
            if not self.cap or not self.cap.isOpened():
                return False, "端口未打开"
            
            # 测试连续帧
            success_count = 0
            for i in range(3):  # 测试3帧
                ret, frame = self.cap.read()
                if ret and frame is not None and frame.size > 0:
                    success_count += 1
                else:
                    break
                time.sleep(0.1)  # 短暂延迟
            
            if success_count >= 2:  # 至少2帧成功
                self.status = "连接正常"
                self.is_available = True
                self.last_test_time = time.time()
                return True, "连接测试成功"
            else:
                self.status = "连接不稳定"
                self.is_available = False
                return False, "视频流不稳定"
                
        except Exception as e:
            self.status = f"测试错误: {str(e)}"
            self.is_available = False
            return False, f"测试失败: {str(e)}"
    
    def get_info_string(self) -> str:
        """获取端口信息字符串"""
        if self.is_available:
            return f"{self.name} - {self.resolution[0]}x{self.resolution[1]} - {self.fps:.1f}fps - {self.status}"
        else:
            return f"{self.name} - {self.status}"
    
    def release(self):
        """释放端口资源"""
        if self.cap:
            self.cap.release()
            self.cap = None

class USBPortScanner:
    """USB端口扫描类"""
    
    def __init__(self, scan_range: Tuple[int, int] = (0, 10)): #默认扫描范围0-9，可更改范围
        self.scan_range = scan_range
        self.available_ports: List[PortInfo] = []
        self.scan_timeout = 2.0  # 每个端口扫描超时时间
    
    def scan_available_ports(self) -> List[PortInfo]:
        """扫描所有可用的USB摄像头端口"""
        print("开始扫描USB端口...")
        self.available_ports = []
        
        for port in range(self.scan_range[0], self.scan_range[1] + 1):
            print(f"扫描端口 {port}...")
            port_info = self._scan_single_port(port)
            if port_info:
                self.available_ports.append(port_info)
                print(f"端口 {port} 可用: {port_info.get_info_string()}")
            else:
                print(f"端口 {port} 不可用")
        
        print(f"扫描完成，找到 {len(self.available_ports)} 个可用端口")
        return self.available_ports
    
    def _scan_single_port(self, port: int) -> Optional[PortInfo]:
        """扫描单个端口"""
        try:
            # 尝试打开端口
            cap = cv2.VideoCapture(port)
            if not cap.isOpened():
                cap.release()
                return None
            
            # 创建端口信息对象
            port_info = PortInfo(port, cap)
            
            # 测试连接
            success, message = port_info.test_connection()
            if success:
                return port_info
            else:
                port_info.release()
                return None
                
        except Exception as e:
            print(f"扫描端口 {port} 时出错: {e}")
            return None
    
    def get_port_by_number(self, port: int) -> Optional[PortInfo]:
        """根据端口号获取端口信息"""
        for port_info in self.available_ports:
            if port_info.port == port:
                return port_info
        return None
    
    def get_available_port_numbers(self) -> List[int]:
        """获取所有可用端口号"""
        return [port_info.port for port_info in self.available_ports]
    
    def refresh_port(self, port: int) -> bool:
        """刷新指定端口"""
        try:
            # 释放现有连接
            existing_port = self.get_port_by_number(port)
            if existing_port:
                existing_port.release()
                self.available_ports.remove(existing_port)
            
            # 重新扫描
            new_port = self._scan_single_port(port)
            if new_port:
                self.available_ports.append(new_port)
                return True
            return False
        except Exception as e:
            print(f"刷新端口 {port} 时出错: {e}")
            return False
    
    def release_all_ports(self):
        """释放所有端口资源"""
        for port_info in self.available_ports:
            port_info.release()
        self.available_ports = []
    
    def get_port_statistics(self) -> Dict:
        """获取端口统计信息"""
        total_ports = self.scan_range[1] - self.scan_range[0] + 1
        available_count = len(self.available_ports)
        
        return {
            'total_ports': total_ports,
            'available_ports': available_count,
            'scan_range': self.scan_range,
            'ports': [
                {
                    'port': p.port,
                    'name': p.name,
                    'resolution': p.resolution,
                    'fps': p.fps,
                    'status': p.status,
                    'is_available': p.is_available
                }
                for p in self.available_ports
            ]
        }
    
    def find_best_port(self) -> Optional[PortInfo]:
        """找到最佳端口（基于分辨率和帧率）"""
        if not self.available_ports:
            return None
        
        # 按分辨率和帧率排序
        def port_score(port_info):
            if not port_info.is_available:
                return 0
            
            # 分辨率分数（更高分辨率更好）
            resolution_score = port_info.resolution[0] * port_info.resolution[1]
            
            # 帧率分数
            fps_score = port_info.fps
            
            # 综合分数
            return resolution_score * 0.7 + fps_score * 1000 * 0.3
        
        best_port = max(self.available_ports, key=port_score)
        return best_port if best_port.is_available else None
    
    def validate_port(self, port: int) -> Tuple[bool, str]:
        """验证端口是否可用"""
        port_info = self.get_port_by_number(port)
        if not port_info:
            return False, f"端口 {port} 不在可用列表中"
        
        if not port_info.is_available:
            return False, f"端口 {port} 当前不可用"
        
        # 重新测试连接
        success, message = port_info.test_connection()
        return success, message
