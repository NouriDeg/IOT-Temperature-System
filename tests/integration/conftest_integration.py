# tests/integration/conftest.py
"""
Integrationstests - KEINE MOCKS!
Stelle sicher, dass echte Module geladen werden.
"""

import sys

# Entferne Mocks für paho-mqtt (falls vorhanden)
if 'paho' in sys.modules:
    del sys.modules['paho']
if 'paho.mqtt' in sys.modules:
    del sys.modules['paho.mqtt']
if 'paho.mqtt.client' in sys.modules:
    del sys.modules['paho.mqtt.client']

# Entferne Mocks für psycopg2
if 'psycopg2' in sys.modules:
    del sys.modules['psycopg2']
if 'psycopg2.extras' in sys.modules:
    del sys.modules['psycopg2.extras']

print("Integrationstests: Mocks deaktiviert, echte Module werden verwendet")