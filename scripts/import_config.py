import traceback
import sys, os
# add project root to path
root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if root not in sys.path:
    sys.path.insert(0, root)

try:
    import config.settings
    print('Import OK')
except Exception as e:
    traceback.print_exc()
