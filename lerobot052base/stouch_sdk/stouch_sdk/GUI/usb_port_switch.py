import cv2
import sys
import os

# 确保可以从项目根目录导入 api 包
CUR_DIR = os.path.dirname(__file__)
ROOT_DIR = os.path.abspath(os.path.join(CUR_DIR, '..', '..'))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from api import TouchSensor


def usb_scan_and_switch(current_sensor, finger_id='sensor', max_port=10):
    """
    在 CLI 中进行一次性扫描与切换：
    1) 等待用户在终端输入 's' 并回车以触发扫描
    2) 扫描 0..max_port-1 范围内可用 USB 端口，打印列表
    3) 读取用户输入的端口号并尝试切换

    参数：
        current_sensor (TouchSensor | None): 当前传感器实例
        finger_id (str): 新实例的 finger_id 标识
        max_port (int): 扫描端口的上限（扫描 [0, max_port)）

    返回：
        TouchSensor: 切换成功则返回新实例；否则返回原实例
    """

    key = input("按 s 后回车开始扫描USB端口（按其他键回车取消）: ").strip().lower()
    if key != 's':
        print("未触发扫描，保持当前端口。")
        return current_sensor

    available = []
    for i in range(max_port):
        cap = cv2.VideoCapture(i)
        ok, _ = cap.read()
        if ok:
            available.append(i)
        cap.release()

    if not available:
        print("未发现可用的USB端口。")
        return current_sensor

    print("可用端口: " + ", ".join(map(str, available)))

    sel = input("请输入要切换的端口号: ").strip()
    if not sel.isdigit():
        print("输入非法（非数字），未切换。")
        return current_sensor

    sel_port = int(sel)
    if sel_port not in available:
        print(f"端口 {sel_port} 不在可用列表中，未切换。")
        return current_sensor

    try:
        if current_sensor is not None:
            current_sensor.release()
        new_sensor = TouchSensor(usb_id=sel_port, finger_id=finger_id)
        print(f"已切换到USB端口 {sel_port}")
        return new_sensor
    except Exception as e:
        print(f"切换失败: {e}，保持原端口。")
        return current_sensor


