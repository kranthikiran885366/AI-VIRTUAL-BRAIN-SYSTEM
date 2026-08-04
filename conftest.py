import sys
import os
import pytest

# Allow agents sub-modules to do `from planning_models import ...`
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "agents"))

def pytest_configure(config):
    config.addinivalue_line("markers", "asyncio: mark test as async")
    try:
        config.option.asyncio_mode = "auto"
    except AttributeError:
        pass

