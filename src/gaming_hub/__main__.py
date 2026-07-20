"""Entry point for the Gaming Hub application.

Intended to be invoked as a module:

    python -m gaming_hub

This file is intentionally thin. It only wires the bootstrap layer and
starts the configured runtime.
"""

import sys

from gaming_hub.bootstrap import Application


def main() -> int:
    """Run the application lifecycle."""
    app = Application()
    return app.run(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
