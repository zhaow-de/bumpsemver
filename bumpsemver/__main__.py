import sys

if sys.version_info[0] == 2:
    print("Fatal: this application requires Python3. Please run it in a virtualenv to make sure \"python --version\" gives 3.x.y.")
    sys.exit(2)

from bumpsemver.cli import main

main()
