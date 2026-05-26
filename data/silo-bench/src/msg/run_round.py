"""CLI: python -m src.msg.run_round -- Execute one round for a P2P case."""

import argparse

from src.engine import run_round


def main():
    parser = argparse.ArgumentParser(description="Run one round of a P2P (msg) case")
    parser.add_argument("--case-dir", required=True, help="Case directory path")
    args = parser.parse_args()

    done = run_round(args.case_dir)
    if done:
        print("Case completed.")
    else:
        print("Round completed. Case still running.")


if __name__ == "__main__":
    main()
