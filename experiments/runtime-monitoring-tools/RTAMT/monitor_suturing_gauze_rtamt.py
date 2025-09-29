
import rtamt, sys, time
_find = str.find
_now  = time.time

FORMULA = (
    'ok = historically( '
    'suturing -> ( once(gauze) -> once( (not gauze) and once(gauze) ) ) '
    ')'
)

def monitor(csv_file: str) -> None:
    spec = rtamt.StlDiscreteTimeOnlineSpecificationCpp()
    spec.declare_var('suturing','int')
    spec.declare_var('gauze',   'int')
    spec.declare_var('ok',      'int')
    spec.spec = FORMULA
    spec.parse()
    _spec_update = spec.update
    _int    = int

    start_wall     = _now()
    max_step_time  = 0.0
    max_step_idx   = -1
    first_violation= None
    step           = 0

    with open(csv_file,'r') as fh:
        for line in fh:
            t0 = _now()
            line = line.rstrip('\n')
            if line:
                # fast: locate 4th and 5th commas to extract columns 5 & 6
                comma_count = 0
                idx = 0
                ln = len(line)
                pos = []  # positions of commas
                while idx < ln and comma_count < 6:
                    if line[idx] == ',':
                        pos.append(idx)
                        comma_count += 1
                    idx += 1
                if len(pos) < 5:
                    step += 1
                    continue
                # start indices of suturing and gauze fields
                sut_start = pos[3] + 1
                gau_start = pos[4] + 1
                # skip spaces
                while sut_start < ln and line[sut_start] == ' ':
                    sut_start += 1
                while gau_start < ln and line[gau_start] == ' ':
                    gau_start += 1
                suturing = 1 if sut_start < ln and line[sut_start] == '1' else 0
                gauze    = 1 if gau_start < ln and line[gau_start] == '1' else 0

                rob = _spec_update(step, [('suturing', suturing),
                                          ('gauze', gauze)])
                if rob < 0 and first_violation is None:
                    first_violation = (step, _now() - start_wall)
            elapsed = _now() - t0
            if elapsed > max_step_time:
                max_step_time, max_step_idx = elapsed, step
            step += 1

    total_wall = _now() - start_wall
    print(f'▶ Wall‑clock runtime: {total_wall:.3f} s')
    print(f'⏱ Max per‑step time:  {max_step_time:.6f} s at step {max_step_idx}')
    if first_violation is None:
        print('✔ Formula held for entire trace.')
    else:
        v_step,v_time = first_violation
        print(f'✘ Violation first detected at fake‑step {v_step} '
              f'(wall‑clock {v_time:.3f} s)')

if __name__ == '__main__':
    if len(sys.argv)!=2:
        print('Usage: python monitor_suturing_gauze.py <csv_file>')
        sys.exit(1)
    monitor(sys.argv[1])
