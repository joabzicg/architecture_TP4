#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt


STAT_LINE_RE = re.compile(r"^(?P<name>[^#\s]+)\s+(?P<value>[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\s*(?:#.*)?$")
EXIT_LINE_RE = re.compile(r"^Exiting @ tick \d+ because (?P<cause>.*)$")


def parse_stats_file(stats_path: Path) -> Dict[str, float]:
    data: Dict[str, float] = {}
    if not stats_path.exists():
        return data

    for line in stats_path.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("-"):
            continue
        m = STAT_LINE_RE.match(line)
        if not m:
            continue
        name = m.group("name")
        try:
            value = float(m.group("value"))
        except ValueError:
            continue
        data[name] = value

    return data


def get(d: Dict[str, float], key: str, default: float = float("nan")) -> float:
    return d.get(key, default)


def safe_div(num: float, den: float) -> float:
    if den == 0 or math.isnan(num) or math.isnan(den):
        return float("nan")
    return num / den


@dataclass(frozen=True)
class RunMetrics:
    sim_seconds: float
    sim_insts: float
    num_cycles: float
    ipc: float
    cpi: float

    l1i_miss_rate: float
    l1d_miss_rate: float
    l2_miss_rate: float

    l1i_accesses: float
    l1i_misses: float
    l1d_accesses: float
    l1d_misses: float
    l2_accesses: float
    l2_misses: float

    bp_cond_pred: float
    bp_cond_incorrect: float


def extract_metrics(stats: Dict[str, float]) -> RunMetrics:
    sim_seconds = get(stats, "simSeconds")
    sim_insts = get(stats, "simInsts")
    num_cycles = get(stats, "system.cpu.numCycles")
    ipc = get(stats, "system.cpu.ipc")
    cpi = get(stats, "system.cpu.cpi")

    l1i_miss_rate = get(stats, "system.cpu.icache.overallMissRate::total")
    l1d_miss_rate = get(stats, "system.cpu.dcache.overallMissRate::total")
    l2_miss_rate = get(stats, "system.l2cache.overallMissRate::total")

    l1i_accesses = get(stats, "system.cpu.icache.overallAccesses::total")
    l1i_misses = get(stats, "system.cpu.icache.overallMisses::total")
    l1d_accesses = get(stats, "system.cpu.dcache.overallAccesses::total")
    l1d_misses = get(stats, "system.cpu.dcache.overallMisses::total")
    l2_accesses = get(stats, "system.l2cache.overallAccesses::total")
    l2_misses = get(stats, "system.l2cache.overallMisses::total")

    bp_cond_pred = get(stats, "system.cpu.branchPred.condPredicted")
    bp_cond_incorrect = get(stats, "system.cpu.branchPred.condIncorrect")

    return RunMetrics(
        sim_seconds=sim_seconds,
        sim_insts=sim_insts,
        num_cycles=num_cycles,
        ipc=ipc,
        cpi=cpi,
        l1i_miss_rate=l1i_miss_rate,
        l1d_miss_rate=l1d_miss_rate,
        l2_miss_rate=l2_miss_rate,
        l1i_accesses=l1i_accesses,
        l1i_misses=l1i_misses,
        l1d_accesses=l1d_accesses,
        l1d_misses=l1d_misses,
        l2_accesses=l2_accesses,
        l2_misses=l2_misses,
        bp_cond_pred=bp_cond_pred,
        bp_cond_incorrect=bp_cond_incorrect,
    )


def sum_runs(a: RunMetrics, b: RunMetrics) -> RunMetrics:
    sim_seconds = a.sim_seconds + b.sim_seconds
    sim_insts = a.sim_insts + b.sim_insts
    num_cycles = a.num_cycles + b.num_cycles

    ipc = safe_div(sim_insts, num_cycles)
    cpi = safe_div(num_cycles, sim_insts)

    l1i_accesses = a.l1i_accesses + b.l1i_accesses
    l1i_misses = a.l1i_misses + b.l1i_misses
    l1d_accesses = a.l1d_accesses + b.l1d_accesses
    l1d_misses = a.l1d_misses + b.l1d_misses
    l2_accesses = a.l2_accesses + b.l2_accesses
    l2_misses = a.l2_misses + b.l2_misses

    l1i_miss_rate = safe_div(l1i_misses, l1i_accesses)
    l1d_miss_rate = safe_div(l1d_misses, l1d_accesses)
    l2_miss_rate = safe_div(l2_misses, l2_accesses)

    bp_cond_pred = a.bp_cond_pred + b.bp_cond_pred
    bp_cond_incorrect = a.bp_cond_incorrect + b.bp_cond_incorrect

    return RunMetrics(
        sim_seconds=sim_seconds,
        sim_insts=sim_insts,
        num_cycles=num_cycles,
        ipc=ipc,
        cpi=cpi,
        l1i_miss_rate=l1i_miss_rate,
        l1d_miss_rate=l1d_miss_rate,
        l2_miss_rate=l2_miss_rate,
        l1i_accesses=l1i_accesses,
        l1i_misses=l1i_misses,
        l1d_accesses=l1d_accesses,
        l1d_misses=l1d_misses,
        l2_accesses=l2_accesses,
        l2_misses=l2_misses,
        bp_cond_pred=bp_cond_pred,
        bp_cond_incorrect=bp_cond_incorrect,
    )


def l1_size_to_int_kb(label: str) -> int:
    m = re.fullmatch(r"(\d+)kB", label)
    if not m:
        raise ValueError(f"Unexpected L1 label: {label}")
    return int(m.group(1))


def find_run(base: Path, l1: str, run_name: str) -> Optional[RunMetrics]:
    stats_path = base / f"L1_{l1}" / run_name / "stats.txt"
    stats = parse_stats_file(stats_path)
    if not stats:
        return None
    return extract_metrics(stats)


def read_exit_cause(base: Path, l1: str, run_name: str) -> str:
    simout_path = base / f"L1_{l1}" / run_name / "simout"
    if not simout_path.exists():
        return ""
    cause = ""
    for line in simout_path.read_text(errors="replace").splitlines():
        m = EXIT_LINE_RE.match(line.strip())
        if m:
            cause = m.group("cause").strip()
    return cause


def is_complete_exit(cause: str) -> bool:
    if not cause:
        return False
    lowered = cause.lower()
    if "max instruction count" in lowered:
        return False
    if "user interrupt" in lowered:
        return False
    return True


def plot_series(x_kb: List[int], y: List[float], title: str, ylabel: str, outpath: Path) -> None:
    plt.figure(figsize=(6.0, 3.6))
    plt.plot(x_kb, y, marker="o")
    plt.grid(True, alpha=0.25)
    plt.title(title)
    plt.xlabel("Tamanho L1 (KB)")
    plt.ylabel(ylabel)
    plt.tight_layout()
    outpath.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(outpath, dpi=200)
    plt.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="Collect Q5 A15 results from gem5 stats")
    ap.add_argument(
        "--base",
        default="/home/xfalc/arq/TP4_EX4/m5out/q5/A15",
        help="Base output directory (contains L1_*/<run>/stats.txt)",
    )
    ap.add_argument(
        "--fig-base",
        default="/home/xfalc/arq/TP4_EX4/tex/figs/q5",
        help="Directory to write figures",
    )
    ap.add_argument(
        "--out-csv",
        default="/home/xfalc/arq/TP4_EX4/analysis/q5_a15_results.csv",
        help="CSV output path",
    )
    ap.add_argument(
        "--out-table-tex",
        default="/home/xfalc/arq/TP4_EX4/tex/tables/q5_a15_summary.tex",
        help="LaTeX table output path",
    )
    args = ap.parse_args()

    base = Path(args.base)
    fig_base = Path(args.fig_base)
    out_csv = Path(args.out_csv)
    out_table_tex = Path(args.out_table_tex)

    l1_labels = ["2kB", "4kB", "8kB", "16kB", "32kB"]
    x_kb = [l1_size_to_int_kb(x) for x in l1_labels]

    rows: List[Dict[str, float | str]] = []

    dijkstra: Dict[str, RunMetrics] = {}
    blowfish_enc: Dict[str, RunMetrics] = {}
    blowfish_dec: Dict[str, RunMetrics] = {}
    blowfish_total: Dict[str, RunMetrics] = {}

    exit_cause: Dict[Tuple[str, str], str] = {}

    for l1 in l1_labels:
        d = find_run(base, l1, "dijkstra")
        e = find_run(base, l1, "blowfish_enc")
        de = find_run(base, l1, "blowfish_dec")

        exit_cause[("dijkstra", l1)] = read_exit_cause(base, l1, "dijkstra")
        exit_cause[("blowfish_enc", l1)] = read_exit_cause(base, l1, "blowfish_enc")
        exit_cause[("blowfish_dec", l1)] = read_exit_cause(base, l1, "blowfish_dec")

        if d is not None:
            dijkstra[l1] = d
        if e is not None:
            blowfish_enc[l1] = e
        if de is not None:
            blowfish_dec[l1] = de
        if e is not None and de is not None:
            blowfish_total[l1] = sum_runs(e, de)
            ec = exit_cause[("blowfish_enc", l1)]
            dc = exit_cause[("blowfish_dec", l1)]
            exit_cause[("blowfish_total", l1)] = f"enc: {ec} | dec: {dc}".strip()

    def add_row(app: str, l1: str, m: RunMetrics) -> None:
        cause = exit_cause.get((app, l1), "")
        complete = is_complete_exit(cause)
        if app == "blowfish_total":
            complete = is_complete_exit(exit_cause.get(("blowfish_enc", l1), "")) and is_complete_exit(
                exit_cause.get(("blowfish_dec", l1), "")
            )
        bp_miss_rate = safe_div(m.bp_cond_incorrect, m.bp_cond_pred)
        rows.append(
            {
                "app": app,
                "l1": l1,
                "l1_kb": l1_size_to_int_kb(l1),
                "complete": int(complete),
                "exit_cause": cause,
                "simSeconds": m.sim_seconds,
                "simInsts": m.sim_insts,
                "numCycles": m.num_cycles,
                "ipc": m.ipc,
                "cpi": m.cpi,
                "l1i_miss_rate": m.l1i_miss_rate,
                "l1d_miss_rate": m.l1d_miss_rate,
                "l2_miss_rate": m.l2_miss_rate,
                "bp_cond_miss_rate": bp_miss_rate,
            }
        )

    for l1, m in dijkstra.items():
        add_row("dijkstra", l1, m)
    for l1, m in blowfish_total.items():
        add_row("blowfish_total", l1, m)
    for l1, m in blowfish_enc.items():
        add_row("blowfish_enc", l1, m)
    for l1, m in blowfish_dec.items():
        add_row("blowfish_dec", l1, m)

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="") as f:
        fieldnames = [
            "app",
            "l1",
            "l1_kb",
            "complete",
            "exit_cause",
            "simSeconds",
            "simInsts",
            "numCycles",
            "ipc",
            "cpi",
            "l1i_miss_rate",
            "l1d_miss_rate",
            "l2_miss_rate",
            "bp_cond_miss_rate",
        ]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in sorted(rows, key=lambda r: (str(r["app"]), int(r["l1_kb"]))):
            w.writerow(r)

    def best_l1(app: str) -> Tuple[str, RunMetrics]:
        lookup = {
            "dijkstra": dijkstra,
            "blowfish_total": blowfish_total,
        }[app]
        best: Optional[Tuple[str, RunMetrics]] = None

        candidates: List[str] = []
        for l1 in l1_labels:
            if l1 not in lookup:
                continue
            if app == "blowfish_total":
                ok = is_complete_exit(exit_cause.get(("blowfish_enc", l1), "")) and is_complete_exit(
                    exit_cause.get(("blowfish_dec", l1), "")
                )
            else:
                ok = is_complete_exit(exit_cause.get((app, l1), ""))
            if ok:
                candidates.append(l1)

        if not candidates:
            candidates = [l1 for l1 in l1_labels if l1 in lookup]

        for l1 in candidates:
            m = lookup.get(l1)
            if m is None:
                continue
            if best is None or m.num_cycles < best[1].num_cycles:
                best = (l1, m)
        if best is None:
            raise RuntimeError(f"Missing data for {app}")
        return best

    best_d_l1, best_d = best_l1("dijkstra")
    best_b_l1, best_b = best_l1("blowfish_total")

    out_table_tex.parent.mkdir(parents=True, exist_ok=True)
    with out_table_tex.open("w") as f:
        f.write("% Auto-generated by analysis/q5_collect_a15.py\n")
        f.write("\\begin{tabular}{lrrrrr}\\toprule\n")
        f.write("Aplicacao & L1 (KB) & Ciclos & IPC & MR(IL1) & MR(DL1)\\\\\\midrule\n")
        f.write(
            f"Dijkstra & {l1_size_to_int_kb(best_d_l1)} & {best_d.num_cycles:.0f} & {best_d.ipc:.3f} & {best_d.l1i_miss_rate:.4f} & {best_d.l1d_miss_rate:.4f}\\\\\n"
        )
        f.write(
            f"Blowfish (enc+dec) & {l1_size_to_int_kb(best_b_l1)} & {best_b.num_cycles:.0f} & {best_b.ipc:.3f} & {best_b.l1i_miss_rate:.4f} & {best_b.l1d_miss_rate:.4f}\\\\\n"
        )
        f.write("\\bottomrule\\end{tabular}\n")

    def series(app: str, metric: str) -> List[float]:
        lookup = {
            "dijkstra": dijkstra,
            "blowfish_total": blowfish_total,
        }[app]
        out: List[float] = []
        for l1 in l1_labels:
            m = lookup.get(l1)
            out.append(getattr(m, metric) if m is not None else float("nan"))
        return out

    def series_bp_cond_miss(app: str) -> List[float]:
        lookup = {
            "dijkstra": dijkstra,
            "blowfish_total": blowfish_total,
        }[app]
        out: List[float] = []
        for l1 in l1_labels:
            m = lookup.get(l1)
            if m is None:
                out.append(float("nan"))
            else:
                out.append(safe_div(m.bp_cond_incorrect, m.bp_cond_pred))
        return out

    plot_series(
        x_kb,
        series("dijkstra", "num_cycles"),
        "Dijkstra (A15) - Ciclos vs L1",
        "Ciclos (numCycles)",
        fig_base / "a15_dijkstra_cycles.png",
    )
    plot_series(
        x_kb,
        series("dijkstra", "ipc"),
        "Dijkstra (A15) - IPC vs L1",
        "IPC",
        fig_base / "a15_dijkstra_ipc.png",
    )
    plot_series(
        x_kb,
        series("dijkstra", "l1d_miss_rate"),
        "Dijkstra (A15) - Miss rate DL1 vs L1",
        "Miss rate (DL1)",
        fig_base / "a15_dijkstra_dl1_miss.png",
    )
    plot_series(
        x_kb,
        series("dijkstra", "l1i_miss_rate"),
        "Dijkstra (A15) - Miss rate IL1 vs L1",
        "Miss rate (IL1)",
        fig_base / "a15_dijkstra_il1_miss.png",
    )
    plot_series(
        x_kb,
        series("dijkstra", "l2_miss_rate"),
        "Dijkstra (A15) - Miss rate L2 vs L1",
        "Miss rate (L2)",
        fig_base / "a15_dijkstra_l2_miss.png",
    )
    plot_series(
        x_kb,
        series_bp_cond_miss("dijkstra"),
        "Dijkstra (A15) - Mispred rate (cond) vs L1",
        "Mispred rate (cond)",
        fig_base / "a15_dijkstra_bp_mispred.png",
    )

    plot_series(
        x_kb,
        series("blowfish_total", "num_cycles"),
        "Blowfish (A15) - Ciclos (enc+dec) vs L1",
        "Ciclos (enc+dec)",
        fig_base / "a15_blowfish_cycles.png",
    )
    plot_series(
        x_kb,
        series("blowfish_total", "ipc"),
        "Blowfish (A15) - IPC (enc+dec) vs L1",
        "IPC (enc+dec)",
        fig_base / "a15_blowfish_ipc.png",
    )
    plot_series(
        x_kb,
        series("blowfish_total", "l1d_miss_rate"),
        "Blowfish (A15) - Miss rate DL1 (enc+dec) vs L1",
        "Miss rate (DL1)",
        fig_base / "a15_blowfish_dl1_miss.png",
    )
    plot_series(
        x_kb,
        series("blowfish_total", "l1i_miss_rate"),
        "Blowfish (A15) - Miss rate IL1 (enc+dec) vs L1",
        "Miss rate (IL1)",
        fig_base / "a15_blowfish_il1_miss.png",
    )
    plot_series(
        x_kb,
        series("blowfish_total", "l2_miss_rate"),
        "Blowfish (A15) - Miss rate L2 (enc+dec) vs L1",
        "Miss rate (L2)",
        fig_base / "a15_blowfish_l2_miss.png",
    )
    plot_series(
        x_kb,
        series_bp_cond_miss("blowfish_total"),
        "Blowfish (A15) - Mispred rate (cond) (enc+dec) vs L1",
        "Mispred rate (cond)",
        fig_base / "a15_blowfish_bp_mispred.png",
    )

    print(f"Wrote CSV: {out_csv}")
    print(f"Wrote figures under: {fig_base}")
    print(f"Wrote LaTeX table: {out_table_tex}")


if __name__ == "__main__":
    main()
