"""Operator Mode: authorized attack-path planning for security research.

The orchestrator plans and executes bounded reconnaissance and vulnerability-analysis
steps, records an attack graph, and requires approval for destructive or interactive
actions unless ``FORGE_OPERATOR_AUTO_APPROVE=true`` is explicitly set.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import sys

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

LOG_DIR = Path.home() / ".forge" / "logs" / "operator_mode"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)
if not logger.handlers:
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    file_handler = logging.FileHandler(LOG_DIR / f"operator_mode_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)


class PhaseType(str, Enum):
    """Attack phase types."""

    RECONNAISSANCE = "reconnaissance"
    ENUMERATION = "enumeration"
    VULNERABILITY_ANALYSIS = "vulnerability_analysis"
    EXPLOITATION = "exploitation"
    REPORTING = "reporting"


class ToolType(str, Enum):
    """Tool categories for attack planning."""

    RECON = "recon"
    DESTRUCTIVE = "destructive"
    INTERACTIVE = "interactive"


@dataclass
class AttackStep:
    """Single step in the attack graph."""

    step_id: str
    phase: PhaseType
    tool_name: str
    tool_type: ToolType
    parameters: dict[str, Any]
    rationale: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    findings: dict[str, Any] = field(default_factory=dict)
    next_steps_possible: list[str] = field(default_factory=list)
    chosen_next_step: str | None = None
    human_approved: bool = False
    executed: bool = False
    result: dict[str, Any] | None = None
    error: str | None = None
    score: float = 0.0
    mcts_visits: int = 0
    mcts_value: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to a JSON-serializable graph node."""
        return {
            "step_id": self.step_id,
            "phase": self.phase.value,
            "tool_name": self.tool_name,
            "tool_type": self.tool_type.value,
            "parameters": self.parameters,
            "rationale": self.rationale,
            "timestamp": self.timestamp,
            "findings": self.findings,
            "next_steps_possible": self.next_steps_possible,
            "chosen_next_step": self.chosen_next_step,
            "human_approved": self.human_approved,
            "executed": self.executed,
            "result": self.result,
            "error": self.error,
            "score": self.score,
            "mcts_visits": self.mcts_visits,
            "mcts_value": self.mcts_value,
        }


@dataclass
class MCTSNode:
    """Node used by the bounded MCTS planner."""

    step: AttackStep | None
    parent: MCTSNode | None = None
    children: list[MCTSNode] = field(default_factory=list)
    visits: int = 0
    value: float = 0.0

    def ucb1(self, exploration: float = 1.414) -> float:
        if self.visits == 0:
            return float("inf")
        parent_visits = max(1, self.parent.visits if self.parent else 1)
        return (self.value / self.visits) + exploration * math.sqrt(math.log(parent_visits) / self.visits)


ToolExecutor = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]
ApprovalCallback = Callable[[AttackStep], Awaitable[bool] | bool]
LLMCallback = Callable[[str], Awaitable[str]]


class OperatorMode:
    """Authorized attack-path planning and execution orchestrator."""

    RECON_TOOLS = {"recon_nmap_scan", "recon_web_tech", "recon_dir_bruteforce", "recon_dns_enum", "recon_whois", "recon_subdomain_enum"}
    INTERACTIVE_TOOLS = {"exploit_hydra", "post_loot_collect", "post_pivot_scan"}

    def __init__(
        self,
        target: str,
        llm_callback: LLMCallback | None = None,
        max_steps: int = 20,
        beam_width: int = 3,
        mcts_simulations: int = 10,
        tool_executor: ToolExecutor | None = None,
        approval_callback: ApprovalCallback | None = None,
    ):
        self.target = target
        self.llm_callback = llm_callback
        self.max_steps = max(1, max_steps)
        self.beam_width = max(1, beam_width)
        self.mcts_simulations = max(1, mcts_simulations)
        self.tool_executor = tool_executor
        self.approval_callback = approval_callback
        self.auto_approve = os.environ.get("FORGE_OPERATOR_AUTO_APPROVE", "").strip().lower() in {"1", "true", "yes", "on"}

        self.attack_graph: dict[str, AttackStep] = {}
        self.phase = PhaseType.RECONNAISSANCE
        self.findings_summary: dict[str, Any] = {}
        self.decisions: list[dict[str, Any]] = []
        self.step_counter = 0
        logger.info("Operator Mode initialized for target: %s", target)

    def _generate_step_id(self) -> str:
        self.step_counter += 1
        return f"step_{self.step_counter:03d}_{int(time.time() * 1000) % 10000}"

    async def _query_llm_for_next_steps(self, context: str) -> list[dict[str, Any]]:
        if not self.llm_callback:
            return self._heuristic_planning(context)
        prompt = f"""Based on these authorized security findings, suggest the next bounded assessment steps.
Target: {self.target}
Current Phase: {self.phase.value}
Findings: {context}
Return JSON array of objects with tool_name, parameters, rationale."""
        try:
            response = await self.llm_callback(prompt)
            parsed = json.loads(response)
            if isinstance(parsed, list):
                return [item for item in parsed if isinstance(item, dict)][: self.beam_width * 2]
        except Exception as exc:
            logger.error("LLM planning failed: %s", exc)
        return self._heuristic_planning(context)

    def _heuristic_planning(self, _context: str) -> list[dict[str, Any]]:
        http_url = self.target if self.target.startswith(("http://", "https://")) else f"http://{self.target}"
        plans = {
            PhaseType.RECONNAISSANCE: [
                ("recon_nmap_scan", {"target": self.target, "scan_type": "quick"}),
                ("recon_dns_enum", {"domain": self.target}),
                ("recon_whois", {"target": self.target}),
            ],
            PhaseType.ENUMERATION: [
                ("recon_nmap_scan", {"target": self.target, "scan_type": "service"}),
                ("recon_web_tech", {"url": http_url}),
                ("recon_dir_bruteforce", {"url": http_url, "wordlist": "common"}),
            ],
            PhaseType.VULNERABILITY_ANALYSIS: [
                ("exploit_search_sploit", {"query": self.target}),
                ("exploit_nuclei_scan", {"target": self.target, "severity": "medium"}),
                ("exploit_sqlmap_test", {"url": http_url}),
            ],
            PhaseType.EXPLOITATION: [],
        }
        return [
            {"tool_name": name, "parameters": params, "rationale": f"Standard {self.phase.value} assessment step"}
            for name, params in plans.get(self.phase, [])
        ]

    def _tool_type(self, tool_name: str) -> ToolType:
        if tool_name in self.RECON_TOOLS or tool_name.startswith("recon_") or tool_name in {"exploit_search_sploit"}:
            return ToolType.RECON
        if tool_name in self.INTERACTIVE_TOOLS:
            return ToolType.INTERACTIVE
        return ToolType.DESTRUCTIVE

    def _extract_findings(self, result: dict[str, Any]) -> dict[str, Any]:
        findings: dict[str, Any] = {}
        ports = result.get("open_ports")
        if isinstance(ports, list):
            findings["open_ports"] = ports
            findings["ports"] = [item.get("port") for item in ports if isinstance(item, dict) and item.get("port")]
            findings["services"] = [item.get("service") for item in ports if isinstance(item, dict) and item.get("service")]
        for key in ("technologies", "directories_found", "subdomains", "exploits", "findings"):
            value = result.get(key)
            if value:
                findings[key] = value
        if result.get("vulnerable") is True:
            findings["vulnerabilities"] = [{k: result.get(k) for k in ("technique", "payload", "database") if result.get(k)}]
        return findings

    def _score_result(self, result: dict[str, Any]) -> float:
        findings = self._extract_findings(result)
        open_ports = findings.get("open_ports", [])
        services = findings.get("services", [])
        vulns = findings.get("vulnerabilities", []) or findings.get("findings", []) or findings.get("exploits", [])
        return float(len(open_ports) * 3 + len(set(services)) * 2 + len(vulns) * 10 + len(findings))

    def _score_candidate(self, step: AttackStep) -> float:
        historical_score = 0.0
        for result in self.findings_summary.values():
            if isinstance(result, dict):
                historical_score += self._score_result(result)
        phase_bias = {
            PhaseType.RECONNAISSANCE: 4.0 if step.tool_type == ToolType.RECON else 0.0,
            PhaseType.ENUMERATION: 2.0 if step.tool_name in {"recon_nmap_scan", "recon_web_tech"} else 1.0,
            PhaseType.VULNERABILITY_ANALYSIS: 4.0 if step.tool_name.startswith("exploit_") else 1.0,
            PhaseType.EXPLOITATION: 0.5,
            PhaseType.REPORTING: 0.0,
        }[step.phase]
        return phase_bias + historical_score * 0.05 + random.random() * 0.01

    def _beam_search_top_paths(self, candidates: list[AttackStep]) -> list[AttackStep]:
        """Keep top beam_width candidates by observed ports, services, and vulnerabilities."""
        for step in candidates:
            step.score = self._score_candidate(step)
        selected = sorted(candidates, key=lambda item: item.score, reverse=True)[: self.beam_width]
        self.decisions.append(
            {
                "algorithm": "beam_search",
                "phase": self.phase.value,
                "beam_width": self.beam_width,
                "selected": [step.step_id for step in selected],
                "scores": {step.step_id: step.score for step in candidates},
            }
        )
        return selected

    def _simulate_tool_outcome(self, step: AttackStep) -> float:
        tool_rewards = {
            "recon_nmap_scan": 0.70,
            "recon_web_tech": 0.55,
            "recon_dir_bruteforce": 0.45,
            "recon_dns_enum": 0.40,
            "recon_whois": 0.25,
            "recon_subdomain_enum": 0.50,
            "exploit_search_sploit": 0.55,
            "exploit_nuclei_scan": 0.70,
            "exploit_sqlmap_test": 0.35,
        }
        known_services = json.dumps(self.findings_summary).lower()
        reward = tool_rewards.get(step.tool_name, 0.25)
        if step.tool_name in {"recon_web_tech", "recon_dir_bruteforce", "exploit_sqlmap_test"} and any(s in known_services for s in ["http", "https", "apache", "nginx"]):
            reward += 0.20
        if step.tool_type != ToolType.RECON:
            reward -= 0.10
        return max(0.0, min(1.0, reward + random.uniform(-0.05, 0.05)))

    def _mcts_select(self, root: MCTSNode) -> MCTSNode:
        node = root
        while node.children:
            node = max(node.children, key=lambda child: child.ucb1())
        return node

    def _mcts_expand(self, node: MCTSNode, candidates: list[AttackStep]) -> MCTSNode:
        existing = {child.step.step_id for child in node.children if child.step}
        unexplored = [step for step in candidates if step.step_id not in existing]
        if not unexplored:
            return node
        child = MCTSNode(step=random.choice(unexplored), parent=node)
        node.children.append(child)
        return child

    def _mcts_backpropagate(self, node: MCTSNode, reward: float) -> None:
        current: MCTSNode | None = node
        while current:
            current.visits += 1
            current.value += reward
            if current.step:
                current.step.mcts_visits = current.visits
                current.step.mcts_value = current.value
                current.step.score = current.value / max(1, current.visits)
            current = current.parent

    def _mcts_plan(self, candidates: list[AttackStep]) -> list[AttackStep]:
        root = MCTSNode(step=None)
        for step in candidates:
            root.children.append(MCTSNode(step=step, parent=root))
        for _ in range(self.mcts_simulations):
            selected = self._mcts_select(root)
            expanded = self._mcts_expand(selected, candidates)
            if not expanded.step:
                continue
            reward = self._simulate_tool_outcome(expanded.step)
            self._mcts_backpropagate(expanded, reward)
        ranked = sorted(candidates, key=lambda step: step.score, reverse=True)[: self.beam_width]
        self.decisions.append(
            {
                "algorithm": "mcts",
                "phase": self.phase.value,
                "simulations": self.mcts_simulations,
                "selected": [step.step_id for step in ranked],
                "scores": {step.step_id: step.score for step in candidates},
            }
        )
        return ranked

    async def _plan_next_steps(self) -> list[AttackStep]:
        context = json.dumps(self.findings_summary, indent=2, default=str)
        proposed = await self._query_llm_for_next_steps(context)
        candidates: list[AttackStep] = []
        seen: set[tuple[str, str]] = set()
        for step_dict in proposed:
            tool_name = str(step_dict.get("tool_name", "")).strip()
            if not tool_name:
                continue
            parameters = step_dict.get("parameters", {}) if isinstance(step_dict.get("parameters", {}), dict) else {}
            key = (tool_name, json.dumps(parameters, sort_keys=True, default=str))
            if key in seen:
                continue
            seen.add(key)
            step = AttackStep(
                step_id=self._generate_step_id(),
                phase=self.phase,
                tool_name=tool_name,
                tool_type=self._tool_type(tool_name),
                parameters=parameters,
                rationale=str(step_dict.get("rationale", "")),
            )
            step.human_approved = step.tool_type == ToolType.RECON
            self.attack_graph[step.step_id] = step
            candidates.append(step)
        if not candidates:
            return []
        if self.phase == PhaseType.ENUMERATION:
            return self._beam_search_top_paths(candidates)
        return self._mcts_plan(candidates)

    async def _request_human_approval(self, step: AttackStep) -> bool:
        if step.tool_type == ToolType.RECON:
            return True
        if self.auto_approve:
            logger.warning("FORGE_OPERATOR_AUTO_APPROVE=true: approving %s (%s)", step.step_id, step.tool_name)
            return True
        if self.approval_callback:
            result = self.approval_callback(step)
            return bool(await result) if asyncio.iscoroutine(result) else bool(result)
        logger.warning("Human approval required for %s (%s). Defaulting to denied in non-interactive mode.", step.step_id, step.tool_name)
        return False

    async def _execute_step(self, step: AttackStep) -> None:
        if not self.tool_executor:
            step.error = "No tool executor configured for OperatorMode"
            step.result = {"status": "error", "error": step.error}
            logger.error(step.error)
            return
        try:
            result = await self.tool_executor(step.tool_name, step.parameters)
        except Exception as exc:
            result = {"status": "error", "error": str(exc)}
        step.result = result
        step.findings = self._extract_findings(result)
        step.score = self._score_result(result)
        step.error = result.get("error") or result.get("stderr") if result.get("status") == "error" else None
        self.findings_summary[step.step_id] = {
            "tool_name": step.tool_name,
            "parameters": step.parameters,
            "findings": step.findings,
            "score": step.score,
            "result": result,
        }

    async def run(self) -> dict[str, Any]:
        logger.info("Starting Operator Mode for target: %s", self.target)
        phases = [PhaseType.RECONNAISSANCE, PhaseType.ENUMERATION, PhaseType.VULNERABILITY_ANALYSIS, PhaseType.EXPLOITATION]
        for phase in phases:
            if self.step_counter >= self.max_steps:
                break
            self.phase = phase
            next_steps = await self._plan_next_steps()
            if not next_steps:
                continue
            for step in next_steps:
                if self.step_counter > self.max_steps:
                    break
                step.human_approved = await self._request_human_approval(step)
                if not step.human_approved:
                    self.decisions.append({"algorithm": "approval", "step_id": step.step_id, "approved": False})
                    continue
                logger.info("Executing %s: %s", step.step_id, step.tool_name)
                await self._execute_step(step)
                step.executed = True
        return await self._generate_report()

    async def _generate_report(self) -> dict[str, Any]:
        report = {
            "target": self.target,
            "timestamp": datetime.now().isoformat(),
            "total_steps": len(self.attack_graph),
            "executed_steps": sum(1 for step in self.attack_graph.values() if step.executed),
            "findings_count": len(self.findings_summary),
            "attack_graph": {sid: step.to_dict() for sid, step in self.attack_graph.items()},
            "decisions": self.decisions,
            "summary_findings": self.findings_summary,
            "markdown_report": self._generate_markdown_report(),
        }
        report_file = LOG_DIR / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_file.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        logger.info("Report saved to %s", report_file)
        return report

    def export_attack_graph_json(self) -> str:
        return json.dumps({sid: step.to_dict() for sid, step in self.attack_graph.items()}, indent=2, default=str)

    def _generate_markdown_report(self) -> str:
        md = f"""# Operator Mode Attack Report

**Target**: {self.target}
**Date**: {datetime.now().isoformat()}
**Total Steps**: {len(self.attack_graph)}
**Executed Steps**: {sum(1 for step in self.attack_graph.values() if step.executed)}
**Findings**: {len(self.findings_summary)}

## Executive Summary

Authorized attack-path planning completed for {self.target}. Review every finding manually before taking action.

## Attack Path
"""
        for step_id, step in sorted(self.attack_graph.items()):
            md += f"\n### {step_id}: {step.tool_name}\n"
            md += f"- **Phase**: {step.phase.value}\n"
            md += f"- **Type**: {step.tool_type.value}\n"
            md += f"- **Executed**: {step.executed}\n"
            md += f"- **Approved**: {step.human_approved}\n"
            md += f"- **Score**: {step.score:.2f}\n"
            md += f"- **Rationale**: {step.rationale}\n"
            md += f"- **Parameters**: {json.dumps(step.parameters, default=str)}\n"
            if step.findings:
                md += f"- **Findings**: `{json.dumps(step.findings, default=str)}`\n"
            if step.error:
                md += f"- **Error**: {step.error}\n"
        md += """

## Recommendations

1. Verify all automated findings manually.
2. Prioritize validated vulnerabilities by severity and exploitability.
3. Keep evidence, timestamps, and tool output with the engagement record.
4. Do not run destructive or interactive actions outside a written authorization scope.

---
*Report generated by Forge-AI Operator Mode*
"""
        return md


_OPERATOR_REPORTS: dict[str, dict[str, Any]] = {}


async def operator_mode_start(target: str, max_steps: int = 20) -> dict[str, Any]:
    """Start Operator Mode without an external tool executor.

    The pentest MCP server supplies a concrete executor when it registers this
    workflow. Direct use returns a planning report and records missing-executor
    errors instead of fabricating findings.
    """
    operator = OperatorMode(target, max_steps=max_steps)
    report = await operator.run()
    _OPERATOR_REPORTS[target] = report
    return {"status": "ok", "report": report}


async def operator_mode_get_attack_graph(target: str) -> dict[str, Any]:
    """Retrieve the most recent in-memory attack graph for a target."""
    report = _OPERATOR_REPORTS.get(target)
    return {"status": "ok", "target": target, "graph": report.get("attack_graph", {}) if report else {}}


if __name__ == "__main__":
    async def example() -> None:
        operator = OperatorMode("192.168.1.100")
        report = await operator.run()
        print(json.dumps(report, indent=2, default=str))

    asyncio.run(example())
