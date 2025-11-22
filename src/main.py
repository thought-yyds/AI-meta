"""Command-line entry point for the agent workflow."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Optional


if __package__:
    # Import from the new unified Agent implementation
    from .agents.Agent import Agent, AgentConfig
    from .llm import DoubaoService
else:  # pragma: no cover - executed when running as a script
    current_dir = Path(__file__).resolve().parent
    if str(current_dir) not in sys.path:
        sys.path.insert(0, str(current_dir))
    # Fallback imports when executed as a plain script
    from agents.Agent import Agent, AgentConfig
    from llm import DoubaoService


def _read_context(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    file_path = Path(path).expanduser().resolve()
    if not file_path.exists():
        raise FileNotFoundError(f"Context file not found: {file_path}")
    return file_path.read_text(encoding="utf-8")


def configure_logging(level: str) -> None:
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    if not isinstance(log_level, int):
        logging.warning("Unknown log level '%s'; defaulting to INFO.", level)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the agent assistant.")
    parser.add_argument(
        "task",
        nargs="?",
        help="Task description for the agent. When omitted, read from stdin.",
    )
    parser.add_argument(
        "--context-file",
        help="Optional path to a file whose contents will be provided as additional context.",
    )
    parser.add_argument(
        "--working-dir",
        help="Working directory for tool execution (defaults to current directory).",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=15,
        help="Maximum number of reasoning steps (default: 15).",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.2,
        help="LLM temperature for reasoning (default: 0.2).",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level (e.g. DEBUG, INFO).",
    )
    parser.add_argument(
        "--stop-on-tool-error",
        action="store_true",
        help="Abort the run immediately when a tool returns an error.",
    )
    args = parser.parse_args()

    configure_logging(args.log_level)

    task = args.task or input("Enter task for the agent:\n").strip()
    if not task:
        raise SystemExit("A non-empty task description is required.")

    context = _read_context(args.context_file)

    config = AgentConfig(
        max_iterations=args.max_iterations,
        llm_temperature=args.temperature,
        working_dir=args.working_dir,
        stop_on_tool_error=args.stop_on_tool_error,
    )

    # Initialize a single DoubaoService instance to act as the LLM "brain" for all agents
    try:
        llm_service = DoubaoService()
        logging.info("Initialized shared DoubaoService instance for agents")
    except Exception as exc:  # noqa: BLE001
        logging.exception("Failed to initialize DoubaoService")
        raise SystemExit(f"Failed to initialize DoubaoService: {exc}") from exc

    agent = Agent(config=config, llm_service=llm_service)
    result = agent.run(task, context=context)

    printable = {
        "task": result.task,
        "final_answer": result.final_answer,
        "error": result.error,
        "steps": [
            {
                "thought": step.thought,
                "action": step.action,
                "action_input": step.action_input,
                "observation": step.observation,
                "final_answer": step.final_answer,
            }
            for step in result.steps
        ],
    }
    
    print(json.dumps(printable, ensure_ascii=False, indent=2))

    if result.error:
        raise SystemExit(1)


if __name__ == "__main__":
    main()


