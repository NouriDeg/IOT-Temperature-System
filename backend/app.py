#!/usr/bin/env python
"""
Backend API für IoT Temperature Monitoring System
Mit Web Dashboard - ZEITZONE: Europe/Berlin (CET/UTC+1, CEST/UTC+2)
"""

from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
import psycopg2
import psycopg2.extras
import os
from datetime import datetime, timedelta
import pytz

app = Flask(__name__)
CORS(app)

# ==========================================
# ZEITZONE KONFIGURATION (Berlin)
# ==========================================
LOCAL_TZ = pytz.timezone('Europe/Berlin')  # CET/CEST

# PostgreSQL Konfiguration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'postgres'),
    'port': os.getenv('DB_PORT', 5432),
    'database': os.getenv('DB_NAME', 'sensordb'),
    'user': os.getenv('DB_USER', 'sensor_user'),
    'password': os.getenv('DB_PASSWORD', '')
}

def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)

def to_local_time(utc_time):
    """Konvertiert UTC Zeit in lokale Berliner Zeit"""
    if utc_time is None:
        return None
    # Falls das datetime object naive ist (keine Zeitzone), füge UTC hinzu
    if utc_time.tzinfo is None:
        utc_time = pytz.UTC.localize(utc_time)
    # Konvertiere nach Europe/Berlin
    local_time = utc_time.astimezone(LOCAL_TZ)
    return local_time

def get_local_now():
    """Gibt die aktuelle lokale Zeit in Berlin zurück"""
    return datetime.now(LOCAL_TZ)

# ==========================================
# WEB DASHBOARD
# ==========================================
@app.route('/')
def dashboard():
    """Zeigt das HTML Dashboard"""
    return render_template('index.html')

# ==========================================
# REST API ENDPOINTS
# ==========================================
@app.route('/api/latest')
def get_latest():
    """Aktuellste Temperatur mit lokaler Berliner Zeit"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT device_id, value as temperature, unit, received_at 
            FROM sensor_data 
            ORDER BY received_at DESC 
            LIMIT 1
        """)
        row = cur.fetchone()
        cur.close()
        conn.close()
        
        if row:
            local_time = to_local_time(row['received_at'])
            return jsonify({
                'device_id': row['device_id'],
                'temperature': float(row['temperature']),
                'unit': row['unit'],
                'timestamp': local_time.strftime('%Y-%m-%d %H:%M:%S'),
                'timezone': 'Europe/Berlin'
            })
        return jsonify({'error': 'Keine Daten'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/history')
def get_history():
    """Historische Temperaturdaten mit lokaler Berliner Zeit"""
    hours = request.args.get('hours', 24, type=int)
    limit = request.args.get('limit', 200, type=int)
    
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT device_id, value as temperature, unit, received_at 
            FROM sensor_data 
            WHERE received_at > NOW() - INTERVAL '%s hours'
            ORDER BY received_at ASC
            LIMIT %s
        """, (hours, limit))
        
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        return jsonify([{
            'device_id': row['device_id'],
            'temperature': float(row['temperature']),
            'unit': row['unit'],
            'timestamp': to_local_time(row['received_at']).strftime('%Y-%m-%d %H:%M:%S')
        } for row in rows])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/devices')
def get_devices():
    """Alle registrierten Geräte mit lokaler Berliner Zeit"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT device_id, status, last_seen, updated_at as last_update
            FROM device_status 
            ORDER BY last_seen DESC NULLS LAST
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        return jsonify([{
            'device_id': row['device_id'],
            'status': row['status'],
            'last_seen': to_local_time(row['last_seen']).strftime('%Y-%m-%d %H:%M:%S') if row['last_seen'] else None,
            'last_update': to_local_time(row['last_update']).strftime('%Y-%m-%d %H:%M:%S') if row['last_update'] else None
        } for row in rows])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats')
def get_stats():
    """Statistiken (Min, Max, Avg) für lokale Zeit"""
    hours = request.args.get('hours', 24, type=int)
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT 
                MIN(value) as min_temp,
                MAX(value) as max_temp,
                AVG(value) as avg_temp,
                COUNT(*) as count
            FROM sensor_data 
            WHERE received_at > NOW() - INTERVAL '%s hours'
        """, (hours,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        
        return jsonify({
            'min_temp': float(row[0]) if row[0] else None,
            'max_temp': float(row[1]) if row[1] else None,
            'avg_temp': float(row[2]) if row[2] else None,
            'count': row[3] if row[3] else 0
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/health')
def health():
    """Health Check Endpoint"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.close()
        return jsonify({
            'status': 'healthy', 
            'database': 'connected',
            'timezone': 'Europe/Berlin',
            'server_time': get_local_now().strftime('%Y-%m-%d %H:%M:%S')
        })
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)