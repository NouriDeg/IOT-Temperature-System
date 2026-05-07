#!/usr/bin/env python
"""
Pytest Konfiguration und Shared Fixtures für alle Tests
"""

import sys
import os
from unittest.mock import MagicMock, patch
import pytest

# ============================================================================
# Mocks NUR FÜR UNIT-TESTS (anhand des Dateipfads erkennen)
# ============================================================================

# Mock für Flask-CORS (Backend) - immer
sys.modules['flask_cors'] = MagicMock()

# Diese Mocks werden NUR für Unit-Tests aktiviert, 


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture(scope="session")
def test_env():
    """Test-Umgebungsvariablen für die gesamte Test-Session"""
    os.environ.setdefault('DB_HOST', 'localhost')
    os.environ.setdefault('DB_PASSWORD', 'test_password_123')
    os.environ.setdefault('MQTT_BROKER_ADDRESS', 'localhost')
    os.environ.setdefault('MQTT_BRIDGE_USER', 'bridge_user')
    os.environ.setdefault('MQTT_BRIDGE_PASSWORD', 'bridge_pass')
    os.environ.setdefault('MQTT_PROVISION_USER', 'provisioner')
    os.environ.setdefault('MQTT_PROVISION_PASSWORD', 'provisioner_pass')
    return os.environ


@pytest.fixture
def mock_db_connection():
    """Mock für Datenbankverbindung (nur für Unit-Tests)"""
    with patch('psycopg2.connect') as mock_connect:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        yield mock_connect


@pytest.fixture
def mock_mqtt_client():
    """Mock für MQTT Client (nur für Unit-Tests)"""
    with patch('paho.mqtt.client.Client') as mock_client:
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance
        yield mock_instance

# ============================================================================
# PYTEST KONFIGURATION
# ============================================================================

def pytest_configure(config):
    """Pytest Konfiguration - Definiert Custom Markers"""
    config.addinivalue_line("markers", "unit: Unit tests (schnell, keine externen Abhängigkeiten)")
    config.addinivalue_line("markers", "integration: Integration tests (benötigt laufende Services)")
    config.addinivalue_line("markers", "slow: Langsame Tests")


def pytest_collection_modifyitems(config, items):
    """Automatische Marker-Zuweisung basierend auf Dateipfad"""
    for item in items:
        # Unit Tests im unit/ Ordner
        if "unit/" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
            # Für Unit-Tests: Mocks aktivieren (wird in den Tests selbst gemacht)
        # Integration Tests im integration/ Ordner - KEINE MOCKS!
        elif "integration/" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
            
        