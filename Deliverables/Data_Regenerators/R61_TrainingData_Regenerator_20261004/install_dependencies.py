"""Install the exact numerical libraries used to verify this R61 data rebuild."""
import subprocess
import sys

if sys.version_info[:2] != (3, 12):
    raise SystemExit("Please use Python 3.12 for this package.")

# The original working environment uses this particular NumPy/OpenCV combination.
# Install its two exact wheels without allowing dependency resolution to replace NumPy.
subprocess.check_call([
    sys.executable, "-m", "pip", "install", "--no-deps",
    "numpy==1.26.4", "opencv-python==4.12.0.88",
])
subprocess.check_call([
    sys.executable, "-c",
    "import numpy, cv2; assert numpy.__version__ == '1.26.4'; assert cv2.__version__ == '4.12.0'; print('R61 dependencies ready')",
])
