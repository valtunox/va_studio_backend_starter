"""
Import Check - Verify Core Module Imports
==========================================

Quick validation script that verifies all critical application modules
can be imported successfully. Exits with code 1 if any import fails.

Usage:
    python scripts/database/import_check.py
"""

import importlib, sys
mods = [
    'app.core.celery_app',
    'app.services.cloud.gateway.tasks',
    'app.services.cloud.gateway.pubsub',
    'app.services.cloud.gateway.ws',
    'app.services.cloud.gateway.router',
]
ok = True
for m in mods:
    try:
        importlib.import_module(m)
        print('OK', m)
    except Exception as e:
        ok = False
        print('ERR', m, '->', e)
sys.exit(0 if ok else 1)
