#!/usr/bin/env python
"""
Backend API für IoT Temperature Monitoring System
Mit Web Dashboard
"""

from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
import psycopg2
import psycopg2.extras
import os
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

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
    """Aktuellste Temperatur"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT device_id, temperature, unit, received_at 
            FROM sensor_data 
            ORDER BY received_at DESC 
            LIMIT 1
        """)
        row = cur.fetchone()
        cur.close()
        conn.close()
        
        if row:
            return jsonify({
                'device_id': row['device_id'],
                'temperature': float(row['temperature']),
                'unit': row['unit'],
                'timestamp': row['received_at'].isoformat()
            })
        return jsonify({'error': 'Keine Daten'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/history')
def get_history():
    """Historische Temperaturdaten"""
    hours = request.args.get('hours', 24, type=int)
    limit = request.args.get('limit', 100, type=int)
    
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT device_id, temperature, unit, received_at 
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
            'timestamp': row['received_at'].isoformat()
        } for row in rows])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/devices')
def get_devices():
    """Alle registrierten Geräte"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT device_id, status, last_seen, provisioned_at
            FROM devices 
            ORDER BY last_seen DESC NULLS LAST
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        return jsonify([{
            'device_id': row['device_id'],
            'status': row['status'],
            'last_seen': row['last_seen'].isoformat() if row['last_seen'] else None,
            'provisioned_at': row['provisioned_at'].isoformat() if row['provisioned_at'] else None
        } for row in rows])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats')
def get_stats():
    """Statistiken (Min, Max, Avg)"""
    hours = request.args.get('hours', 24, type=int)
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT 
                MIN(temperature) as min_temp,
                MAX(temperature) as max_temp,
                AVG(temperature) as avg_temp,
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)