## lerobot_robot_piper_follower

LeRobot robot plugin for AgileX PiPER follower arm (CAN based).

### Action schema

- Joint target: `joint_1.pos ... joint_6.pos` (rad)
- Gripper: `gripper.pos` (0..1, optional)

### Observation schema

- Joint state: `joint_1.pos ... joint_6.pos` (rad)
- Gripper: `gripper.pos` (0..1)
- End-effector pose from feedback: `endpose.x, endpose.y, endpose.z, endpose.roll, endpose.pitch, endpose.yaw`

### Minimal config example

```yaml
robot:
  type: piper_follower
  can_name: can_follower
  id: piper_follower_01
  disable_on_disconnect: false
  max_relative_target: 0.08
  workspace_limits:
    x: [0.20, 0.55]
    y: [-0.25, 0.25]
    z: [0.05, 0.40]
```

Default CAN names expected for this project are `can_leader` and `can_follower`.

`disable_on_disconnect=false` keeps motors enabled on exit so the arm keeps holding pose.
`workspace_limits` checks the predicted FK end-effector position before `JointCtrl`; out-of-bounds joint targets are rejected.

To measure `workspace_limits` from the real robot, run:

```bash
python3 tools/measure_workspace.py --can-name can_follower --margin 0.02
```

Move the robot through the full safe workspace, then press `Ctrl-C`. The script prints `workspace_limits` in YAML form and can optionally save JSON with `--output`.
