"""Start the desktop health platform through its shared launcher."""

from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from start_interactive_rest import HOME_URL, run


if __name__ == '__main__':
    result = run(HOME_URL)
    if result == 0 and '--keep-alive' in sys.argv:
        try:
            while True:
                time.sleep(15)
        except KeyboardInterrupt:
            pass
    raise SystemExit(result)
