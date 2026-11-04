"""Start the exec target from the proof config's directory.

Promptfoo 0.124.1 runs an exec provider with its working directory set to the
directory of the config file. This script moves to the repository root, which
is where `python3 -m grader.redteam_target` resolves, and then calls it.
"""
import os
import sys


ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, os.pardir, os.pardir))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from grader.redteam_target import main  # noqa: E402


sys.exit(main(sys.argv[1:]))
