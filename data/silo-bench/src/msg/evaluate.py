"""CLI: python -m src.msg.evaluate -- Evaluate a P2P case."""

import argparse

from src.engine import evaluate


def main():
    parser = argparse.ArgumentParser(description="Evaluate a P2P (msg) case")
    parser.add_argument("--case-dir", required=True, help="Case directory path")
    args = parser.parse_args()

    results = evaluate(args.case_dir)
    print(f"Success rate: {results['metrics']['success_rate']:.2%}")
    print(f"Token efficiency: {results['metrics']['token_efficiency']:.1f}")
    print(f"Communication density: {results['metrics']['communication_density']:.3f}")


if __name__ == "__main__":
    main()
