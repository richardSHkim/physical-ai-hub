#!/usr/bin/env python3

import argparse
import time

from piper_sdk import *


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("can_name", help="CAN interface name such as can0")
    args = parser.parse_args()

    piper = C_PiperInterface_V2(args.can_name)
    piper.ConnectPort()
    while not piper.EnablePiper():
        time.sleep(0.01)

    factor = 57295.7795  # 1000 * 180 / pi
    position = [0, 0, 0, 0, 0, 0, 0]

    joint_0 = round(position[0] * factor)
    joint_1 = round(position[1] * factor)
    joint_2 = round(position[2] * factor)
    joint_3 = round(position[3] * factor)
    joint_4 = round(position[4] * factor)
    joint_5 = round(position[5] * factor)
    joint_6 = round(position[6] * 1000 * 1000)

    piper.ModeCtrl(0x01, 0x01, 30, 0x00)
    piper.JointCtrl(joint_0, joint_1, joint_2, joint_3, joint_4, joint_5)
    piper.GripperCtrl(abs(joint_6), 1000, 0x01, 0)

    print(f"{args.can_name} moved to zero")
