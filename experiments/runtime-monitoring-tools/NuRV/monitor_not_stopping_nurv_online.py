
import sys
import time
from omniORB import CORBA, any
import Monitor
import CosNaming


# ──────────────────────────────────────────────────────────────────────────
# Fast CSV → observation converter  (C-level split, no per-row strip/format)
# ──────────────────────────────────────────────────────────────────────────
def csv_to_state(line: str) -> str:
    parts = line.split(",", 3)
    if len(parts) < 3:
        return ""
    try:
        x = int(parts[0])
        y = int(parts[1])
        z = int(parts[2])
    except ValueError:
        return ""
    return f"x = {x} & y = {y} & z = {z}"


# ──────────────────────────────────────────────────────────────────────────
def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: python monitor_not_stopping_nurv_online.py "
              "-ORBInitRef NameService=IOR:<IOR> <csv_file>")
        sys.exit(1)

    orb_args, csv_file = sys.argv[1:-1], sys.argv[-1]

    # ── CORBA bind ───────────────────────────────────────────────────────
    orb   = CORBA.ORB_init(orb_args, CORBA.ORB_ID)
    root  = orb.resolve_initial_references("NameService") \
               ._narrow(CosNaming.NamingContext)
    name  = [
        CosNaming.NameComponent("NuRV", ""),
        CosNaming.NameComponent("Monitor", ""),
        CosNaming.NameComponent("Service", "")
    ]
    svc   = root.resolve(name)._narrow(Monitor.MonitorService)

    hb    = svc.heartbeat            # local alias (saves attr-lookups)
    prop0 = any.to_any(0)
    svc.reset(prop0, True)           # property index 0

    # ── timing and violation tracking ───────────────────────────────────
    start_wall = None
    end_wall   = None
    viol_step  = None
    viol_time  = None
    step_idx   = 1
    max_dt    = 0.0
    max_step  = None

    with open(csv_file, "r", encoding="utf-8") as fh:
        for raw in fh:
            state = csv_to_state(raw.rstrip("\n"))
            if not state:
                step_idx += 1
                continue

            if start_wall is None:
                start_wall = time.time()   # timer starts *right before* 1st hb

            t0=time.time()
            verdict = hb(prop0, state)
            t1=time.time()
            dt = t1 - t0
            if dt > max_dt:
                max_dt = dt
                max_step = step_idx
            end_wall = t1         # updated after *each* heartbeat

            if verdict == Monitor.RV_False and viol_step is None:
                viol_step = step_idx
                viol_time = end_wall - start_wall

            step_idx += 1

    total_wall = 0 if start_wall is None else end_wall - start_wall
    print(f"Max per-step time: {max_dt*1000:.2f} ms at step {max_step}")
    print(f"▶ Python wall-clock runtime: {total_wall:.3f} s")
    if viol_step is None:
        print("✔ No violation of not stopping for 100 steps found.")
    else:
        print(f"✘ Violation at step {viol_step} "
              f"(wall-clock time = {viol_time:.3f} s)")


if __name__ == "__main__":
    main()