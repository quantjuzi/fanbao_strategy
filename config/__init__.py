"""Config Loader"""

import os
import yaml
from typing import Any, Dict

def load_config(path=None):
    if path is None:
        path = os.path.join(os.path.dirname(__file__), 'settings.yaml')
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

settings = load_config()