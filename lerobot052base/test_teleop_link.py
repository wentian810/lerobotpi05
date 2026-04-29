#!/usr/bin/env python3
"""
最小化测试LeRobot Piper遥操作链路
直接测试 PiperLeader.get_action() -> PiperFollower.send_action()
"""
import time
import sys
sys.path.insert(0, '/home/stouching/vla/repo/lerobot052base/src')

from lerobot.teleoperators.piper_leader.piper_leader import PiperLeader
from lerobot.teleoperators.piper_leader.config_piper_leader import PiperLeaderConfig
from lerobot.robots.piper_follower.piper_follower import PiperFollower
from lerobot.robots.piper_follower.config_piper_follower import PiperFollowerConfig

# 创建Leader和Follower（无相机，避免相机连接问题）
leader = PiperLeader(PiperLeaderConfig(can_port="can_leader", manual_control=True))
follower = PiperFollower(PiperFollowerConfig(can_port="can_follower", auto_enable=True, cameras={}))

print("连接Leader...")
leader.connect()
print(f"Leader connected: {leader.is_connected}")

print("\n连接Follower...")
follower.connect()
print(f"Follower connected: {follower.is_connected}")

print("\n" + "="*60)
print("测试1: 读取Leader当前位置")
print("="*60)
action = leader.get_action()
print(f"Leader action keys: {list(action.keys())}")
for k, v in action.items():
    print(f"  {k}: {v:.6f}")

print("\n" + "="*60)
print("测试2: 发送相同位置给Follower（应该基本不动）")
print("="*60)
sent = follower.send_action(action)
print(f"Sent action keys: {list(sent.keys())}")
for k, v in sent.items():
    print(f"  {k}: {v:.6f}")

# 读取Follower当前位置
obs = follower.get_observation()
print(f"\nFollower observation keys: {[k for k in obs.keys() if 'pos' in k]}")
for k, v in obs.items():
    if 'pos' in k:
        print(f"  {k}: {v:.6f}")

print("\n" + "="*60)
print("测试3: 连续控制10秒（请手动移动主臂）")
print("="*60)
start = time.time()
count = 0
while time.time() - start < 10:
    act = leader.get_action()
    
    # 每1秒打印一次
    if count % 30 == 0:
        j1 = act.get('joint_1.pos', 0)
        g = act.get('gripper.pos', 0)
        print(f"  t={time.time()-start:.1f}s | j1={j1:.4f} rad | gripper={g:.4f} m")
    
    follower.send_action(act)
    time.sleep(0.033)  # ~30fps
    count += 1

print("\n测试完成")
leader.disconnect()
follower.disconnect()
