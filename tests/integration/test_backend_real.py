# tests/integration/test_backend_real.py
import requests
import pytest

API_URL = "http://192.168.0.106:5000/api"

def test_health():
    response = requests.get(f"{API_URL}/health")
    assert response.status_code == 200
    assert response.json()['status'] == 'healthy'

def test_latest():
    response = requests.get(f"{API_URL}/latest")
    assert response.status_code in [200, 404]

def test_stats():
    response = requests.get(f"{API_URL}/stats")
    assert response.status_code in [200, 500]