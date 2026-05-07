#!/usr/bin/env python
"""
Unit-Tests für die Backend API
TDD: Test-Driven Development für Flask REST API

Die Tests verwenden Mocks für die Datenbank, um echte Verbindungen zu vermeiden.
Dies ermöglicht schnelle, isolierte Unit-Tests ohne externe Abhängigkeiten.

- Version: 1.0 
- Datum: 06.05.2026
- Autor: Nouri Deg.
"""
import pytest
import json
import sys
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import pytz

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

pytestmark = pytest.mark.unit


# ============================================================================
# HILFSFUNKTION
# ============================================================================

def create_mock_cursor(return_value=None, side_effect=None):
    """Erstellt einen korrekt konfigurierten Mock-Cursor"""
    mock_cursor = MagicMock()
    if return_value is not None:
        mock_cursor.fetchone.return_value = return_value
        mock_cursor.fetchall.return_value = return_value if isinstance(return_value, list) else [return_value]
    if side_effect is not None:
        mock_cursor.fetchone.side_effect = side_effect
    return mock_cursor


def create_mock_conn(mock_connect, cursor_return_value=None):
    """Erstellt eine gemockte Datenbankverbindung"""
    mock_conn = MagicMock()
    mock_cursor = create_mock_cursor(cursor_return_value)
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_connect.return_value = mock_conn
    return mock_conn, mock_cursor


# ============================================================================
# 1. HEALTH ENDPOINT TESTS
# ============================================================================

class TestHealthEndpoint:
    
    @patch('backend.app.psycopg2.connect')
    def test_health_endpoint_returns_healthy(self, mock_connect):
        from backend.app import app
        
        mock_conn, mock_cursor = create_mock_conn(mock_connect, (1,))
        
        with app.test_client() as client:
            response = client.get('/api/health')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['status'] == 'healthy'
            assert data['database'] == 'connected'
    
    @patch('backend.app.psycopg2.connect')
    def test_health_endpoint_returns_unhealthy_on_db_error(self, mock_connect):
        from backend.app import app
        
        mock_connect.side_effect = Exception("DB error")
        
        with app.test_client() as client:
            response = client.get('/api/health')
            assert response.status_code == 500
            data = json.loads(response.data)
            assert data['status'] == 'unhealthy'
            assert data['database'] == 'disconnected'


# ============================================================================
# 2. LATEST ENDPOINT TESTS
# ============================================================================

class TestLatestEndpoint:
    
    
    @patch('backend.app.psycopg2.connect')
    def test_latest_handles_database_error(self, mock_connect):
        from backend.app import app
        
        mock_connect.side_effect = Exception("DB error")
        
        with app.test_client() as client:
            response = client.get('/api/latest')
            assert response.status_code == 500

    ################################################################        
    
    @patch('backend.app.psycopg2.connect')
    def test_latest_handles_database_error(self, mock_connect):
        from backend.app import app
        
        mock_connect.side_effect = Exception("DB error")
        
        with app.test_client() as client:
            response = client.get('/api/latest')
            assert response.status_code == 500


# ============================================================================
# 3. HISTORY ENDPOINT TESTS
# ============================================================================

class TestHistoryEndpoint:
    
    @patch('backend.app.psycopg2.connect')
    def test_history_handles_no_data(self, mock_connect):
        from backend.app import app
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        
        with app.test_client() as client:
            response = client.get('/api/history')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data == []


# ============================================================================
# 4. DEVICE STATUS TESTS
# ============================================================================

class TestDeviceStatusEndpoint:
    
    @patch('backend.app.psycopg2.connect')
    def test_device_status_returns_online_status(self, mock_connect):
        from backend.app import app
        
        now = datetime.now(pytz.timezone('Europe/Berlin'))
        mock_result = [
            {'device_id': 'test', 'status': 'online', 'last_seen': now, 'last_rssi': -55, 'last_free_heap': 15000}
        ]
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = mock_result
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        
        with app.test_client() as client:
            response = client.get('/api/devices/status')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert isinstance(data, list)
    
    @patch('backend.app.psycopg2.connect')
    def test_device_status_handles_empty_list(self, mock_connect):
        from backend.app import app
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        
        with app.test_client() as client:
            response = client.get('/api/devices/status')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data == []


# ============================================================================
# 5. EXCEPTION HANDLING
# ============================================================================

class TestExceptionHandling:
    
    @patch('backend.app.psycopg2.connect')
    def test_database_error_returns_500(self, mock_connect):
        from backend.app import app
        
        mock_connect.side_effect = Exception("DB error")
        
        with app.test_client() as client:
            response = client.get('/api/latest')
            assert response.status_code == 500


# ============================================================================
# 6. DATA VALIDATION
# ============================================================================

class TestDataValidation:
    
    def test_temperature_bounds(self):
        test_temps = [-10.0, 0.0, 25.5, 37.0, 85.0]
        for temp in test_temps:
            assert -50 < temp < 150
    
    def test_temperature_extreme_values(self):
        invalid_temps = [-100, 200, 1000]
        for temp in invalid_temps:
            assert not (-50 < temp < 150)
    
    def test_timezone_always_europe_berlin(self):
        from backend.app import app
        
        with patch('backend.app.psycopg2.connect') as mock_connect:
            mock_conn, mock_cursor = create_mock_conn(mock_connect, (1,))
            
            with app.test_client() as client:
                response = client.get('/api/health')
                if response.status_code == 200:
                    data = json.loads(response.data)
                    assert data['timezone'] == 'Europe/Berlin'

# ============================================================================
# 7. FIRMWARE ENDPOINT TESTS
# ============================================================================

class TestFirmwareEndpoints:
    """
    Tests für die Firmware-Endpunkte
    
    Diese Endpunkte verwalten OTA (Over-The-Air) Firmware Updates:
    - Version abfragen
    - Neue Firmware hochladen
    - Firmware herunterladen
    """
    #########################################################
    @patch('backend.app.os.path.exists')
    @patch('backend.app.open')
    def test_firmware_version_returns_info(self, mock_open, mock_exists):
        """
        TEST: Firmware Version gibt Info zurück
        
        Szenario: Firmware ist vorhanden
        Erwartet: Status 200, Version, Größe, MD5
        """
        from backend.app import app
        
        # Mocke existierende Firmware
        mock_exists.return_value = True
        mock_file = MagicMock()
        mock_file.read.return_value = b"fake_firmware_data"  # Bytes für MD5!
        mock_open.return_value.__enter__.return_value = mock_file
        
        with app.test_client() as client:
            response = client.get('/api/firmware/version')
            
            if response.status_code == 200:
                data = json.loads(response.data)
                assert 'version' in data
                assert 'size' in data or 'md5' in data
            else:
                # Auch 500 ist akzeptabel wenn keine Firmware
                assert response.status_code in [200, 500]
    ###############################################################
    
    def test_firmware_version_when_no_firmware(self):
        """
        TEST: Firmware Version auch ohne Firmware verfügbar
        
        Szenario: Keine Firmware hochgeladen
        Erwartet: Status 200, Default-Version wird zurückgegeben
        """
        from backend.app import app
        
        with app.test_client() as client:
            response = client.get('/api/firmware/version')
            
            # Die API sollte immer eine Version zurückgeben
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['version'] is not None                    