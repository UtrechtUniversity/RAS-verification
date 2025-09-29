#!/usr/bin/env python3

import sys
import os
import time
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET

NURV_CMD = "/home/okitim/Programs/RV/NuRV-2.0.0-linuxx64/NuRV"


# ── CSV → NuRV XML trace ──────────────────────────────────────────────────
def csv_to_xml(csv_path: str, xml_path: str) -> None:
    root = ET.Element("counter-example",
                      {"type": "0", "id": "1", "desc": "LTL Counterexample"})
    step = 1
    with open(csv_path, "r", encoding="utf-8") as fh:
        for raw in fh:
            parts = raw.rstrip("\n").split(",", 6)
            if len(parts) < 6:
                step += 1
                continue
            node = ET.SubElement(root, "node")
            st   = ET.SubElement(node, "state", {"id": str(step)})
            ET.SubElement(
                st, "value", {"variable": "suturing"}
            ).text = "TRUE" if parts[4].lstrip().startswith("1") else "FALSE"
            ET.SubElement(
                st, "value", {"variable": "gauze"}
            ).text = "TRUE" if parts[5].lstrip().startswith("1") else "FALSE"
            step += 1
    ET.ElementTree(root).write(xml_path,
                               encoding="utf-8",
                               xml_declaration=True)


# ── Build offline.cmd ─────────────────────────────────────────────────────
def make_cmd(trace_xml: str, cmd_path: str) -> None:
    with open(cmd_path, "w") as f:
        f.write("go\n")
        f.write("build_monitor -n 0\n")
        f.write(f"read_trace {trace_xml}\n")
        f.write("verify_property -r -n 0 1\n")
        f.write("quit\n")


# ── Run NuRV & record per‑step latency ────────────────────────────────────
def run_nurv(smv: str, cmd_file: str):
    proc = subprocess.Popen(
        [NURV_CMD, "-quiet", "-source", cmd_file, smv],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    start = None
    last  = None
    max_dt = 0.0
    max_step = None
    first_step = None
    first_time = None

    for line in proc.stdout:
        if start is None and "Trace is stored" in line:
            start = last = time.time()
            continue

        if start is None:
            continue

        m = re.match(r"\s*(\d+),\s*(true|false)", line, re.I)
        if not m:
            continue

        now = time.time()
        dt  = now - last
        last = now
        step = int(m.group(1))

        if dt > max_dt:
            max_dt, max_step = dt, step

        if m.group(2).lower() == "false" and first_step is None:
            first_step = step
            first_time = now - start

    proc.wait()
    total = last - start if start else 0
    return first_step, first_time, total, max_dt, max_step


# ── Main ───────────────────────────────────────────────────────────────────
def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: python monitor_suture_once_past.py <smv_file> <csv_file>")
        sys.exit(1)

    smv_file, csv_file = sys.argv[1], sys.argv[2]
    trace_xml = tempfile.mktemp(suffix=".xml")
    cmd_file  = tempfile.mktemp(suffix=".cmd")

    try:
        csv_to_xml(csv_file, trace_xml)
        make_cmd(trace_xml, cmd_file)
        first_step, first_time, total, max_dt, max_step = run_nurv(
            smv_file, cmd_file)

        print(f"Max per‑step time: {max_dt * 1000:.2f} ms at step {max_step}")
        print(f"▶ NuRV wall‑clock runtime: {total:.3f} s")
        if first_step is None:
            print("✔ No violation found.")
        else:
            print(f"✘ Violation at step {first_step} "
                  f"(wall‑clock time = {first_time:.3f} s)")
    finally:
        for tmp in (trace_xml, cmd_file):
            try:
                os.remove(tmp)
            except OSError:
                pass


if __name__ == "__main__":
    main()
