
import rtamt, sys, time

def monitor_in_camera_view(file_path):
    spec = rtamt.StlDiscreteTimeOnlineSpecificationCpp()
    spec.declare_var('inCameraView', 'int')
    spec.declare_var('out',          'int')
    spec.spec = 'out = historically(inCameraView)'
    spec.parse()
    _spec_update   = spec.update
    _time          = time.time
    _find          = str.find

    start_wall       = _time()
    max_step_time    = 0.0
    max_step_index   = -1
    violation_step   = None
    violation_real   = None

    step_index = 0
    with open(file_path, 'r') as f:
        for raw_line in f:
            t0 = _time()
            line = raw_line.strip()
            if line:
                # fast‑path: skip first 3 commas → char after = tool flag
                comma_cnt = 0
                i = 0
                ln = len(line)
                while i < ln and comma_cnt < 3:
                    if line[i] == ',':
                        comma_cnt += 1
                    i += 1
                while i < ln and line[i] == ' ':
                    i += 1
                in_camera = 1 if (i < ln and line[i] == '1') else 0

                out_rob = _spec_update(step_index, [('inCameraView', in_camera)])

                if out_rob == 0 and violation_step is None:
                    violation_step = step_index
                    violation_real = _time() - start_wall
            step_elapsed = _time() - t0
            if step_elapsed > max_step_time:
                max_step_time, max_step_index = step_elapsed, step_index
            step_index += 1

    total_wall = _time() - start_wall
    print(f'▶ Wall‑clock runtime: {total_wall:.3f} s')
    print(f'⏱ Max per‑step time:  {max_step_time:.6f} s at step {max_step_index}')
    if violation_step is None:
        print('✔ No violation of historically(inCameraView == 1) found.')
    else:
        print(f'✘ Violation at fake‑step {violation_step} '
              f'(wall‑clock {violation_real:.3f} s)')

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Usage: python monitor_one_tool.py <csv_file>')
        sys.exit(1)
    monitor_in_camera_view(sys.argv[1])
