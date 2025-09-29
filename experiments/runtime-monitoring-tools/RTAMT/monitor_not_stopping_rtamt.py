
import rtamt, sys, time
_find   = str.find
_int    = int
_now    = time.time

# ---- build the gigantic STL formula ----------------------------------------
def nested_prev(var: str, k: int) -> str:
    expr = var
    for _ in range(k):
        expr = f'prev({expr})'
    return expr

def build_freeze_clause(var: str, window: int = 99) -> str:
    terms = [f'({var} == {nested_prev(var, k)})' for k in range(1, window + 1)]
    return ' and '.join(terms)

WINDOW = 99
freeze_x = build_freeze_clause('x', WINDOW)
freeze_y = build_freeze_clause('y', WINDOW)
freeze_z = build_freeze_clause('z', WINDOW)

SPEC_FORMULA = f'safe = historically( not( ({freeze_x}) and ({freeze_y}) and ({freeze_z}) ) )'

def monitor(csv_path: str) -> None:
    spec = rtamt.StlDiscreteTimeOnlineSpecificationCpp()
    for v in ('x','y','z'):
        spec.declare_var(v,'int')
    spec.declare_var('safe','int')
    spec.spec = SPEC_FORMULA
    spec.parse()
    _spec_update = spec.update
    _now_time    = _now

    start_wall = _now_time()
    max_step_time = 0.0
    max_step_idx  = -1
    first_violation = None
    step = 0

    with open(csv_path,'r') as fh:
        for line in fh:
            t0 = _now_time()
            line = line.rstrip('\n')
            if line:
                i1 = _find(line, ',')
                i2 = _find(line, ',', i1+1)
                i3 = _find(line, ',', i2+1)
                try:
                    x = _int(line[:i1].strip())
                    y = _int(line[i1+1:i2].strip())
                    z = _int(line[i2+1:i3].strip())
                except ValueError:
                    step += 1
                    continue
                rob = _spec_update(step, [('x',x),('y',y),('z',z)])
                if rob <= 0 and step>=WINDOW and first_violation is None:
                    first_violation = (step, _now_time() - start_wall)
            elapsed = _now_time() - t0
            if elapsed > max_step_time:
                max_step_time, max_step_idx = elapsed, step
            step += 1

    total_wall = _now_time() - start_wall
    print(f'▶ Wall‑clock runtime: {total_wall:.3f} s')
    print(f'⏱ Max per‑step time:  {max_step_time:.6f} s at step {max_step_idx}')
    if first_violation is None:
        print('✔ Tool never remained motionless for 100 consecutive steps.')
    else:
        v_step,v_time = first_violation
        print(f'✘ Tool froze ≥100 steps starting at fake‑step {v_step} '
              f'(wall‑clock {v_time:.3f} s)')

if __name__ == '__main__':
    if len(sys.argv)!=2:
        print('Usage: python monitor_not_stopping.py <csv_file>')
        sys.exit(1)
    monitor(sys.argv[1])
