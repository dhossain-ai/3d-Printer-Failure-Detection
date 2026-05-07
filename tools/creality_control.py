"""CLI tool for safe Creality K1C WebSocket control."""

import argparse
import sys
import os
from pathlib import Path

# Add project root to path so we can import creality_control
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from creality_control import CrealityWebSocketControlClient


def main():
    parser = argparse.ArgumentParser(description="Send low-risk commands to Creality K1C via WebSocket.")
    parser.add_argument("ws_url", help="WebSocket URL (e.g., ws://192.168.137.211:9999)")
    
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # light
    light_parser = subparsers.add_parser("light", help="Control LED light")
    light_parser.add_argument("state", choices=["on", "off"], help="Light state")
    
    # fan
    fan_parser = subparsers.add_parser("fan", help="Control fans")
    fan_parser.add_argument("type", choices=["model", "auxiliary", "case"], help="Fan type")
    fan_parser.add_argument("state", choices=["on", "off"], help="Fan state")
    
    # files
    subparsers.add_parser("files", help="Request file list")

    args = parser.parse_args()

    client = CrealityWebSocketControlClient(ws_url=args.ws_url)

    if args.command == "light":
        result = client.set_light(args.state == "on")
    elif args.command == "fan":
        enabled = args.state == "on"
        if args.type == "model":
            result = client.set_model_fan(enabled)
        elif args.type == "auxiliary":
            result = client.set_auxiliary_fan(enabled)
        elif args.type == "case":
            result = client.set_case_fan(enabled)
    elif args.command == "files":
        result = client.request_file_list()
    else:
        print(f"Unknown command: {args.command}")
        sys.exit(1)

    print(f"Action: {result.action}")
    print(f"Success: {result.success}")
    print(f"Message: {result.message}")
    if result.response_preview:
        print(f"Response: {result.response_preview}")

    if not result.success:
        sys.exit(1)


if __name__ == "__main__":
    main()
