#!/usr/bin/env python3
"""
测试PiperLeader位置读取是否实时更新
"""
import time
import sys
sys.path.insert(0, '/home/stouching/vla/repo/lerobot052base/src')

from piper_sdk import C_PiperInterface_V2, LogLevel

print("直接通过Piper SDK读取Leader关节位置（请手动移动主臂）")
piper = C_PiperInterface_V2(
    can_name="can_leader",
    judge_flag=False,
    can_auto_init=True,
    logger_level=LogLevel.WARNING,
)
piper.ConnectPort()

# 先禁用电机（如果之前有力矩）
piper.DisablePiper()

print("读取30次关节数据，间隔100ms...")
for i in range(30):
    joint_msgs = piper.GetArmJointMsgs()
    js = joint_msgs.joint_state
    joints = [js.joint_1, js.joint_2, js.joint_3, js.joint_4, js.joint_5, js.joint_6]
    angles_deg = [j/1000.0 for j in joints]
    
    # 计算与上一次的差值
    if i > 0:
        delta = [angles_deg[j] - prev_angles_deg[j] for j in range(6)]
        max_delta = max(abs(d) for d in delta)
        status = "MOVED!" if max_delta > 0.1 else ""
        print(f"  [{i:2d}] j1={angles_deg[0]:8.3f} j2={angles_deg[1]:8.3f} j3={angles_deg[2]:8.3f} "
              f"j4={angles_deg[3]:8.3f} j5={angles_deg[4]:8.3f} j6={angles_deg[5]:8.3f} "
              f"max_delta={max_delta:.3f} {status}")
    else:
        print(f"  [{i:2d}] j1={angles_deg[0]:8.3f} j2={angles_deg[1]:8.3f} j3={angles_deg[2]:8.3f} "
              f"j4={angles_deg[3]:8.3f} j5={angles_deg[4]:8.3f} j6={angles_deg[5]:8.3f}")
    
    prev_angles_deg = angles_deg
    time.sleep(0.1)

piper.DisconnectPort()
print("\n测试完成。如果有MOVED标记，说明读数是实时更新的。")
