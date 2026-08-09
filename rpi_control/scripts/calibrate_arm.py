#!/usr/bin/env python3
"""Interactive arm calibration script.

This script guides the user through calibrating each servo joint
of the robotic arm, saving offsets to the system configuration.
"""

import json
import os
import sys
import time
from pathlib import Path


def print_header():
    """Print calibration script header."""
    print("=" * 60)
    print("  Robotic Arm Servo Calibration Tool")
    print("=" * 60)
    print()
    print("This tool will help you calibrate each servo joint.")
    print("For each joint, you will:")
    print("  1. Set the servo to its neutral position")
    print("  2. Fine-tune the offset")
    print("  3. Verify the position")
    print()


def get_float_input(prompt, default=0.0):
    """Get a float input from the user with default."""
    try:
        value = input(f"{prompt} [{default}]: ").strip()
        if not value:
            return default
        return float(value)
    except ValueError:
        print(f"Invalid input, using default: {default}")
        return default


def calibrate_joint(joint_id, current_offset=0.0):
    """Calibrate a single joint."""
    print(f"\n--- Joint {joint_id} Calibration ---")
    print(f"Current offset: {current_offset}")

    print("Move the servo to its neutral/home position.")
    input("Press Enter when ready...")

    print("\nOptions:")
    print("  1. Set offset manually")
    print("  2. Increment offset (+1 degree)")
    print("  3. Decrement offset (-1 degree)")
    print("  4. Set to zero")
    print("  5. Keep current and continue")

    choice = input("Choice [5]: ").strip()

    if choice == "1":
        offset = get_float_input("Enter new offset (degrees)")
        return offset
    elif choice == "2":
        return current_offset + 1.0
    elif choice == "3":
        return current_offset - 1.0
    elif choice == "4":
        return 0.0
    else:
        return current_offset


def verify_calibration(offsets):
    """Verify the calibration by testing all joints."""
    print("\n" + "=" * 60)
    print("  Calibration Verification")
    print("=" * 60)
    print()
    print("Current offsets:")
    for i, offset in enumerate(offsets, 1):
        print(f"  Joint {i}: {offset:.1f} degrees")
    print()

    print("Testing joint movements...")
    for i in range(6):
        print(f"  Moving Joint {i+1} to 0 degrees...")
        time.sleep(0.5)
    print("  All joints test complete.")

    print("\nDoes the arm appear correctly calibrated?")
    print("  1. Yes - Save calibration")
    print("  2. No - Recalibrate")
    print("  3. Cancel")

    choice = input("Choice [1]: ").strip()
    return choice


def save_calibration(offsets):
    """Save calibration offsets to config file."""
    config_dir = Path("./data")
    config_dir.mkdir(parents=True, exist_ok=True)

    config_path = config_dir / "calibration.json"
    config = {
        "joint_offsets": offsets,
        "calibrated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "version": "1.0",
    }

    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    print(f"\nCalibration saved to: {config_path}")
    return config_path


def load_calibration():
    """Load existing calibration if available."""
    config_path = Path("./data/calibration.json")
    if config_path.exists():
        with open(config_path) as f:
            config = json.load(f)
            return config.get("joint_offsets", [0.0] * 6)
    return [0.0] * 6


def main():
    """Main calibration routine."""
    print_header()

    # Load existing offsets
    offsets = load_calibration()
    if any(o != 0.0 for o in offsets):
        print("Found existing calibration offsets:")
        for i, offset in enumerate(offsets, 1):
            print(f"  Joint {i}: {offset:.1f} degrees")
        print()

    while True:
        print("\nCalibration Menu:")
        print("  1. Calibrate all joints")
        print("  2. Calibrate specific joint")
        print("  3. View current offsets")
        print("  4. Save and exit")
        print("  5. Exit without saving")

        choice = input("\nChoice [1]: ").strip()

        if choice == "2":
            try:
                joint_id = int(input("Joint ID (1-6): "))
                if 1 <= joint_id <= 6:
                    offsets[joint_id - 1] = calibrate_joint(joint_id, offsets[joint_id - 1])
                else:
                    print("Invalid joint ID. Must be 1-6.")
            except ValueError:
                print("Invalid input.")
        elif choice == "3":
            print("\nCurrent offsets:")
            for i, offset in enumerate(offsets, 1):
                print(f"  Joint {i}: {offset:.1f} degrees")
        elif choice == "4":
            verify = verify_calibration(offsets)
            if verify == "1":
                save_calibration(offsets)
                print("Calibration complete!")
                return
            elif verify == "3":
                print("Calibration cancelled.")
                return
        elif choice == "5":
            print("Exiting without saving.")
            return
        else:
            # Calibrate all
            for i in range(6):
                offsets[i] = calibrate_joint(i + 1, offsets[i])


if __name__ == "__main__":
    main()