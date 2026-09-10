from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from .case_memory import CaseBank
from .domain import Scenario
from .engine import MilitaryResearchPipeline
from .baselines import (
    run_fewshot_cot_baseline,
    run_random_search_baseline,
    run_singlepass_memento_baseline,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Memento + Hope military research prototype")
    parser.add_argument("--scenario", default="data/sample_antidrone.json", help="Path to the scenario JSON file.")
    parser.add_argument("--case-bank", default="data/memory_bank.jsonl", help="Path to the military case bank JSONL file.")
    parser.add_argument("--output-dir", default="result/military_research_demo", help="Directory for generated outputs.")
    parser.add_argument("--iterations", type=int, default=3, help="Optimization loop count.")
    parser.add_argument("--seed", type=int, default=7, help="Random seed for Python and PyTorch reproducibility.")
    parser.add_argument("--disable-memory", action="store_true", help="Disable Memento memory retrieval and write-back.")
    parser.add_argument("--disable-hope", action="store_true", help="Disable HOPE fast/slow adaptive weighting.")
    parser.add_argument("--disable-reflection", action="store_true", help="Disable EvoPrompt reflection between iterations.")
    parser.add_argument("--disable-writeback", action="store_true", help="Disable case-bank write-back for fair ablations or frozen evaluations.")
    parser.add_argument("--sim-runs", type=int, default=1, help="Number of simulation runs for Monte Carlo averaging.")
    parser.add_argument("--baseline", choices=["fewshot_cot", "random_search", "singlepass_memento"],
                        help="Run an external baseline instead of the main pipeline.")
    parser.add_argument("--random-candidates", type=int, default=20,
                        help="Number of random candidates for random_search baseline.")
    parser.add_argument("--hope-theta", type=float, default=0.5,
                        help="HOPE SDE reversion coefficient (forgetting rate).")
    parser.add_argument("--hope-epsilon", type=float, default=0.02,
                        help="HOPE SDE noise strength.")

    # ── 快速方案生成模式（Tier 1 / Tier 2 / 单候选 / 规则化反思）──
    parser.add_argument("--single-candidate", action="store_true",
                        help="收敛为单个候选，消除候选竞争带来的多倍 LLM 调用（快速模式）。")
    parser.add_argument("--rule-based-reflection", action="store_true",
                        help="规则化反思：零 LLM 调用，直接由仿真诊断构造反思增量。")
    parser.add_argument("--fast-first", action="store_true",
                        help="Tier 1 应急预案：零 LLM 案例骨架形变，毫秒级出库（--iterations 0 时仅出应急预案）。")
    parser.add_argument("--delta-refine", action="store_true",
                        help="Tier 2 Delta Loop：以应急预案为锚点做局部补丁增量优化，替代全量迭代。")
    parser.add_argument("--delta-max-iters", type=int, default=12,
                        help="Delta Loop 最大迭代轮次（默认 12）。")
    parser.add_argument("--early-stop-ms", type=float, default=0.635,
                        help="Delta Loop 早停质量门限（mission_success，默认 0.635）。")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    scenario_payload = json.loads(Path(args.scenario).read_text(encoding="utf-8"))
    scenario = Scenario.from_dict(scenario_payload)
    rng = random.Random(args.seed)

    if args.baseline:
        result = _run_baseline(args, scenario, rng)
    else:
        pipeline = MilitaryResearchPipeline(args.case_bank, seed=args.seed)
        result = pipeline.run(
            scenario,
            iterations=args.iterations,
            disable_memory=args.disable_memory,
            disable_hope=args.disable_hope,
            disable_reflection=args.disable_reflection,
            sim_runs=args.sim_runs,
            allow_writeback=not args.disable_writeback,
            sde_theta=args.hope_theta,
            sde_epsilon=args.hope_epsilon,
            single_candidate=args.single_candidate,
            rule_based_reflection=args.rule_based_reflection,
            fast_first=args.fast_first,
            delta_refine=args.delta_refine,
            delta_max_iters=args.delta_max_iters,
            early_stop_ms=args.early_stop_ms,
        )
        result.setdefault("experiment_config", {})
        result["experiment_config"]["scenario_path"] = str(Path(args.scenario))
        result["experiment_config"]["output_dir"] = str(Path(args.output_dir))
        pipeline.write_outputs(result, args.output_dir)

    print(
        json.dumps(
            {
                "operation": result["best_plan"]["title"]
                if "best_plan" in result
                else result.get("plan", {}).get("title", "baseline"),
                "seed": args.seed,
                "baseline": args.baseline,
                "mission_success": (
                    result["best_simulation"]["mission_success"]
                    if "best_simulation" in result
                    else result.get("simulation", {}).get("mission_success")
                ),
                "ler": (
                    result["best_simulation"]["ler"]
                    if "best_simulation" in result
                    else result.get("simulation", {}).get("ler")
                ),
                "completion_time_hours": (
                    result["best_simulation"]["completion_time_hours"]
                    if "best_simulation" in result
                    else result.get("simulation", {}).get("completion_time_hours")
                ),
                "overall_effectiveness": (
                    result["best_simulation"]["overall_effectiveness"]
                    if "best_simulation" in result
                    else result.get("simulation", {}).get("overall_effectiveness")
                ),
                "output_dir": args.output_dir,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _run_baseline(args: argparse.Namespace, scenario: Scenario, rng: random.Random) -> dict:
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.baseline == "fewshot_cot":
        raw = run_fewshot_cot_baseline(scenario, rng, sim_runs=args.sim_runs)
    elif args.baseline == "random_search":
        raw = run_random_search_baseline(
            scenario, rng, candidates=args.random_candidates, sim_runs=args.sim_runs
        )
    elif args.baseline == "singlepass_memento":
        bank = CaseBank(args.case_bank)
        raw = run_singlepass_memento_baseline(scenario, bank, rng, sim_runs=args.sim_runs)
    else:
        raise ValueError(f"Unknown baseline: {args.baseline}")

    export = {
        "experiment_config": {
            "baseline": args.baseline,
            "seed": args.seed,
            "sim_runs": args.sim_runs,
            "scenario_path": str(Path(args.scenario)),
            "output_dir": str(out_dir),
        },
        "scenario": scenario.to_dict(),
        "best_plan": raw["plan"],
        "best_simulation": raw["simulation"],
    }
    if args.baseline == "random_search":
        export["random_search"] = {
            "candidates_evaluated": raw.get("candidates_evaluated"),
            "all_candidate_summaries": raw.get("all_candidate_summaries"),
        }
    if args.baseline == "singlepass_memento":
        export["memory_hits"] = raw.get("memory_hits_used", [])

    (out_dir / "full_result.json").write_text(
        json.dumps(export, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return export


if __name__ == "__main__":
    main()
