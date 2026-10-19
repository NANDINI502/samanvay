"""Command-line entry point.

    python -m orchestrator.cli "What GFR value suggests kidney disease?"
    MEDBOT_MOCK_LLM=1 python -m orchestrator.cli "..."   # offline, stub replies

Risk-tool inputs as JSON, inline or from a file (cardiac model; renal eGFR and
hepatic FIB-4 calculators):
    python -m orchestrator.cli "..." --values '{"age": 63, "sex": "male", ...}'
    python -m orchestrator.cli "..." --values-file patient.json
    python -m orchestrator.cli --inputs cardiac        # list the inputs a model needs

Health-worker wording (simple language, Hindi/Hinglish, fixed "next step" line):
    python -m orchestrator.cli "..." --audience health_worker --lang hi
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from models.tool import RISK_ORGANS, RiskResult, required_inputs
from orchestrator.audience import AUDIENCES, LANGUAGES
from orchestrator.router import handle_query


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m orchestrator.cli")
    parser.add_argument("question", nargs="*")
    parser.add_argument("--values", help="risk-tool inputs as a JSON object")
    parser.add_argument("--values-file", type=Path, help="JSON file with risk-tool inputs")
    parser.add_argument("--inputs", choices=RISK_ORGANS, help="print the inputs a risk tool needs, then exit")
    parser.add_argument("--audience", choices=AUDIENCES, default="clinician")
    parser.add_argument("--lang", choices=LANGUAGES, default="en", help="health_worker only")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):  # Windows consoles (cp1252) can't print e.g. "√"
        sys.stdout.reconfigure(errors="replace")

    if args.inputs:
        for f in required_inputs(args.inputs):
            if f["kind"] == "categorical":
                extra = f"one of {f['choices']}"
            elif "range" in f:
                extra = f"{f['range'][0]:g}-{f['range'][1]:g}"
            else:
                extra = f"{'>' if f['min_exclusive'] else '>='} {f['min']:g}"
            print(f"  {f['key']:30s} {f['label']}" + (f" [{f['unit']}]" if f["unit"] else "") + f"  ({extra})")
        return
    if not args.question:
        parser.print_usage()
        sys.exit(1)

    values = None
    if args.values_file:
        values = json.loads(args.values_file.read_text(encoding="utf-8"))
    elif args.values:
        values = json.loads(args.values)

    r = handle_query(" ".join(args.question), patient_values=values, audience=args.audience, language=args.lang)
    print(f"Routing: {r.routing_method} -> {r.agents_consulted or '-'}")
    for organ, a in r.agent_answers.items():
        status = f"DEFERRED ({a.defer_kind})" if a.deferred else "answered"
        print(f"  [{organ}] {status}; retrieved: {a.retrieved_headings}")
        if a.risk:
            print(f"      risk tool [{a.risk['status']}]: {RiskResult(**a.risk).summary()}")
    print("\n" + r.final_answer)


if __name__ == "__main__":
    main()
