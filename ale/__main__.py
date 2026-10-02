"""`python -m ale <command>` entry point."""

import sys

from ale.interfaces.cli import main

if __name__ == "__main__":
    sys.exit(main())
