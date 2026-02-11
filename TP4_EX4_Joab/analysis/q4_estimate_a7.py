#!/usr/bin/env python3

from __future__ import annotations

import re
import argparse
from pathlib import Path
from typing import Optional

BASE = Path("/home/xfalc/arq/TP4_EX4/m5out/q4/A7")
L1_DEFAULT = "16kB"

EXIT_RE = re.compile(r"^Exiting @ tick \d+ because (.*)$")


def tail_exit_cause(simout: Path) -> str:
    if not simout.exists():
        return ""
    cause = ""
    for line in simout.read_text(errors="replace").splitlines():
        m = EXIT_RE.match(line.strip())
        if m:
            cause = m.group(1).strip()
    return cause


def stat_value(stats: Path, key: str) -> Optional[float]:
    if not stats.exists():
        return None
    for line in stats.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("-") or line.startswith("#"):
            continue
        if not line.startswith(key):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        try:
            return float(parts[1])
        except ValueError:
            return None
    return None


def fmt(v: Optional[float], suffix: str = "") -> str:
    if v is None:
        return "?"
    if abs(v) >= 1000 and v.is_integer():
        return f"{int(v)}{suffix}"
    return f"{v:.3f}{suffix}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--l1", default=L1_DEFAULT, help="Tamanho L1 usado na calibração (ex: 16kB)")
    args = ap.parse_args()

    l1 = args.l1
    root = BASE / f"L1_{l1}"

    runs = [
        ("dijkstra", root / "dijkstra"),
        ("blowfish_enc", root / "blowfish_enc"),
        ("blowfish_dec", root / "blowfish_dec"),
    ]

    print(f"- L1 usado para estimativa: {l1}")

    total_host_s = 0.0
    total_host_known = True
    max_sim_insts = 0.0

    for name, d in runs:
        stats = d / "stats.txt"
        simout = d / "simout"

        sim_insts = stat_value(stats, "simInsts")
        host_s = stat_value(stats, "hostSeconds")
        inst_rate = stat_value(stats, "hostInstRate")
        exit_cause = tail_exit_cause(simout)

        if host_s is None:
            total_host_known = False
        else:
            total_host_s += host_s

        if sim_insts is not None:
            max_sim_insts = max(max_sim_insts, sim_insts)

        print(
            f"- {name}: simInsts={fmt(sim_insts)} hostSeconds={fmt(host_s, 's')} hostInstRate={fmt(inst_rate)} exit='{exit_cause or '?'}'"
        )

    # Suggest a safe MAXINSTS (10% slack), if simInsts is known.
    if max_sim_insts > 0:
        suggested = int(max_sim_insts * 1.10) + 1
        print(f"- MAXINSTS sugerido (seguro, +10%): {suggested}")

    if total_host_known:
        # Full sweep = 5 L1 sizes * (1 dijkstra + 2 blowfish) = 15 runs.
        # Small L1 tends to be slower; add a conservative factor.
        base_runs = 15
        factor = 1.4
        est = total_host_s * base_runs / 3.0 * factor
        print(f"- Estimativa sweep completo (5 tamanhos, 15 runs): ~{est/60.0:.1f} min (fator {factor}x)")
        print("  (isso é uma estimativa: a variação de cache muda ciclos e wall-time do gem5)")


if __name__ == "__main__":
    main()
