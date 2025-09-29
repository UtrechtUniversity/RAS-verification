#!/usr/bin/env python3

import sys, time
from omniORB import CORBA, any
import Monitor, CosNaming

def build_state(parts):
    return ("suturing" if parts[4].strip().startswith("1") else "!suturing") + " & " +            ("gauze" if parts[5].strip().startswith("1") else "!gauze")

def main():
    if len(sys.argv)<3:
        print("Usage: python monitor_suture_once_online.py -ORBInitRef NameService=IOR:<IOR> <csv>")
        sys.exit(1)
    orb_args, csv_file = sys.argv[1:-1], sys.argv[-1]
    orb = CORBA.ORB_init(orb_args, CORBA.ORB_ID)
    root= orb.resolve_initial_references("NameService")._narrow(CosNaming.NamingContext)
    name=[CosNaming.NameComponent("NuRV",""),CosNaming.NameComponent("Monitor",""),CosNaming.NameComponent("Service","")]
    svc = root.resolve(name)._narrow(Monitor.MonitorService)
    prop0= any.to_any(0)
    svc.reset(prop0,True)
    hb = svc.heartbeat
    start=None; end=None
    viol_step=None; viol_time=None
    max_dt=0.0; max_step=None
    step=1
    with open(csv_file) as fh:
        for raw in fh:
            parts = raw.rstrip("\n").split(',',6)
            if len(parts)<6:
                step+=1; continue
            state = build_state(parts)
            if start is None:
                start=time.time()
            t0=time.time()
            verdict = hb(prop0,state)
            t1=time.time()
            dt=t1-t0
            if dt>max_dt: max_dt=dt; max_step=step
            end=t1
            if verdict==Monitor.RV_False and viol_step is None:
                viol_step=step; viol_time=end-start
            step+=1
    total=end-start if start else 0
    print(f"▶ Python wall-clock runtime: {total:.3f} s")
    print(f"Max per-step time: {max_dt*1000:.2f} ms at step {max_step}")
    if viol_step is None:
        print("✔ No violation found.")
    else:
        print(f"✘ Violation at step {viol_step} (wall-clock time = {viol_time:.3f} s)")
if __name__=='__main__':
    main()
