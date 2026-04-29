import cv2
import os
import time

camera_ids = [7, 9, 17]
save_dir = "/home/stouching/Desktop/"
os.makedirs(save_dir, exist_ok=True)

caps = []
for cam_id in camera_ids:
    cap = cv2.VideoCapture(cam_id)
    if not cap.isOpened():
        print(f"错误: 无法打开摄像头 /dev/video{cam_id}")
        continue
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    caps.append((cam_id, cap))
    print(f"成功打开摄像头 /dev/video{cam_id}")

if not caps:
    exit(1)

print("开始采集，按 Ctrl+C 停止...")
frame_count = 0

try:
    for cam_id, cap in caps:
        ret, frame = cap.read()
        if ret:
            filename = f"{save_dir}/cam{cam_id}_{frame_count:04d}.jpg"
            cv2.imwrite(filename, frame)
            print(f"保存: {filename}")
        
        frame_count += 1
        time.sleep(0.5)  # 每0.5秒采集一次
            
except KeyboardInterrupt:
    print("\n停止采集")

for _, cap in caps:
    cap.release()
print(f"图片保存在: {save_dir}")