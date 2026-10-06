"""PyInstaller entry script (the package itself uses relative imports)."""
import sys

from racingsim.app import main

sys.exit(main())
