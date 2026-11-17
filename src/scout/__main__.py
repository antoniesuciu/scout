import sys
from .app import main

try:
    main()
except (RuntimeError,OSError,ValueError) as error:
    print(f"Scout: {error}",file=sys.stderr)
    raise SystemExit(1)
