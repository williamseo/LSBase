from __future__ import annotations

import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

from .app import app

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    print(f"🚀 LeadingStock with LSBase: http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=True, use_reloader=False)
