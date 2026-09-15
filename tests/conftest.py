import os
# Existing API tests exercise the engine without accounts; dedicated auth tests re-enable it.
os.environ.setdefault("YARNENGINE_AUTH_DISABLED", "1")
