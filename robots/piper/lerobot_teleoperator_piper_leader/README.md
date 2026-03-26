## lerobot_teleoperator_piper_leader

LeRobot teleoperator plugin for AgileX PiPER leader arm (CAN based).

### Output action schema

- `joint_1.pos ... joint_6.pos` (rad)
- `gripper.pos` (normalized 0..1)

### Minimal config example

```yaml
teleop:
  type: piper_leader
  can_name: can_leader
  id: piper_leader_01
  source_mode: feedback
  hand_guiding: true
  hand_guiding_mode: free
```

`source_mode=feedback` is recommended for hand-guided teleoperation.

### Hand-guiding options

- `hand_guiding_mode=free` (default): disable arm and use free-drive style drag.
- `hand_guiding_mode=drag_teach`: keep servo on and enter drag-teach assist mode.

`drag_teach` tuning fields:

- `teaching_friction` (1~10): higher value increases resistance.
- `teaching_range_per` (100~200): teaching stroke scale.
- `teaching_max_range_mm` (`0`, `70`, or `100`): gripper/teaching max stroke limit.

Example:

```yaml
teleop:
  type: piper_leader
  can_name: can_leader
  id: piper_leader_01
  hand_guiding: true
  hand_guiding_mode: drag_teach
  teaching_friction: 2
  teaching_range_per: 100
  teaching_max_range_mm: 70
  source_mode: feedback
```
