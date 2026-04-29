#!/usr/bin/env python3
"""
测试Follower是否响应LeRobot的控制指令
直接发送缓慢变化的正弦波目标位置
"""
import time
import math
import sys
sys.path.insert(0, '/home/stouching/vla/repo/lerobot052base/src')

from lerobot.robots.piper_follower.piper_follower import PiperFollower
from lerobot.robots.piper_follower.config_piper_follower import PiperFollowerConfig

print("测试Follower是否响应控制指令")
follower = PiperFollower(PiperFollowerConfig(can_port="can_follower", auto_enable=True, cameras={}))

print("连接Follower...")
follower.connect()
print(f"Follower connected: {follower.is_connected}")

# 读取初始位置
obs = follower.get_observation()
initial_joints = [obs[f"joint_{i}.pos"] for i in range(1, 7)]
print(f"\n初始关节位置(deg): {[j*180/math.pi for j in initial_joints]}")

print("\n发送正弦波运动指令到joint_1，持续5秒...")
start = time.time()
while time.time() - start < 5:
    t = time.time() - start
    # joint_1 做 +/- 10度 的正弦运动
    delta_rad = 10 * math.pi / 180 * math.sin(2 * math.pi * 0.5 * t)  # 0.5Hz
    
    action = {}
    for i in range(1, 7):
        key = f"joint_{i}.pos"
        if i == 1:
            action[key] = initial_joints[i-1] + delta_rad
        else:
            action[key] = initial_joints[i-1]
    action["gripper.pos"] = 0.05
    
    follower.send_action(action)
    
    if int(t * 10) % 5 == 0:  # 每0.5秒打印一次
        obs = follower.get_observation()
        current_j1_deg = obs["joint_1.pos"] * 180 / math.pi
        target_j1_deg = action["joint_1.pos"] * 180 / math.pi
        print(f"  t={t:.1f}s | target_j1={target_j1_deg:7.2f}deg | actual_j1={current_j1_deg:7.2f}deg | delta={current_j1_deg - initial_joints[0]*180/math.pi:+.2f}deg")
    
    time.sleep(0.033)

print("\n恢复初始位置...")
for i in range(1, 7):
    action[f"joint_{i}.pos"] = initial_joints[i-1]
action["gripper.pos"] = 0.05
for _ in range(30):  # 发送1秒
    follower.send_action(action)
    time.sleep(0.033)

follower.disconnect()
print("测试完成。如果actual_j1跟随target_j1变化，说明Follower控制正常。")
