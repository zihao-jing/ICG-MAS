"""CLI: python -m src.msg.init_case -- Initialize a P2P protocol case."""

import argparse

from src.engine import DEFAULT_API_KEY, DEFAULT_MODEL, DEFAULT_MODEL_URL, init_case


def main():
    parser = argparse.ArgumentParser(description="Initialize a P2P (msg) protocol case")
    parser.add_argument("--task-file", required=True, help="Path to task JSON")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Model name")
    parser.add_argument("--api-base", default=DEFAULT_MODEL_URL, help="API base URL")
    parser.add_argument("--api-key", default=DEFAULT_API_KEY, help="API key")
    parser.add_argument("--max-rounds", type=int, default=100, help="Max rounds")
    parser.add_argument("--workspace", default="workspace", help="Workspace directory")
    args = parser.parse_args()

    case_dir = init_case(
        task_file=args.task_file,
        protocol="msg",
        model=args.model,
        api_base=args.api_base,
        api_key=args.api_key,
        max_rounds=args.max_rounds,
        workspace=args.workspace,
    )
    print(f"Case initialized: {case_dir}")


if __name__ == "__main__":
    main()
