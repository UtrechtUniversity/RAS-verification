# NuRV‑based Run‑Time Monitoring Using the da Vinci Surgical System (Linux)

This repository contains a **minimal, NuRV‑centric** prototype that evaluates the LTL safety property
`G(inCameraView)` online while a surgical procedure is underway. A lightweight script
monitors wheter at least one of the **several instruments** is in camera view; this is streamed to the
NuRV monitor via CORBA heartbeats.

> **Repository scope:**
>
> - `run_experiment.py` — end‑to‑end Python client (video device → instrument presence → NuRV heartbeat → logging)  
> - `MetaFormer.py` — model definition used for instrument segmentation  
> - `CAFormerS18_RAMIE_SurgeNet.pth` — weights file
>
> No other files or tools are included here. The emphasis is on **NuRV runtime monitoring**; the
> segmentation part supplies propositions to the monitor.

---

## What the client does (high level)

1. **Reads a video device** that provides the da Vinci Surgical System (dVSS) console output.  
   *Do not change device index unless your system enumerates a different `/dev/video*`.*
2. **Segments** each frame and derives a 4‑bit instrument‑presence vector for **hook, forceps, suction & irrigation, vessel sealer**.
3. Computes the Boolean proposition **`inCameraView`** as “at least one of the tracked instruments is present in the current frame” and sends either `"inCameraView"` or `"!inCameraView"` to NuRV via `Monitor.MonitorService.heartbeat(...)`.
4. **Logs** each step to `./logs/rv_run_YYYYMMDD_HHMMSS.log` with columns:  
   `state, tools vector, inCameraView, G(inCameraView), time since previous step [s], FPS`.


---

## System & dependencies (Linux only)

This prototype was **used and verified on Linux** during intraoperative experiments.

### Python environment
- Python 3.10–3.12
- `torch`, `torchvision` (CUDA optional), `opencv-python`, `pillow`, `numpy`, `timm`
- `omniORB` (Python bindings) for the CORBA client

Create a virtual environment and install:
```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip

# Choose ONE PyTorch build (example wheels shown):
# CUDA 12.1:
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
# or CPU-only:
# pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

pip install opencv-python pillow numpy timm omniORB
```

### System packages for omniORB (Name Service)
```bash
sudo apt-get update
sudo apt-get install -y omniidl omniorb omniorb-nameserver python3-omniorb
```

> **Monitor stubs.** This repo assumes the **NuRV Monitor** Python stubs (`Monitor` module) are available on your `PYTHONPATH` from your NuRV installation. If `import Monitor` fails, generate stubs from your `Monitor.idl` and add them to `PYTHONPATH` (see Troubleshooting → Import/IDL).

---

## Configuration

In `run_experiment.py`:

- **Weights path:** set `weights_path = "CAFormerS18_RAMIE_SurgeNet.pth"` (same directory).  
- **Device selection:** the script auto‑selects `cuda:0` when available, otherwise CPU.
- **Instrument set & threshold:** classes **8..11** correspond to the four instruments above.
  We declare an instrument **present** if its pixel count exceeds **T = 50** (empirically stable).  
  The 4‑bit vector is logged and used to compute `inCameraView`.

---

## Running the experiment

### 1) Start the omniORB Name Service and NuRV monitor (server side)

1. Launch omniORB Name Service:
   ```bash
   omniNames -start -logdir ./omniorb_logs
   # default port 2809; note the IOR printed at startup
   ```
2. Start your NuRV monitor and **register it** under the exact path:
   ```
   NuRV / Monitor / Service
   ```

### 2) Run the Python client (this repo)

From the directory containing the three files:
```bash
python run_experiment.py -ORBInitRef NameService=IOR:PUT_THE_IOR_HERE
# or
python run_experiment.py -ORBInitRef NameService=corbaloc::SERVER_IP:2809/NameService
```

Runtime console example:
```
Binary tool presence vector: [0, 1, 0, 0], FPS: 27.5, state time: 0.036
```
A new logfile appears in `./logs/` with a header line documenting the columns.

---

## How propositions are produced (for NuRV)

- Each frame is resized to **256×256**, normalized (`mean=[0.4927,0.2927,0.2982]`, `std=[0.2680,0.2320,0.2343]`), and passed to `MetaFormerFPN(num_classes=13, pretrained='SurgNet')`.
- We compute argmax over classes and count pixels per class. For instrument classes **8..11** we form:
  ```python
  counts = torch.bincount(output_classes, minlength=13)[8:12]
  binary_vector = (counts > 50).to(torch.uint8)  # hook, forceps, suction&irrigation, vessel sealer
  flag = bool(binary_vector.sum().item())        # at least one instrument present
  state_expr = "inCameraView" if flag else "!inCameraView"
  verdict = service.heartbeat(any.to_any(0), state_expr)
  ```
- NuRV returns an enum which we map to the text `"True" | "False" | "Unknown"` for the `G(inCameraView)` column.

---

## Experimental notes

- **Video source.** dVSS console output was captured via **HDMI‑to‑USB** to a Linux machine as a standard video device.  
- **Resolution & frame rate.** 640×480 at 25 fps were used during the experiment.  
- **Hardware.** Inference ran on a **GeForce GTX 1050 Ti Mobile** (single CUDA core used by the code path).  
- **Monitoring duration.** A continuous monitoring segment of ~15 minutes was executed intraoperatively.  
- **Timing.** Total per‑frame processing averaged **≈31.25 ms** (max **36 ms**), with the **NuRV** check itself up to **≈6.1 ms**, leaving headroom within the 40 ms/frame budget of the feed.  
- **Accuracy caveats.** The instrument detector was fine‑tuned on RAMIE data; for other procedures the presence signals may degrade and should be validated per setting.

---

## Troubleshooting (Linux)

### Name Service / CORBA
- **`Failed to narrow the root naming context`** → wrong `-ORBInitRef` or unreachable Name Service. Use the exact IOR/corbaloc from `omniNames`.
- **`CosNaming.NamingContext.NotFound`** on `resolve` → monitor not bound as `NuRV/Monitor/Service`. Fix server registration or adjust the three `CosNaming.NameComponent`s.
- **`TRANSIENT_NoServers` / timeouts** → server down or firewall blocking the Name Service / object endpoints.
- **`Object reference is not an Monitor::Service`** → stub/IDL mismatch with the running server.

### Import/IDL (`Monitor` module)
- **`ImportError: No module named Monitor`** → generate Python stubs from your `Monitor.idl` and expose them via `PYTHONPATH`:
  ```bash
  omniidl -bpython -C monitor_stubs path/to/Monitor.idl
  export PYTHONPATH="$(pwd)/monitor_stubs:$PYTHONPATH"
  ```

### PyTorch / CUDA
- `torch.cuda.is_available() == False` on a GPU machine → installed CPU wheel or driver/runtime mismatch; reinstall the correct wheel.
- `RuntimeError: invalid device function` → wheel incompatible with GPU compute capability or driver.
- OOM → reduce input size (e.g., 224×224) knowing it changes pixel counts/threshold behavior.

### Video device
- If the device index is wrong or in use, you will see `Could not open video capture`. Try indices `0,1,2,...` or ensure your user has permissions for `/dev/video*` (group `video`).

---

## Logging

The client creates `./logs/rv_run_YYYYMMDD_HHMMSS.log` and writes one CSV‑style line per processed frame:
```
step, [b0,b1,b2,b3], inCameraView, NuRVVerdict, delta_t_sec, fps

---

## Acknowledgements

This client reuses and adapts components from **SurgeNet** (Tim Jaspers et al.). We thank the authors for releasing their code and pretrained weights.

SurgeNet: <https://github.com/TimJaspers0801/SurgeNet>
