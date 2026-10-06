"""One command for "is it done?". Spec: docs/live-coding.md.

    python -m uv run python -m scripts.check                 # offline: tests + spec/data rules, < 5 s
    python -m uv run python -m scripts.check --live T-024    # + one real ticket: status, tools, cost, trace URL
    python -m uv run python -m scripts.check --eval 5        # + a mini experiment on 5 dataset items

Exit code 0 only when every step passes. Paste the output when you say "done".
"""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = [sys.executable]


def step(title: str, cmd: list[str]) -> bool:
    print(f"\n== {title}: {' '.join(cmd)}", flush=True)
    ok = subprocess.run(cmd, cwd=ROOT).returncode == 0
    print(f"== {title}: {'OK' if ok else 'FAIL'}", flush=True)
    return ok


def changed_files() -> list[str]:
    out = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout
    return [line[3:] for line in out.splitlines()]


def spec_rule(files: list[str]) -> bool:
    """CLAUDE.md rule 1: a change in app/ or evals/ comes with a change in docs/specs/."""
    code = [f for f in files if f.startswith(("app/", "evals/")) and f.endswith(".py")]
    specs = [f for f in files if f.startswith("docs/specs/")]
    print(f"\n== spec rule: code changed {code or '-'}, specs changed {specs or '-'}")
    if code and not specs:
        print("== spec rule: FAIL (update docs/specs/<module>.md and its diagram in the same commit)")
        return False
    print("== spec rule: OK")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(prog="scripts.check")
    parser.add_argument("--live", metavar="TICKET_ID", help="Run one dataset ticket through the real pipeline")
    parser.add_argument("--eval", type=int, metavar="N", help="Run the experiment on the first N dataset items")
    parser.add_argument("--run-name", default="live-coding", help="Experiment run name for --eval")
    args = parser.parse_args()

    results = [step("tests", [*PY, "-m", "pytest", "-q", "-p", "no:warnings"]), spec_rule(changed_files())]
    if args.live:
        results.append(step("live ticket", [*PY, "-m", "app.cli", "process", "data/tickets.jsonl",
                                            "--ids", args.live, "-v"]))
    if args.eval:
        results.append(step("mini experiment", [*PY, "-m", "evals.run_experiment", "--limit", str(args.eval),
                                                "--run-name", args.run_name]))

    print(f"\nCHECK {'PASS' if all(results) else 'FAIL'}: {sum(results)}/{len(results)} steps")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
