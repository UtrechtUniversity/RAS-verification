# NuRV client imports
import sys
from omniORB import CORBA
from omniORB import any
import Monitor
import CosNaming

# Segmentation imports
import cv2
import torch
import numpy as np
from PIL import Image
from MetaFormer import MetaFormerFPN
from torchvision import transforms as T
import time

# Logging
import logging
from pathlib import Path
from datetime import datetime

# 1 -- Build a timestamped base name
ts      = datetime.now().strftime("%Y%m%d_%H%M%S")
basename = f"rv_run_{ts}.log"

# 2 -- Pick / create the directory where the logs should live
log_dir = Path.cwd() / "logs"      # e.g.  .../your_project/logs
log_dir.mkdir(parents=True, exist_ok=True)

# 3 -- Combine directory + file name → full path object
fname = log_dir / basename

logging.basicConfig(                   # one call, done
    filename=fname,                    # omit to log to stdout instead
    level=logging.INFO,                # always on; no level gymnastics
    format="%(message)s",
    force=True,                        # overwrites any prior config
)
log = logging.getLogger(__name__)

# Logging the description of columns
log.info("state, tools vector, inCameraView, G(inCameraView), time passed since previous step, FPS")

# NuRV client set up
if len(sys.argv) < 2:
    print("Usage: run_experiment.py -ORBInitRef NameService=IOR:...")
    sys.exit(1)

orb = CORBA.ORB_init(sys.argv, CORBA.ORB_ID)

# Obtain a reference to the root naming context
obj = orb.resolve_initial_references("NameService");
rootContext = obj._narrow(CosNaming.NamingContext)

if rootContext is None:
    print("Failed to narrow the root naming context")
    sys.exit(1)

# Resolve the name "NuRV/Monitor/Service"
name = [CosNaming.NameComponent("NuRV", ""),
        CosNaming.NameComponent("Monitor", ""),
        CosNaming.NameComponent("Service", "")]
#print(name)
try:
    obj = rootContext.resolve(name)

#except Exception as ex:
#    print(ex)
except CosNaming.NamingContext.NotFound as ex:
    print("Name not found")
    sys.exit(1)

# Narrow the object to an Example::Echo
service = obj._narrow(Monitor.MonitorService)

if service is None:
    print("Object reference is not an Monitor::Service")
    sys.exit(1)


# Neural model set up

# Paths
weights_path = r'path_to_pth'

threshold = 50  # Nr of pixels before considering a tool is present

# Load model
device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
model = MetaFormerFPN(num_classes=13, pretrained='SurgNet').to(device)
model.load_state_dict(torch.load(weights_path))
model.eval()

# Video capture
cap = cv2.VideoCapture(0) # changed the index
if not cap.isOpened():
    raise RuntimeError("Could not open video capture")

# Normalization and preprocessing
mean = torch.tensor([0.4927, 0.2927, 0.2982])
std = torch.tensor([0.2680, 0.2320, 0.2343])
t_norm = T.Normalize(mean=mean, std=std)

def preprocess_frame(frame):
    image_rgb = cv2.resize(frame, (256, 256))
    image_tensor = T.ToTensor()(image_rgb).unsqueeze(0).to(device)
    return t_norm(image_tensor)

def predict(image_tensor):
    with torch.no_grad():
        return model(image_tensor)


# Reset the path history
service.reset(any.to_any(0), True)


# Print current evaluation function (state_count, binary_vector.tolist(), flag, state_time, fps)
def send_in_camera_view(
    step: int,
    tool_vector: list[int],        # keep as list[int]
    in_camera_view: bool,
    state_time: float,
    fps: float,
) -> None:
    """
    :param step:             just a line counter for pretty printing
    :param in_camera_view:   True  = the target **is** inside the camera view
                             False = it is **not** inside the camera view
    """
    # Build the NuSMV expression that describes the current state.
    # For a single Boolean variable this is either  "inCameraView"
    # or its negation "!inCameraView".
    state_expr = "inCameraView" if in_camera_view else "!inCameraView"

    # Index 0 is the monitor we built with `build_monitor -n 0`
    verdict = service.heartbeat(any.to_any(0), state_expr)

    # Translate the enum to something human-readable
    text = {Monitor.RV_True:    "True",
            Monitor.RV_False:   "False",
            Monitor.RV_Unknown: "Unknown"}.get(verdict, "Error")

    #print(f"{step:>3}: {state_expr:<15} ⇒  G(inCameraView) is {text}")
    #print(f"{step}, {tool_vector.tolist()}, {in_camera_view}, {text}, {state_time}, {fps}")
    log.info("%d, %s, %s, %s, %.3f, %.2f", step, tool_vector.tolist(), in_camera_view, text, state_time, fps)


# Tools identification cycle
state_count = 0
state_time = 0
try:
    while True:
        start_time = time.time()

        ret, frame = cap.read()
        if not ret:
            print("Failed to grab frame")
            break

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image_tensor = preprocess_frame(frame_rgb)
        pred = predict(image_tensor)

        output_classes = torch.argmax(pred, dim=1).flatten()
        counts = torch.bincount(output_classes, minlength=13)[8:12]
        binary_vector = (counts > threshold).to(torch.uint8) # hook, forceps, suction irrigation, vessel sealer

        elapsed_time = time.time() - start_time
        fps = 1 / (elapsed_time)

        flag = bool(binary_vector.sum().item())
        
        
        send_in_camera_view(state_count, binary_vector, flag, state_time, fps)
        print(f"Binary tool presence vector: {binary_vector.tolist()}, FPS: {fps:.2f}, state time: {state_time}")

        state_time = elapsed_time
        state_count += 1

except KeyboardInterrupt:
    print("Interrupted by user")

finally:
    cap.release()


