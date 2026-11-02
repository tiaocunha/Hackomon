import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / "payload" / "hackomon"
if str(PAYLOAD) not in sys.path:
    sys.path.insert(0, str(PAYLOAD))


TEST_TEMP = ROOT / ".test-tmp"


def temporary_directory():
    TEST_TEMP.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(dir=str(TEST_TEMP))

