import os
import runpy
import sys

if getattr(sys, "frozen", False):
    os.chdir(os.path.dirname(sys.executable))

from dotenv import load_dotenv

load_dotenv(".env")

if os.environ.get("INSTA_USERNAME"):
    print(f"claudina is up on instagram as @{os.environ['INSTA_USERNAME']}  (ctrl+c to stop)")
    runpy.run_module("insta", run_name = "__main__")
else:
    print("claudina is up, say hi  (ctrl+d to stop)")
    runpy.run_module("main", run_name = "__main__")
