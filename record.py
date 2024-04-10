import json
import datetime
import os
import numpy as np
import argparse
import time
from dynamixel import DynamixelActuatorV1, compute_volts
from trajectory import *

arg_parser = argparse.ArgumentParser()
arg_parser.add_argument("--mass", type=float, required=True)
arg_parser.add_argument("--length", type=float, required=True)
arg_parser.add_argument("--port", type=str, default="/dev/ttyUSB0")
arg_parser.add_argument("--logdir", type=str, required=True)
arg_parser.add_argument("--trajectory", type=str, default="lift_and_drop")
arg_parser.add_argument("--kp", type=int, default=32)
args = arg_parser.parse_args()

if args.trajectory not in trajectories:
    raise ValueError(f"Unknown trajectory: {args.trajectory}")

dxl = DynamixelActuatorV1(args.port)
trajectory = trajectories[args.trajectory]

start = time.time()
while time.time() - start < 1.0:
    goal_position, torque_enable = trajectory(0)
    if torque_enable:
        dxl.set_goal_position(goal_position)
    dxl.set_torque(torque_enable)
    dxl.set_p_gain(args.kp)

start = time.time()
data = {
    "mass": args.mass,
    "length": args.length,
    "kp": args.kp,
    "entries": []
}

while time.time() - start < trajectory.duration:
    t = time.time() - start
    goal_position, new_torque_enable = trajectory(t)
    if new_torque_enable != torque_enable:
        dxl.set_torque(new_torque_enable)
        torque_enable = new_torque_enable
    if torque_enable:
        dxl.set_goal_position(goal_position)

    t0 = time.time() - start
    entry = dxl.read_data()
    t1 = time.time() - start

    entry["timestamp"] = (t0 + t1) / 2.0
    entry["goal_position"] = goal_position
    entry["torque_enable"] = torque_enable
    data["entries"].append(entry)

#Format YYYY-MM-DD_HH:mm:ss"
date = datetime.datetime.now().strftime("%Y-%m-%d_%Hh%Mm%S")

filename = f"{args.logdir}/{date}.json"
json.dump(data, open(filename, "w"))
