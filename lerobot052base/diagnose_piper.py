#!/usr/bin/env python3
"""排查 Piper 主从臂遥操作问题"""
import time
from piper_sdk import C_PiperInterface_V2, LogLevel

def check_arm(name, can_port):
    print(f"\n{'='*60}")
    print(f"检查 {name} ({can_port})")
    print('='*60)
    
    piper = C_PiperInterface_V2(
        can_name=can_port,
        judge_flag=False,
        can_auto_init=True,
        logger_level=LogLevel.WARNING,
    )
    piper.ConnectPort()
    time.sleep(0.5)
    
    # 1. 检查是否能读取关节数据
    print(f"\n[1] 读取关节反馈 (GetArmJointMsgs):")
    joint_msgs = piper.GetArmJointMsgs()
    js = joint_msgs.joint_state
    joints = [js.joint_1, js.joint_2, js.joint_3, js.joint_4, js.joint_5, js.joint_6]
    print(f"    当前关节: {joints}")
    if all(j == 0 for j in joints):
        print("    ⚠️ 警告: 所有关节读数为0！可能处于主臂模式或连接异常")
    else:
        print(f"    关节角度(deg): {[j/1000 for j in joints]}")
    
    # 2. 检查末端位姿
    print(f"\n[2] 读取末端位姿 (GetArmEndPoseMsgs):")
    pose = piper.GetArmEndPoseMsgs().end_pose
    print(f"    X={pose.X_axis} Y={pose.Y_axis} Z={pose.Z_axis} (0.001mm)")
    if pose.X_axis == 0 and pose.Y_axis == 0 and pose.Z_axis == 0:
        print("    ⚠️ 警告: 位姿全为0！")
    
    # 3. 检查电机使能状态
    print(f"\n[3] 读取电机使能状态 (GetArmEnableStatus):")
    status = piper.GetArmEnableStatus()
    print(f"    {status}")
    
    # 4. 检查机械臂状态码
    print(f"\n[4] 读取状态 (GetArmStatus):")
    arm_status = piper.GetArmStatus()
    print(f"    {arm_status}")
    
    # 5. 检查控制指令反馈（主臂模式下这里能读到控制指令）
    print(f"\n[5] 读取控制指令 (GetArmJointCtrl):")
    ctrl = piper.GetArmJointCtrl()
    c = ctrl.joint_ctrl
    ctrls = [c.joint_1, c.joint_2, c.joint_3, c.joint_4, c.joint_5, c.joint_6]
    print(f"    {ctrls}")
    
    piper.DisconnectPort()
    return joints, status

def test_follower_move():
    print(f"\n{'='*60}")
    print("测试 Follower 关节运动")
    print('='*60)
    
    piper = C_PiperInterface_V2(can_name="can_follower", judge_flag=False, can_auto_init=True)
    piper.ConnectPort()
    
    # 使能
    print("\n使能电机...")
    timeout = 5.0
    start = time.time()
    while not piper.EnablePiper():
        if time.time() - start > timeout:
            print("❌ 使能超时！")
            piper.DisconnectPort()
            return False
        time.sleep(0.01)
    print("✅ 电机已使能")
    
    # 读取当前位置
    js = piper.GetArmJointMsgs().joint_state
    current = [js.joint_1, js.joint_2, js.joint_3, js.joint_4, js.joint_5, js.joint_6]
    print(f"当前位置: {[c/1000 for c in current]} deg")
    
    # 关节1 +/- 10度测试
    target1 = [current[0] + 10000] + current[1:]
    print(f"\n发送目标: {[t/1000 for t in target1]} deg")
    piper.MotionCtrl_2(0x01, 0x01, 30, 0x00)
    time.sleep(0.05)
    piper.JointCtrl(*target1)
    time.sleep(2.0)
    
    js_new = piper.GetArmJointMsgs().joint_state
    new_pos = [js_new.joint_1, js_new.joint_2, js_new.joint_3, js_new.joint_4, js_new.joint_5, js_new.joint_6]
    print(f"运动后:   {[n/1000 for n in new_pos]} deg")
    
    # 恢复原位
    piper.JointCtrl(*current)
    time.sleep(2.0)
    
    piper.DisablePiper()
    piper.DisconnectPort()
    
    moved = abs(new_pos[0] - current[0]) > 1000  # 变化 > 1度
    if moved:
        print("✅ Follower 可以正常运动")
    else:
        print("❌ Follower 没有响应关节控制命令！")
    return moved

if __name__ == "__main__":
    print("Piper 遥操作故障诊断")
    print("请确保 can_leader 和 can_follower 已激活，且两个臂已上电")
    
    leader_joints, leader_status = check_arm("Leader", "can_leader")
    follower_joints, follower_status = check_arm("Follower", "can_follower")
    follower_ok = test_follower_move()
    
    print(f"\n{'='*60}")
    print("诊断总结")
    print('='*60)
    
    if all(j == 0 for j in leader_joints):
        print("\n🔴 关键发现: Leader 关节读数全为0")
        print("   原因: Leader 可能被设为了'主臂模式'(0xFA)")
        print("   主臂模式只发送控制帧，不发送反馈帧")
        print("   LeRobot 读取不到 Leader 位置，导致从臂不动")
        print("\n   修复方法:")
        print("   1. 运行: python -c \"from piper_sdk import C_PiperInterface_V2; p=C_PiperInterface_V2('can_leader'); p.ConnectPort(); p.MasterSlaveConfig(0x00,0,0,0); p.DisconnectPort()\"")
        print("   2. 对 Follower 同样执行上述命令（can_name='can_follower'）")
        print("   3. 关闭两个机械臂电源，等待5秒")
        print("   4. 先开 Follower，再开 Leader")
        print("   5. 重新运行遥操作")
    elif not follower_ok:
        print("\n🔴 Follower 不响应控制命令")
        print("   可能原因:")
        print("   1. Follower 被设为从臂模式(0xFC) - 需要按上述方法恢复")
        print("   2. CAN 接线问题")
        print("   3. 电机有错误状态 - 尝试断电重启")
    else:
        print("\n🟢 硬件通信正常！问题在软件遥操作逻辑")
        print("   建议:")
        print("   1. 改用关节空间控制: --robot.use_cartesian_control=false --teleop.use_cartesian_control=false")
        print("   2. 检查 candump can_follower 是否有高频 TX 帧")
