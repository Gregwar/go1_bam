import placo
import json
import numpy as np
import time
from placo_utils.visualization import robot_viz, point_viz
from placo_utils.tf import tf
from .etherban import Client
from .trajectory_2r import SquareWave
import argparse

args_parser = argparse.ArgumentParser()
args_parser.add_argument("--meshcat", action="store_true")
args_parser.add_argument("--plot", action="store_true")
args_parser.add_argument("--robot", action="store_true")
args_parser.add_argument("--kp", type=float, default=10.0)
args_parser.add_argument("--r1_offset", type=float, default=None)
args_parser.add_argument("--r2_offset", type=float, default=None)
args_parser.add_argument("--mass", type=float, default=9.5)
args_parser.add_argument("--trajectory", type=str, default="square_wave")
args_parser.add_argument("--logdir", type=str, required=True)
args = args_parser.parse_args()

robot = placo.RobotWrapper("2R/2r_erob/robot.urdf", placo.Flags.ignore_collisions)
robot.update_kinematics()

solver = placo.KinematicsSolver(robot)
solver.mask_fbase(True)

effector_task = solver.add_position_task("end", np.array([0.0, 0.0, 0.0]))
effector_task.mask.set_axises("xz")

solver.add_regularization_task(1e-3)

if args.trajectory == "square_wave":
    trajectory = SquareWave()
else:
    print(f"Unknown trajectory: {args.trajectory}")

# Initializing the robot
effector_task.target_world = trajectory(0.0)
for k in range(100):
    solver.solve(True)
    robot.update_kinematics()

if args.plot:
    import matplotlib.pyplot as plt

    ts = np.linspace(0, trajectory.duration, 1000)
    pos = np.array([trajectory(t) for t in ts])
    effector_pos = []

    for t in ts:
        effector_task.target_world = trajectory(t)
        for k in range(16):
            solver.solve(True)
            robot.update_kinematics()
        effector_position = robot.get_T_world_frame("end")[:3, 3]
        effector_pos.append(effector_position)
    effector_pos = np.array(effector_pos)

    plt.plot(pos[:, 0], pos[:, 2], label="target")
    plt.plot(effector_pos[:, 0], effector_pos[:, 2], label="effector")
    plt.xlabel("x")
    plt.ylabel("z")
    plt.axis("equal")
    plt.grid()
    plt.tight_layout()
    plt.show()
    exit()


def send_order(eth: Client, r1: float, r2: float):
    eth.position_control(0, args.r1_offset + r1, 0.0, args.kp, 2.0)
    eth.position_control(1, args.r2_offset + r2, 0.0, args.kp, 1.0)


if not args.meshcat and not args.robot and not args.plot:
    print("Please set either --meshcat, --robot or --plot")
    exit()

if args.meshcat:
    viz = robot_viz(robot)
elif args.robot:
    if args.r1_offset is None or args.r2_offset is None:
        print("Please set r1_offset and r2_offset")
        exit()

    eth = Client("localhost")
    # Initializing the system
    eth.run_background()
    eth.wait_stability(0)
    eth.wait_stability(1)

    send_order(robot.get_joint("R1"), robot.get_joint("R2"))
    time.sleep(5.0)

t_start = time.time()
data = {
    "mass": args.mass,
    "length": [0.25, 0.25],
    "kp": args.kp,
    "trajectory": "square_wave",
    "entries": [],
}

t = 0
while t < trajectory.duration:
    t = time.time() - t_start

    effector_task.target_world = trajectory(t)
    solver.solve(True)
    robot.update_kinematics()

    if args.meshcat:
        viz.display(robot.state.q)
        time.sleep(0.01)
    elif args.robot:
        send_order(robot.get_joint("R1"), robot.get_joint("R2"))
        status = eth.statuses
        # TODO: Retrieve in statuses

    point_viz("target", effector_task.target_world)

filename = f"{args.logdir}_{trajectory}_{args.kp}.json"
with open(filename, "w") as f:
    json.dump(data, f)
