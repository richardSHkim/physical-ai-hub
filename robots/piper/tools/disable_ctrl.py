import argparse
import time
from piper_sdk import *


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("can_name", default="can0")
    args = parser.parse_args()

    piper = C_PiperInterface_V2(args.can_name)
    piper.ConnectPort()
    while(piper.DisablePiper()):
        time.sleep(0.01)
    print(f"{args.can_name} disabled")
    