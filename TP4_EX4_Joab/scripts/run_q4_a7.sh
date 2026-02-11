#!/usr/bin/env bash
set -euo pipefail

GEM5_BIN=${GEM5_BIN:-/opt/gem5/build/RISCV/gem5.opt}
CFG=${CFG:-/home/xfalc/arq/TP4_EX4/gem5/se_A7_q4.py}
OUT_BASE=${OUT_BASE:-/home/xfalc/arq/TP4_EX4/m5out/q4/A7}
MAXINSTS=${MAXINSTS:-0}
PROGRESS=${PROGRESS:-10}
SKIP_DONE=${SKIP_DONE:-1}
CALIBRATE=${CALIBRATE:-0}

DIJK_DIR=/home/xfalc/arq/TP4_EX4/bench/mibench/network/dijkstra
BLOW_DIR=/home/xfalc/arq/TP4_EX4/bench/mibench/security/blowfish
BIN_DIR=/home/xfalc/arq/TP4_EX4/bench/bin

DEFAULT_SIZES=(1kB 2kB 4kB 8kB 16kB)
if [ -n "${SIZES:-}" ]; then
  # SIZES must be a space-separated list, e.g.: "1kB 2kB 4kB 8kB 16kB" or "16kB".
  read -r -a SIZES_ARR <<< "$SIZES"
else
  SIZES_ARR=("${DEFAULT_SIZES[@]}")
fi

if [ "$CALIBRATE" = "1" ]; then
  # Fast path: run just one size (default 16kB) to estimate runtime and instruction counts.
  if [ -z "${SIZES:-}" ]; then
    SIZES_ARR=(16kB)
  fi
  SKIP_DONE=0
  MAXINSTS=0
fi

mkdir -p "$OUT_BASE"

run_one() {
  local outdir=$1
  shift
  mkdir -p "$outdir"

  if [ "$SKIP_DONE" = "1" ] && [ -s "$outdir/stats.txt" ]; then
    echo "[skip] already done: $outdir"
    return 0
  fi

  # If a previous run left an empty stats file, rerun cleanly.
  if [ -f "$outdir/stats.txt" ] && [ ! -s "$outdir/stats.txt" ]; then
    rm -f "$outdir/stats.txt" "$outdir/simout" "$outdir/simerr" "$outdir/program.out" "$outdir/program.err" || true
  fi

  : > "$outdir/simout"
  echo "[run ] $(date +%T) outdir=$outdir"
  tail -n 20 -f "$outdir/simout" &
  local tail_pid=$!
  local t0=$SECONDS
  set +e
  PYTHONUTF8=1 "$GEM5_BIN" -r -d "$outdir" "$CFG" "$@"
  local rc=$?
  set -e
  kill "$tail_pid" >/dev/null 2>&1 || true
  wait "$tail_pid" >/dev/null 2>&1 || true
  echo "[done] $(date +%T) rc=$rc elapsed=$((SECONDS-t0))s outdir=$outdir"
  return $rc
}

echo "[Q4][A7] gem5: $GEM5_BIN"
echo "[Q4][A7] cfg : $CFG"
echo "[Q4][A7] out : $OUT_BASE"
echo "[Q4][A7] maxinsts: $MAXINSTS"
echo "[Q4][A7] progress: $PROGRESS"
echo "[Q4][A7] skip_done: $SKIP_DONE"
echo "[Q4][A7] sizes: ${SIZES_ARR[*]}"
echo "[Q4][A7] calibrate: $CALIBRATE"

for sz in "${SIZES_ARR[@]}"; do
  echo "\n=== L1=$sz ==="

  # Dijkstra (small)
  run_one "$OUT_BASE/L1_${sz}/dijkstra" \
    --l1 "$sz" \
    --maxinsts "$MAXINSTS" \
    --progress "$PROGRESS" \
    --cmd "$BIN_DIR/dijkstra_small" \
    --options "$DIJK_DIR/input.dat"

  # Blowfish: encryption
  run_one "$OUT_BASE/L1_${sz}/blowfish_enc" \
    --l1 "$sz" \
    --maxinsts "$MAXINSTS" \
    --progress "$PROGRESS" \
    --cmd "$BIN_DIR/bf" \
    --options e "$BLOW_DIR/input_small.asc" "$OUT_BASE/L1_${sz}/blowfish_enc/output_small.enc" 1234567890abcdeffedcba0987654321

  # Blowfish: decryption
  run_one "$OUT_BASE/L1_${sz}/blowfish_dec" \
    --l1 "$sz" \
    --maxinsts "$MAXINSTS" \
    --progress "$PROGRESS" \
    --cmd "$BIN_DIR/bf" \
    --options d "$OUT_BASE/L1_${sz}/blowfish_enc/output_small.enc" "$OUT_BASE/L1_${sz}/blowfish_dec/output_small.asc" 1234567890abcdeffedcba0987654321

done

echo "\nDone. Results in: $OUT_BASE"

if [ "$CALIBRATE" = "1" ]; then
  echo "\n[Q4][A7] Calibration completed. Summary:"
  /home/xfalc/arq/TP4_EX4/analysis/q4_estimate_a7.py --l1 "${SIZES_ARR[0]}" || true
fi