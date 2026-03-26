import argparse
import time

from pika import sense

from utils import format_pose_6d


def read_one(tag: str, dev) -> str:
    enc = dev.get_encoder_data()
    cmd = dev.get_command_state()
    dist = dev.get_gripper_distance()
    pose = format_pose_6d(dev.get_pose())
    return (
        f"{tag} rad={enc['rad']:.4f}, angle={enc['angle']:.2f}, "
        f"cmd={cmd}, dist_mm={dist:.2f}, pose={pose}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Read two PIKA Sense devices continuously.")
    parser.add_argument("--port-a", default="/dev/ttyUSB0", help="Serial port for first device")
    parser.add_argument("--port-b", default="/dev/ttyUSB1", help="Serial port for second device")
    parser.add_argument("--sleep", type=float, default=0.1, help="Loop sleep seconds")
    args = parser.parse_args()

    dev_a = sense(args.port_a)
    dev_b = sense(args.port_b)

    ok_a = dev_a.connect()
    ok_b = dev_b.connect()
    print(f"connect[senseA={args.port_a}]:", ok_a)
    print(f"connect[senseB={args.port_b}]:", ok_b)
    if not ok_a or not ok_b:
        if ok_a:
            dev_a.disconnect()
        if ok_b:
            dev_b.disconnect()
        raise SystemExit(1)

    try:
        print("tracker devices A:", dev_a.get_tracker_devices())
        print("tracker devices B:", dev_b.get_tracker_devices())

        while True:
            try:
                print(read_one("senseA", dev_a))
            except Exception as e:
                print(f"senseA error: {e}")

            try:
                print(read_one("senseB", dev_b))
            except Exception as e:
                print(f"senseB error: {e}")

            time.sleep(args.sleep)
    except KeyboardInterrupt:
        print("\nCtrl+C received, shutting down safely...")
    finally:
        dev_a.disconnect()
        dev_b.disconnect()
        print("disconnect: done")


if __name__ == "__main__":
    main()
