#!/usr/bin/env python3
"""测试入口：``python tests/run_tests.py``"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_algorithms import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
