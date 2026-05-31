#!/usr/bin/env python3
"""Run a Ralph-style optimization loop for the Anki Sorter ranking algorithm.

The loop is intentionally conservative: it creates scratch copies of the repo,
asks an external agent command to produce variants, benchmarks those variants,
and writes a comparison report. It only applies the winning patch to the real
checkout when --apply-winner is passed.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import shlex
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = "python3 scripts/benchmark_ranking.py --json"
UNITTEST = "python3 -m unittest discover -s tests"


@dataclass
class CommandResult:
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    def combined(self) -> str:
        parts = []
        if self.stdout:
            parts.append(self.stdout)
        if self.stderr:
            parts.append("[stderr]\n" + self.stderr)
        return "\n".join(parts).strip()


@dataclass
class VariantResult:
    iteration: int
    variant: int
    path: Path
    prompt_path: Path
    agent_ok: bool
    tests_ok: bool
    benchmark_ok: bool
    objective: float | None
    diff_path: Path
    benchmark_path: Path
    unittest_log_path: Path
    agent_log_path: Path
    error: str | None = None


def run_shell(
    command: str,
    cwd: Path,
    *,
    timeout: int,
    input_text: str | None = None,
) -> CommandResult:
    completed = subprocess.run(
        shlex.split(command),
        cwd=str(cwd),
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    return CommandResult(completed.returncode, completed.stdout, completed.stderr)


def run_args(args: list[str], cwd: Path, *, timeout: int) -> CommandResult:
    completed = subprocess.run(
        args,
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    return CommandResult(completed.returncode, completed.stdout, completed.stderr)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def default_agent_cmd() -> str | None:
    env_cmd = os.environ.get("RALPH_CMD")
    if env_cmd:
        return env_cmd
    if shutil.which("ralph"):
        return "ralph"
    return None


def copy_repo_to_scratch(destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    tracked = run_args(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        ROOT,
        timeout=60,
    )
    if not tracked.ok:
        raise RuntimeError(f"Could not list copyable repo files:\n{tracked.combined()}")

    seen: set[str] = set()
    for raw_path in tracked.stdout.splitlines():
        if not raw_path or raw_path in seen:
            continue
        seen.add(raw_path)
        relative_path = Path(raw_path)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            continue
        source_path = ROOT / relative_path
        if not source_path.exists() or not source_path.is_file():
            continue
        target_path = destination / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path, follow_symlinks=False)

    run_args(["git", "init"], destination, timeout=60)
    run_args(["git", "config", "user.name", "Ralph Loop"], destination, timeout=30)
    run_args(["git", "config", "user.email", "ralph-loop@example.invalid"], destination, timeout=30)
    run_args(["git", "add", "."], destination, timeout=60)
    commit = run_args(["git", "commit", "--quiet", "-m", "baseline"], destination, timeout=60)
    if not commit.ok:
        raise RuntimeError(f"Could not create scratch baseline commit in {destination}:\n{commit.combined()}")
    exclude_path = destination / ".git" / "info" / "exclude"
    with exclude_path.open("a", encoding="utf-8") as handle:
        handle.write("\n.ralph-loop/\n")


def render_agent_command(command_template: str, prompt_path: Path, worktree: Path) -> tuple[str, bool]:
    replacements = {
        "prompt_file": shlex.quote(str(prompt_path)),
        "worktree": shlex.quote(str(worktree)),
        "repo_root": shlex.quote(str(ROOT)),
        "prompt": shlex.quote(prompt_path.read_text(encoding="utf-8")),
    }
    rendered = command_template
    used_placeholder = False
    for key, value in replacements.items():
        placeholder = "{" + key + "}"
        if placeholder in rendered:
            rendered = rendered.replace(placeholder, value)
            used_placeholder = True
    return rendered, used_placeholder


def variant_angle(variant: int) -> str:
    angles = [
        "Try a nonlinear frequency/readability blend: keep frequency dominant, but use a curve or saturation function so close ranks care more about readability than distant ranks.",
        "Try a Pareto/frontier or banded ranking idea: group by useful frequency bands first, then use readability tradeoffs inside each band without returning to hard buckets.",
        "Try an adaptive penalty idea: unknown-kanji cost changes with raw rank, coverage, and source confidence rather than being a fixed multiplier.",
        "Try a calibrated tie-breaker idea: keep the score simple but improve ordering by adding principled secondary keys for length, source confidence, and partial known coverage.",
    ]
    return angles[(variant - 1) % len(angles)]


def build_prompt(
    *,
    iteration: int,
    variant: int,
    baseline: dict[str, Any],
    prior_winner: dict[str, Any] | None,
) -> str:
    baseline_objective = baseline.get("objective", "unknown")
    prior_text = "No prior winner yet."
    if prior_winner:
        prior_text = json.dumps(prior_winner, ensure_ascii=False, indent=2, sort_keys=True)

    return f"""You are optimizing the Anki Sorter ranking algorithm in this scratch repo.

Iteration: {iteration}
Variant: {variant}
Variant angle: {variant_angle(variant)}

Baseline objective from scripts/benchmark_ranking.py:
{baseline_objective}

Prior best variant, if any:
{prior_text}

Task:
1. Inspect addon/anki_sorter/ranking.py, README.md, and tests/test_ranking.py.
2. Invent one concrete algorithmic improvement for frequency_first_soft_v1.
3. Keep the product goal: prioritize useful common Japanese cards while keeping the top of queue readable and not painful.
4. Edit only files that are directly relevant to ranking behavior, docs, or tests.
5. Do not touch a live Anki collection, install the add-on, package the add-on, call network APIs, push to GitHub, or edit files outside this scratch repo.
6. Run these checks before finishing:
   - {UNITTEST}
   - {BENCHMARK}
7. Leave a concise note in OPTIMIZATION_NOTES.md explaining the idea, expected tradeoff, and benchmark result.

Important benchmark details:
- The loop compares the JSON field named "objective".
- Preference failures matter a lot; avoid gaming synthetic NDCG by violating README behavior.
- Runtime should remain simple O(n log n) sorting over scored cards.
- A useful but smaller improvement is better than a complicated fragile one.

Return only after the repo contains your best variant and the checks have been run.
"""


def run_tests(worktree: Path, log_path: Path, timeout: int) -> bool:
    result = run_shell(UNITTEST, worktree, timeout=timeout)
    write_text(log_path, result.combined() + "\n")
    return result.ok


def run_benchmark(worktree: Path, output_path: Path, timeout: int) -> tuple[bool, float | None, str | None]:
    result = run_shell(BENCHMARK, worktree, timeout=timeout)
    write_text(output_path, result.stdout if result.stdout else result.combined() + "\n")
    if not result.ok:
        return False, None, result.combined()
    payload = read_json(output_path)
    if not payload:
        return False, None, "Benchmark did not emit valid JSON."
    objective = payload.get("objective")
    if isinstance(objective, (int, float)):
        return True, float(objective), None
    return False, None, "Benchmark JSON did not include numeric objective."


def git_diff(worktree: Path, diff_path: Path) -> None:
    # Include relevant untracked files, such as new tests or OPTIMIZATION_NOTES.md,
    # while keeping .ralph-loop/ artifacts excluded via .git/info/exclude.
    run_args(["git", "add", "-N", "."], worktree, timeout=60)
    result = run_args(["git", "diff", "--binary"], worktree, timeout=60)
    write_text(diff_path, result.stdout)


def run_variant(
    *,
    run_dir: Path,
    iteration: int,
    variant: int,
    baseline: dict[str, Any],
    prior_winner: dict[str, Any] | None,
    agent_cmd: str | None,
    dry_run: bool,
    agent_timeout: int,
    check_timeout: int,
) -> VariantResult:
    variant_dir = run_dir / f"iter-{iteration:02d}" / f"variant-{variant:02d}"
    copy_repo_to_scratch(variant_dir)

    prompt = build_prompt(
        iteration=iteration,
        variant=variant,
        baseline=baseline,
        prior_winner=prior_winner,
    )
    prompt_path = run_dir / f"iter-{iteration:02d}" / f"variant-{variant:02d}-prompt.md"
    write_text(prompt_path, prompt)

    artifact_dir = variant_dir / ".ralph-loop"
    agent_log = artifact_dir / "agent.log"
    unit_log = artifact_dir / "unittest.log"
    benchmark_path = artifact_dir / "benchmark.json"
    diff_path = variant_dir / "diff.patch"

    agent_ok = True
    error: str | None = None
    if dry_run:
        write_text(agent_log, "DRY RUN: agent was not executed. Prompt saved at: " + str(prompt_path) + "\n")
    elif not agent_cmd:
        agent_ok = False
        error = "No Ralph/agent command found. Set RALPH_CMD or pass --agent-cmd."
        write_text(agent_log, error + "\n")
    else:
        rendered, used_placeholder = render_agent_command(agent_cmd, prompt_path, variant_dir)
        try:
            result = run_shell(
                rendered,
                variant_dir,
                timeout=agent_timeout,
                input_text=None if used_placeholder else prompt,
            )
            agent_ok = result.ok
            write_text(agent_log, result.combined() + "\n")
            if not result.ok:
                error = f"Agent command exited {result.returncode}."
        except subprocess.TimeoutExpired:
            agent_ok = False
            error = f"Agent command timed out after {agent_timeout} seconds."
            write_text(agent_log, error + "\n")

    tests_ok = run_tests(variant_dir, unit_log, check_timeout)
    benchmark_ok, objective, benchmark_error = run_benchmark(variant_dir, benchmark_path, check_timeout)
    if benchmark_error and not error:
        error = benchmark_error
    git_diff(variant_dir, diff_path)

    return VariantResult(
        iteration=iteration,
        variant=variant,
        path=variant_dir,
        prompt_path=prompt_path,
        agent_ok=agent_ok,
        tests_ok=tests_ok,
        benchmark_ok=benchmark_ok,
        objective=objective,
        diff_path=diff_path,
        benchmark_path=benchmark_path,
        unittest_log_path=unit_log,
        agent_log_path=agent_log,
        error=error,
    )


def result_to_dict(result: VariantResult) -> dict[str, Any]:
    return {
        "iteration": result.iteration,
        "variant": result.variant,
        "path": str(result.path),
        "promptPath": str(result.prompt_path),
        "agentOk": result.agent_ok,
        "testsOk": result.tests_ok,
        "benchmarkOk": result.benchmark_ok,
        "objective": result.objective,
        "diffPath": str(result.diff_path),
        "benchmarkPath": str(result.benchmark_path),
        "unittestLogPath": str(result.unittest_log_path),
        "agentLogPath": str(result.agent_log_path),
        "error": result.error,
    }


def choose_winner(results: list[VariantResult]) -> VariantResult | None:
    eligible = [result for result in results if result.agent_ok and result.tests_ok and result.benchmark_ok and result.objective is not None]
    if not eligible:
        return None
    return max(eligible, key=lambda result: result.objective if result.objective is not None else float("-inf"))


def write_report(
    *,
    run_dir: Path,
    baseline: dict[str, Any],
    baseline_tests_ok: bool,
    results: list[VariantResult],
    winner: VariantResult | None,
    applied: bool,
) -> Path:
    report_path = run_dir / "report.md"
    lines = [
        "# Ralph ranking optimizer report",
        "",
        f"Run directory: `{run_dir}`",
        f"Baseline tests ok: `{baseline_tests_ok}`",
        f"Baseline objective: `{baseline.get('objective')}`",
        "",
        "| Iteration | Variant | Agent | Tests | Benchmark | Objective | Path |",
        "|---:|---:|---|---|---|---:|---|",
    ]
    for result in results:
        lines.append(
            "| {iteration} | {variant} | {agent} | {tests} | {benchmark} | {objective} | `{path}` |".format(
                iteration=result.iteration,
                variant=result.variant,
                agent="ok" if result.agent_ok else "fail",
                tests="ok" if result.tests_ok else "fail",
                benchmark="ok" if result.benchmark_ok else "fail",
                objective="" if result.objective is None else result.objective,
                path=result.path,
            )
        )
    lines.append("")
    if winner:
        lines.extend(
            [
                f"Winner: iteration {winner.iteration}, variant {winner.variant}",
                f"Winner objective: `{winner.objective}`",
                f"Winner diff: `{winner.diff_path}`",
                f"Applied to real checkout: `{applied}`",
            ]
        )
    else:
        lines.append("Winner: none; no variant passed agent/tests/benchmark gates.")
    lines.append("")
    lines.append("## Failed variant notes")
    for result in results:
        if result.error:
            lines.append(f"- iter {result.iteration} variant {result.variant}: {result.error}")
    lines.append("")
    lines.append("## Next steps")
    lines.append("- Inspect the winning `diff.patch` and `OPTIMIZATION_NOTES.md` before applying or committing.")
    lines.append("- If the benchmark looks overfit, add real exported card snapshots to the benchmark before another loop.")
    write_text(report_path, "\n".join(lines).rstrip() + "\n")
    return report_path


def apply_winner_patch(winner: VariantResult) -> None:
    if winner.diff_path.stat().st_size == 0:
        raise RuntimeError("Winning variant produced an empty diff; nothing to apply.")
    check = run_args(["git", "apply", "--check", str(winner.diff_path)], ROOT, timeout=60)
    if not check.ok:
        raise RuntimeError(f"Winning diff does not apply cleanly:\n{check.combined()}")
    apply = run_args(["git", "apply", str(winner.diff_path)], ROOT, timeout=60)
    if not apply.ok:
        raise RuntimeError(f"Failed to apply winning diff:\n{apply.combined()}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ask Ralph/an agent to invent ranking variants, benchmark them, and compare.",
        epilog=(
            "Examples:\n"
            "  RALPH_CMD=ralph python3 scripts/ralph_optimize_ranking.py\n"
            "  python3 scripts/ralph_optimize_ranking.py --agent-cmd 'ralph {prompt_file}'\n"
            "  python3 scripts/ralph_optimize_ranking.py --agent-cmd 'codex exec --full-auto {prompt}'\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--iterations", type=int, default=1)
    parser.add_argument("--variants", type=int, default=2, help="Variants per iteration.")
    parser.add_argument("--agent-cmd", default=default_agent_cmd(), help="Command line for Ralph/agent. Prompt is sent on stdin unless the command contains {prompt_file} or {prompt}.")
    parser.add_argument("--dry-run", action="store_true", help="Create scratch repos/prompts and benchmark without running an agent.")
    parser.add_argument("--apply-winner", action="store_true", help="Apply the highest-scoring passing variant patch to the real checkout.")
    parser.add_argument("--agent-timeout", type=int, default=1800)
    parser.add_argument("--check-timeout", type=int, default=300)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.iterations <= 0:
        raise SystemExit("--iterations must be positive")
    if args.variants <= 0:
        raise SystemExit("--variants must be positive")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = ROOT / ".tmp" / "ralph-ranking-optimizer" / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)

    baseline_tests = run_shell(UNITTEST, ROOT, timeout=args.check_timeout)
    write_text(run_dir / "baseline-unittest.log", baseline_tests.combined() + "\n")
    baseline_benchmark = run_shell(BENCHMARK, ROOT, timeout=args.check_timeout)
    write_text(run_dir / "baseline-benchmark.json", baseline_benchmark.stdout if baseline_benchmark.stdout else baseline_benchmark.combined() + "\n")
    if not baseline_tests.ok:
        raise SystemExit(f"Baseline tests failed. See {run_dir / 'baseline-unittest.log'}")
    if not baseline_benchmark.ok:
        raise SystemExit(f"Baseline benchmark failed. See {run_dir / 'baseline-benchmark.json'}")
    baseline = read_json(run_dir / "baseline-benchmark.json")
    if not baseline:
        raise SystemExit(f"Baseline benchmark did not emit JSON. See {run_dir / 'baseline-benchmark.json'}")

    results: list[VariantResult] = []
    prior_winner_payload: dict[str, Any] | None = None
    for iteration in range(1, args.iterations + 1):
        for variant in range(1, args.variants + 1):
            result = run_variant(
                run_dir=run_dir,
                iteration=iteration,
                variant=variant,
                baseline=baseline,
                prior_winner=prior_winner_payload,
                agent_cmd=args.agent_cmd,
                dry_run=args.dry_run,
                agent_timeout=args.agent_timeout,
                check_timeout=args.check_timeout,
            )
            results.append(result)
        current_winner = choose_winner(results)
        if current_winner:
            prior_winner_payload = result_to_dict(current_winner)

    winner = choose_winner(results)
    applied = False
    if args.apply_winner:
        if not winner:
            raise SystemExit("--apply-winner was set, but no passing winner exists.")
        apply_winner_patch(winner)
        applied = True

    write_text(
        run_dir / "results.json",
        json.dumps(
            {
                "baseline": baseline,
                "baselineTestsOk": baseline_tests.ok,
                "results": [result_to_dict(result) for result in results],
                "winner": result_to_dict(winner) if winner else None,
                "applied": applied,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    report_path = write_report(
        run_dir=run_dir,
        baseline=baseline,
        baseline_tests_ok=baseline_tests.ok,
        results=results,
        winner=winner,
        applied=applied,
    )

    print(f"Run directory: {run_dir}")
    print(f"Report: {report_path}")
    if winner:
        print(f"Winner: iteration {winner.iteration}, variant {winner.variant}, objective {winner.objective}")
        if not applied:
            print("Winner was not applied. Re-run with --apply-winner after inspecting the diff if you want to apply it.")
    else:
        print("No passing winner found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
