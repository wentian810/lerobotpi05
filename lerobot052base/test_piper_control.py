#!/usr/bin/env python3
"""
测试 Piper Leader 和 Follower 的基本通信和控制。
用于排查遥操作时从臂不动的问题。
"""

import time
import math

DEG_TO_RAD = math.pi / 180.0

def test_leader_reading():
    """测试 Leader 是否能正确读取关节/位姿数据。"""
    from piper_sdk import C_PiperInterface_V2, LogLevel

    print("=" * 60)
    print("测试 Leader 数据读取")
    print("=" * 60)

    piper = C_PiperInterface_V2(
        can_name="can_leader",
        judge_flag=False,
        can_auto_init=True,
        logger_level=LogLevel.WARNING,
    )
    piper.ConnectPort()
    time.sleep(0.5)

    # 读取 5 次关节数据
    print("\n--- 关节数据 (GetArmJointMsgs) ---")
    for i in range(5):
        joint_msgs = piper.GetArmJointMsgs()
        js = joint_msgs.joint_state
        joints = [js.joint_1, js.joint_2, js.joint_3, js.joint_4, js.joint_5, js.joint_6]
        print(f"  读取 {i+1}: {[j/1000.0 for j in joints]} deg")
        time.sleep(0.2)

    # 读取 5 次末端位姿
    print("\n--- 末端位姿 (GetArmEndPoseMsgs) ---")
    for i in range(5):
        pose_msgs = piper.GetArmEndPoseMsgs()
        ep = pose_msgs.end_pose
        print(f"  读取 {i+1}: X={ep.X_axis/1e6:.3f}m Y={ep.Y_axis/1e6:.3f}m Z={ep.Z_axis/1e6:.3f}m")
        time.sleep(0.2)

    # 读取夹爪
    print("\n--- 夹爪数据 (GetArmGripperMsgs) ---")
    for i in range(5):
        gripper_msgs = piper.GetArmGripperMsgs()
        g = gripper_msgs.gripper_state
        print(f"  读取 {i+1}: angle={g.grippers_angle/1e6:.4f}m effort={g.grippers_effort}")
        time.sleep(0.2)

    piper.DisconnectPort()
    print("\nLeader 测试完成")


def test_follower_moving():
    """测试 Follower 是否能被单独控制（关节空间）。"""
    from piper_sdk import C_PiperInterface_V2, LogLevel

    print("\n" + "=" * 60)
    print("测试 Follower 关节控制")
    print("=" * 60)

    piper = C_PiperInterface_V2(
        can_name="can_follower",
        judge_flag=False,
        can_auto_init=True,
        logger_level=LogLevel.WARNING,
    )
    piper.ConnectPort()

    # 使能
    print("\n使能电机...")
    timeout = 5.0
    start = time.time()
    while not piper.EnablePiper():
        if time.time() - start > timeout:
            print("ERROR: 使能超时！")
            piper.DisconnectPort()
            return
        time.sleep(0.01)
    print("电机已使能")

    # 读取当前位置
    joint_msgs = piper.GetArmJointMsgs()
    js = joint_msgs.joint_state
    current = [js.joint_1, js.joint_2, js.joint_3, js.joint_4, js.joint_5, js.joint_6]
    print(f"\n当前关节角度: {[c/1000.0 for c in current]} deg")

    # 小幅度运动测试：每个关节 +/- 5度
    delta = int(5 * 1000)  # 5度 = 5000 (0.001度单位)
    targets = [c + delta for c in current]

    print(f"\n发送目标关节角度: {[t/1000.0 for t in targets]} deg")
    piper.MotionCtrl_2(0x01, 0x01, 30, 0x00)
    time.sleep(0.05)
    piper.JointCtrl(*targets)
    time.sleep(2.0)

    # 读新位置
    joint_msgs = piper.GetArmJointMsgs()
    js = joint_msgs.joint_state
    new_pos = [js.joint_1, js.joint_2, js.joint_3, js.joint_4, js.joint_5, js.joint_6]
    print(f"运动后位置: {[n/1000.0 for n in new_pos]} deg")

    # 恢复原位
    print(f"\n恢复原位...")
    piper.JointCtrl(*current)
    time.sleep(2.0)

    piper.DisablePiper()
    piper.DisconnectPort()
    print("Follower 测试完成")


def test_leader_slave_mode():
    """检查 Leader 是否被设为主臂模式（导致无法读取反馈）。"""
    from piper_sdk import C_PiperInterface_V2, LogLevel

    print("\n" + "=" * 60)
    print("检查 Leader 主从模式状态")
    print("=" * 60)

    piper = C_PiperInterface_V2(
        can_name="can_leader",
        judge_flag=False,
        can_auto_init=True,
        logger_level=LogLevel.WARNING,
    )
    piper.ConnectPort()
    time.sleep(0.5)

    # 读取状态反馈
    status = piper.GetArmStatus()
    print(f"Leader 状态: {status}")

    # 尝试读取控制指令（如果是主臂，能读到自己发的控制指令）
    print("\n--- 尝试读取控制指令 (GetArmJointCtrl) ---")
    for i in range(5):
        ctrl = piper.GetArmJointCtrl()
        print(f"  JointCtrl: j1={ctrl.joint_ctrl.joint_1} j2={ctrl.joint_ctrl.joint_2} ...")
        time.sleep(0.2)

    piper.DisconnectPort()


if __name__ == "__main__":
    print("Piper 遥操作故障排查脚本")
    print("请确保 can_leader 和 can_follower 都已激活")
    print("=" * 60)

    try:
        test_leader_reading()
    except Exception as e:
        print(f"Leader 测试失败: {e}")

    try:
        test_follower_moving()
    except Exception as e:
        print(f"Follower 测试失败: {e}")

    try:
        test_leader_slave_mode()
    except Exception as e:
        print(f"主从模式检查失败: {e}")

    print("\n" + "=" * 60)
    print("排查建议:")
    print("  1. 如果 Leader 关节/位姿数据始终不变 → Leader 可能被设为主臂模式")
    print("  2. 如果 Follower 不运动 → CAN 接线或电机使能问题")
    print("  3. 如果 Follower 能动 → 问题在遥操作代码逻辑")
