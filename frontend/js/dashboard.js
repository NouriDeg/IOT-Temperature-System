/**
 * ============================================
 * IoT DASHBOARD - JAVASCRIPT
 * ============================================
 * 
 * Funktionen:
 * - Live-Datenabfrage über REST API
 * - Automatische Aktualisierung alle 10 Sekunden
 * - Chart.js Diagramm für Temperaturverlauf
 * - OTA Firmware Upload
 * - LWT Status Anzeige
 * 
 * API Endpoints:
 * - GET /api/latest - Aktuelle Temperatur
 * - GET /api/stats - Statistiken
 * - GET /api/devices/status - Gerätestatus
 * - GET /api/lwt/stats - LWT Statistiken
 * - GET /api/firmware/version - Firmware Version
 * - POST /api/firmware/upload - Firmware Upload
 * 
 *  Autor: Nouri deg.
 * @version 2.0
 * @date 29.04.2026
 * ============================================
 */

// API Basis-URL (Backend)
const API_BASE = 'http://192.168.0.105:5000/api';

// Chart.js Diagramm-Instanz (global für Updates)
let chart = null;

/**
 * Lädt die aktuellste Temperatur vom Backend
 * Endpoint: GET /api/latest
 * 
 * Aktualisiert:
 * - Aktuelle Temperatur (rot, groß)
 * - Geräte-ID
 * - Letzte Messung (gelb, größer)
 */
async function fetchLatest() {
    try {
        const response = await fetch(`${API_BASE}/latest`);
        const data = await response.json();
        
        if (!data.error) {
            // Temperatur anzeigen (2 Nachkommastellen)
            document.getElementById('current-temp').innerHTML = data.temperature.toFixed(2) + ' °C';
            document.getElementById('current-device').innerHTML = '📟 Gerät: ' + data.device_id;
            
            // Letzte Messung - GELB und GRÖSSER (special class)
            const lastTimeElement = document.getElementById('current-time');
            const formattedDate = new Date(data.timestamp).toLocaleString('de-DE', {
                day: '2-digit',
                month: '2-digit',
                year: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            });
            lastTimeElement.innerHTML = '🕐 Letzte Messung: ' + formattedDate;
        }
    } catch (error) {
        console.error('Fehler beim Laden der aktuellen Temperatur:', error);
    }
}

/**
 * Lädt Statistiken der letzten 24 Stunden
 * Endpoint: GET /api/stats?hours=24
 * 
 * Aktualisiert:
 * - Minimale Temperatur
 * - Maximale Temperatur
 * - Durchschnittstemperatur
 * - Anzahl der Messungen
 */
async function fetchStats() {
    try {
        const response = await fetch(`${API_BASE}/stats?hours=24`);
        const data = await response.json();
        
        if (!data.error) {
            document.getElementById('min-temp').innerHTML = data.min_temp?.toFixed(2) || '--';
            document.getElementById('max-temp').innerHTML = data.max_temp?.toFixed(2) || '--';
            document.getElementById('avg-temp').innerHTML = data.avg_temp?.toFixed(2) || '--';
            document.getElementById('count').innerHTML = data.count || 0;
        }
    } catch (error) {
        console.error('Fehler beim Laden der Statistiken:', error);
    }
}

/**
 * Lädt den Status aller Geräte
 * Endpoint: GET /api/devices/status
 * 
 * Aktualisiert:
 * - Geräteliste mit Status (online/offline)
 * - RSSI Signalstärke mit Farbkodierung
 * - Heap Speicher
 * - Letzte Nachricht
 */
async function fetchDevicesStatus() {
    try {
        const response = await fetch(`${API_BASE}/devices/status`);
        const data = await response.json();
        
        if (!data.error && data.length > 0) {
            let html = '';
            
            data.forEach(device => {
                // Status-Klasse für Farbe
                const statusClass = device.status === 'online' ? 'online' : 'offline';
                
                // RSSI-Klasse für Signalstärke
                let rssiClass = '';
                if (device.last_rssi) {
                    if (device.last_rssi > -60) rssiClass = 'signal-good';
                    else if (device.last_rssi > -70) rssiClass = 'signal-medium';
                    else rssiClass = 'signal-bad';
                }
                
                // HTML für jedes Gerät
                html += `
                    <div class="device-item">
                        <strong>📟 ${escapeHtml(device.device_id)}</strong><br>
                        Status: <span class="${statusClass}">${device.status === 'online' ? '🟢 Online' : '🔴 Offline'}</span><br>
                        📶 RSSI: <span class="${rssiClass}">${device.last_rssi || '--'} dBm</span><br>
                        💾 Heap: ${device.last_free_heap || '--'} bytes<br>
                        🕐 Letzte Nachricht: ${device.last_seen ? new Date(device.last_seen).toLocaleString() : 'never'}
                    </div>
                `;
            });
            
            document.getElementById('devices-list').innerHTML = html;
        } else {
            document.getElementById('devices-list').innerHTML = '<div class="device-item">Keine Geräte gefunden</div>';
        }
    } catch (error) {
        console.error('Fehler beim Laden der Geräteliste:', error);
    }
}

/**
 * Lädt LWT (Last Will Testament) Statistiken
 * Endpoint: GET /api/lwt/stats
 * 
 * Aktualisiert:
 * - Gesamtanzahl Geräte
 * - Online Geräte
 * - Offline Geräte
 * - Durchschnittliche RSSI
 */
async function fetchLWTStats() {
    try {
        const response = await fetch(`${API_BASE}/lwt/stats`);
        const data = await response.json();
        
        if (!data.error) {
            document.getElementById('total-devices').innerHTML = data.total_devices || 0;
            document.getElementById('online-devices').innerHTML = data.online_devices || 0;
            document.getElementById('offline-devices').innerHTML = data.offline_devices || 0;
            document.getElementById('avg-rssi').innerHTML = data.avg_rssi || '--';
        }
    } catch (error) {
        console.error('Fehler beim Laden der LWT Statistiken:', error);
    }
}

/**
 * Lädt Informationen über die aktuelle Firmware
 * Endpoint: GET /api/firmware/version
 * 
 * Aktualisiert:
 * - Firmware Version
 * - Dateigröße in KB
 * - MD5 Hash (gekürzt)
 */
async function fetchFirmwareInfo() {
    try {
        const response = await fetch(`${API_BASE}/firmware/version`);
        const data = await response.json();
        
        if (!data.error) {
            const sizeKB = (data.size / 1024).toFixed(2);
            document.getElementById('firmware-info').innerHTML = `
                📦 Version: <strong>${data.version}</strong><br>
                📏 Größe: ${sizeKB} KB<br>
                🔑 MD5: ${data.md5?.substring(0, 16) || '---'}...
            `;
        } else {
            document.getElementById('firmware-info').innerHTML = '📦 Keine Firmware vorhanden';
        }
    } catch (error) {
        console.error('Fehler beim Laden der Firmware Info:', error);
        document.getElementById('firmware-info').innerHTML = '📦 Fehler beim Laden';
    }
}

/**
 * Lädt Firmware-Datei hoch und speichert sie auf dem Server
 * Endpoint: POST /api/firmware/upload
 * 
 * @param {File} file - Die ausgewählte .bin Datei
 * @param {string} version - Versionsnummer
 */
async function uploadFirmware() {
    const fileInput = document.getElementById('firmware-file');
    const versionInput = document.getElementById('firmware-version');
    const statusDiv = document.getElementById('upload-status');
    
    // Prüfe ob eine Datei ausgewählt wurde
    if (!fileInput.files.length) {
        showStatus('❌ Bitte wähle eine Firmware Datei aus', '#ff6666');
        return;
    }
    
    const file = fileInput.files[0];
    const version = versionInput.value.trim() || '1.0.0';
    
    // FormData für Datei-Upload
    const formData = new FormData();
    formData.append('file', file);
    formData.append('version', version);
    
    showStatus('📤 Upload läuft...', '#FFC107');
    
    try {
        const response = await fetch(`${API_BASE}/firmware/upload`, {
            method: 'POST',
            body: formData
        });
        const data = await response.json();
        
        if (response.ok) {
            showStatus(`✅ ${data.message} (Version ${data.version})`, '#4CAF50');
            fetchFirmwareInfo(); // Firmware Info aktualisieren
        } else {
            showStatus(`❌ Fehler: ${data.error}`, '#ff6666');
        }
    } catch (error) {
        showStatus(`❌ Upload fehlgeschlagen: ${error.message}`, '#ff6666');
    }
}

/**
 * Statusmeldung im Upload-Bereich anzeigen
 * @param {string} message - Die anzuzeigende Nachricht
 * @param {string} color - Textfarbe (CSS-Farbwert)
 */
function showStatus(message, color) {
    const statusDiv = document.getElementById('upload-status');
    statusDiv.innerHTML = message;
    statusDiv.style.color = color;
    
    // Nach 5 Sekunden ausblenden
    setTimeout(() => {
        if (statusDiv.innerHTML === message) {
            statusDiv.innerHTML = '';
        }
    }, 5000);
}

/**
 * Löst ein OTA (Over-the-Air) Update aus
 * Sendet einen Befehl an den ESP8266 (simuliert)
 */
async function triggerOTA() {
    const btn = event.target;
    const originalText = btn.innerHTML;
    
    btn.innerHTML = '⏳ Wird ausgelöst...';
    btn.disabled = true;
    
    try {
        // Simuliere OTA Update (würde eigentlich MQTT Befehl senden)
        await new Promise(resolve => setTimeout(resolve, 2000));
        
        alert('🚀 OTA Update wurde ausgelöst!\n\nDas ESP8266 wird die Firmware herunterladen und aktualisieren.');
        
        btn.innerHTML = originalText;
        btn.disabled = false;
    } catch (error) {
        console.error('Fehler beim OTA Update:', error);
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}

/**
 * Lädt den Temperaturverlauf der letzten 24 Stunden
 * Endpoint: GET /api/history?hours=24&limit=200
 * 
 * Zeichnet ein Chart.js Liniendiagramm mit roter Linie
 */
async function fetchHistory() {
    try {
        const response = await fetch(`${API_BASE}/history?hours=24&limit=200`);
        const data = await response.json();
        
        if (!data.error && data.length > 0) {
            // X-Achse: Zeit (nur Stunden:Minuten)
            const times = data.map(d => {
                const date = new Date(d.timestamp);
                return date.toLocaleTimeString('de-DE', { 
                    hour: '2-digit', 
                    minute: '2-digit' 
                });
            });
            
            // Y-Achse: Temperaturwerte
            const temps = data.map(d => d.temperature);
            
            // Altes Diagramm zerstören (falls vorhanden)
            if (chart) chart.destroy();
            
            // Neues Diagramm zeichnen (rote Linie)
            const ctx = document.getElementById('tempChart').getContext('2d');
            chart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: times,
                    datasets: [{
                        label: 'Temperatur (°C)',
                        data: temps,
                        borderColor: '#ff4444',        // ROTE Linie
                        backgroundColor: 'rgba(255, 68, 68, 0.1)',  // Leichter roter Hintergrund
                        borderWidth: 2,
                        fill: true,
                        tension: 0.4,                  // Leichte Kurvenglättung
                        pointRadius: 2,
                        pointHoverRadius: 5,
                        pointBackgroundColor: '#ff4444'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {
                        legend: {
                            labels: { color: '#ffffff' }  // Weiße Legende
                        },
                        tooltip: {
                            mode: 'index',
                            intersect: false
                        }
                    },
                    scales: {
                        x: {
                            ticks: { 
                                color: '#ffffff',
                                maxRotation: 45,
                                minRotation: 45
                            },
                            grid: { color: 'rgba(255, 255, 255, 0.1)' }
                        },
                        y: {
                            ticks: { color: '#ffffff' },
                            grid: { color: 'rgba(255, 255, 255, 0.1)' }
                        }
                    }
                }
            });
        }
    } catch (error) {
        console.error('Fehler beim Laden des Temperaturverlaufs:', error);
    }
}

/**
 * HTML Escape gegen XSS-Angriffe
 * @param {string} text - Der zu escapende Text
 * @returns {string} - Escapeter Text
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ============================================
// AUTOMATISCHE AKTUALISIERUNG
// ============================================
// Alle 10 Sekunden werden alle Daten neu geladen
setInterval(() => {
    fetchLatest();
    fetchStats();
    fetchDevicesStatus();
    fetchLWTStats();
    fetchHistory();
    fetchFirmwareInfo();
}, 10000);

// ============================================
// INITIALES LADEN BEIM SEITENSTART
// ============================================
fetchLatest();
fetchStats();
fetchDevicesStatus();
fetchLWTStats();
fetchHistory();
fetchFirmwareInfo();

// Console-Ausgabe für Debugging
console.log('🌡️ Dashboard gestartet - Aktualisiert alle 10 Sekunden');