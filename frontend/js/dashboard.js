// /**
//  * ============================================
//  * IoT DASHBOARD - JAVASCRIPT
//  * ============================================
//  * 
//  * Funktionen:
//  * - Live-Datenabfrage über REST API
//  * - Automatische Aktualisierung alle 10 Sekunden
//  * - Chart.js Diagramm für Temperaturverlauf
//  * - OTA Firmware Upload
//  * - LWT Status Anzeige
//  * 
//  * API Endpoints:
//  * - GET /api/latest - Aktuelle Temperatur
//  * - GET /api/stats - Statistiken
//  * - GET /api/devices/status - Gerätestatus
//  * - GET /api/lwt/stats - LWT Statistiken
//  * - GET /api/firmware/version - Firmware Version
//  * - POST /api/firmware/upload - Firmware Upload
//  * 
//  *  Autor: Nouri deg.
//  * @version 2.0
//  * @date 29.04.2026
//  * ============================================
//  */

// // API Basis-URL (Backend)
// const API_BASE = 'http://192.168.0.105:5000/api';

// // Chart.js Diagramm-Instanz (global für Updates)
// let chart = null;

// /**
//  * Lädt die aktuellste Temperatur vom Backend
//  * Endpoint: GET /api/latest
//  * 
//  * Aktualisiert:
//  * - Aktuelle Temperatur (rot, groß)
//  * - Geräte-ID
//  * - Letzte Messung (gelb, größer)
//  */
// async function fetchLatest() {
//     try {
//         const response = await fetch(`${API_BASE}/latest`);
//         const data = await response.json();
        
//         if (!data.error) {
//             // Temperatur anzeigen (2 Nachkommastellen)
//             document.getElementById('current-temp').innerHTML = data.temperature.toFixed(2) + ' °C';
//             document.getElementById('current-device').innerHTML = '📟 Gerät: ' + data.device_id;
            
//             // Letzte Messung - GELB und GRÖSSER (special class)
//             const lastTimeElement = document.getElementById('current-time');
//             const formattedDate = new Date(data.timestamp).toLocaleString('de-DE', {
//                 day: '2-digit',
//                 month: '2-digit',
//                 year: 'numeric',
//                 hour: '2-digit',
//                 minute: '2-digit',
//                 second: '2-digit'
//             });
//             lastTimeElement.innerHTML = '🕐 Letzte Messung: ' + formattedDate;
//         }
//     } catch (error) {
//         console.error('Fehler beim Laden der aktuellen Temperatur:', error);
//     }
// }

// /**
//  * Lädt Statistiken der letzten 24 Stunden
//  * Endpoint: GET /api/stats?hours=24
//  * 
//  * Aktualisiert:
//  * - Minimale Temperatur
//  * - Maximale Temperatur
//  * - Durchschnittstemperatur
//  * - Anzahl der Messungen
//  */
// async function fetchStats() {
//     try {
//         const response = await fetch(`${API_BASE}/stats?hours=24`);
//         const data = await response.json();
        
//         if (!data.error) {
//             document.getElementById('min-temp').innerHTML = data.min_temp?.toFixed(2) || '--';
//             document.getElementById('max-temp').innerHTML = data.max_temp?.toFixed(2) || '--';
//             document.getElementById('avg-temp').innerHTML = data.avg_temp?.toFixed(2) || '--';
//             document.getElementById('count').innerHTML = data.count || 0;
//         }
//     } catch (error) {
//         console.error('Fehler beim Laden der Statistiken:', error);
//     }
// }

// /**
//  * Lädt den Status aller Geräte
//  * Endpoint: GET /api/devices/status
//  * 
//  * Aktualisiert:
//  * - Geräteliste mit Status (online/offline)
//  * - RSSI Signalstärke mit Farbkodierung
//  * - Heap Speicher
//  * - Letzte Nachricht
//  */
// async function fetchDevicesStatus() {
//     try {
//         const response = await fetch(`${API_BASE}/devices/status`);
//         const data = await response.json();
        
//         if (!data.error && data.length > 0) {
//             let html = '';
            
//             data.forEach(device => {
//                 // Status-Klasse für Farbe
//                 const statusClass = device.status === 'online' ? 'online' : 'offline';
                
//                 // RSSI-Klasse für Signalstärke
//                 let rssiClass = '';
//                 if (device.last_rssi) {
//                     if (device.last_rssi > -60) rssiClass = 'signal-good';
//                     else if (device.last_rssi > -70) rssiClass = 'signal-medium';
//                     else rssiClass = 'signal-bad';
//                 }
                
//                 // HTML für jedes Gerät
//                 html += `
//                     <div class="device-item">
//                         <strong>📟 ${escapeHtml(device.device_id)}</strong><br>
//                         Status: <span class="${statusClass}">${device.status === 'online' ? '🟢 Online' : '🔴 Offline'}</span><br>
//                         📶 RSSI: <span class="${rssiClass}">${device.last_rssi || '--'} dBm</span><br>
//                         💾 Heap: ${device.last_free_heap || '--'} bytes<br>
//                         🕐 Letzte Nachricht: ${device.last_seen ? new Date(device.last_seen).toLocaleString() : 'never'}
//                     </div>
//                 `;
//             });
            
//             document.getElementById('devices-list').innerHTML = html;
//         } else {
//             document.getElementById('devices-list').innerHTML = '<div class="device-item">Keine Geräte gefunden</div>';
//         }
//     } catch (error) {
//         console.error('Fehler beim Laden der Geräteliste:', error);
//     }
// }

// /**
//  * Lädt LWT (Last Will Testament) Statistiken
//  * Endpoint: GET /api/lwt/stats
//  * 
//  * Aktualisiert:
//  * - Gesamtanzahl Geräte
//  * - Online Geräte
//  * - Offline Geräte
//  * - Durchschnittliche RSSI
//  */
// async function fetchLWTStats() {
//     try {
//         const response = await fetch(`${API_BASE}/lwt/stats`);
//         const data = await response.json();
        
//         if (!data.error) {
//             document.getElementById('total-devices').innerHTML = data.total_devices || 0;
//             document.getElementById('online-devices').innerHTML = data.online_devices || 0;
//             document.getElementById('offline-devices').innerHTML = data.offline_devices || 0;
//             document.getElementById('avg-rssi').innerHTML = data.avg_rssi || '--';
//         }
//     } catch (error) {
//         console.error('Fehler beim Laden der LWT Statistiken:', error);
//     }
// }

// /**
//  * Lädt Informationen über die aktuelle Firmware
//  * Endpoint: GET /api/firmware/version
//  * 
//  * Aktualisiert:
//  * - Firmware Version
//  * - Dateigröße in KB
//  * - MD5 Hash (gekürzt)
//  */
// async function fetchFirmwareInfo() {
//     try {
//         const response = await fetch(`${API_BASE}/firmware/version`);
//         const data = await response.json();
        
//         if (!data.error) {
//             const sizeKB = (data.size / 1024).toFixed(2);
//             document.getElementById('firmware-info').innerHTML = `
//                 📦 Version: <strong>${data.version}</strong><br>
//                 📏 Größe: ${sizeKB} KB<br>
//                 🔑 MD5: ${data.md5?.substring(0, 16) || '---'}...
//             `;
//         } else {
//             document.getElementById('firmware-info').innerHTML = '📦 Keine Firmware vorhanden';
//         }
//     } catch (error) {
//         console.error('Fehler beim Laden der Firmware Info:', error);
//         document.getElementById('firmware-info').innerHTML = '📦 Fehler beim Laden';
//     }
// }

// /**
//  * Lädt Firmware-Datei hoch und speichert sie auf dem Server
//  * Endpoint: POST /api/firmware/upload
//  * 
//  * @param {File} file - Die ausgewählte .bin Datei
//  * @param {string} version - Versionsnummer
//  */
// async function uploadFirmware() {
//     const fileInput = document.getElementById('firmware-file');
//     const versionInput = document.getElementById('firmware-version');
//     const statusDiv = document.getElementById('upload-status');
    
//     // Prüfe ob eine Datei ausgewählt wurde
//     if (!fileInput.files.length) {
//         showStatus('❌ Bitte wähle eine Firmware Datei aus', '#ff6666');
//         return;
//     }
    
//     const file = fileInput.files[0];
//     const version = versionInput.value.trim() || '1.0.0';
    
//     // FormData für Datei-Upload
//     const formData = new FormData();
//     formData.append('file', file);
//     formData.append('version', version);
    
//     showStatus('📤 Upload läuft...', '#FFC107');
    
//     try {
//         const response = await fetch(`${API_BASE}/firmware/upload`, {
//             method: 'POST',
//             body: formData
//         });
//         const data = await response.json();
        
//         if (response.ok) {
//             showStatus(`✅ ${data.message} (Version ${data.version})`, '#4CAF50');
//             fetchFirmwareInfo(); // Firmware Info aktualisieren
//         } else {
//             showStatus(`❌ Fehler: ${data.error}`, '#ff6666');
//         }
//     } catch (error) {
//         showStatus(`❌ Upload fehlgeschlagen: ${error.message}`, '#ff6666');
//     }
// }

// /**
//  * Statusmeldung im Upload-Bereich anzeigen
//  * @param {string} message - Die anzuzeigende Nachricht
//  * @param {string} color - Textfarbe (CSS-Farbwert)
//  */
// function showStatus(message, color) {
//     const statusDiv = document.getElementById('upload-status');
//     statusDiv.innerHTML = message;
//     statusDiv.style.color = color;
    
//     // Nach 5 Sekunden ausblenden
//     setTimeout(() => {
//         if (statusDiv.innerHTML === message) {
//             statusDiv.innerHTML = '';
//         }
//     }, 5000);
// }

// /**
//  * Löst ein OTA (Over-the-Air) Update aus
//  * Sendet einen Befehl an den ESP8266 (simuliert)
//  */
// async function triggerOTA() {
//     const btn = event.target;
//     const originalText = btn.innerHTML;
    
//     btn.innerHTML = '⏳ Wird ausgelöst...';
//     btn.disabled = true;
    
//     try {
//         // Simuliere OTA Update (würde eigentlich MQTT Befehl senden)
//         await new Promise(resolve => setTimeout(resolve, 2000));
        
//         alert('🚀 OTA Update wurde ausgelöst!\n\nDas ESP8266 wird die Firmware herunterladen und aktualisieren.');
        
//         btn.innerHTML = originalText;
//         btn.disabled = false;
//     } catch (error) {
//         console.error('Fehler beim OTA Update:', error);
//         btn.innerHTML = originalText;
//         btn.disabled = false;
//     }
// }

// /**
//  * Lädt den Temperaturverlauf der letzten 24 Stunden
//  * Endpoint: GET /api/history?hours=24&limit=200
//  * 
//  * Zeichnet ein Chart.js Liniendiagramm mit roter Linie
//  */
// async function fetchHistory() {
//     try {
//         const response = await fetch(`${API_BASE}/history?hours=24&limit=200`);
//         const data = await response.json();
        
//         if (!data.error && data.length > 0) {
//             // X-Achse: Zeit (nur Stunden:Minuten)
//             const times = data.map(d => {
//                 const date = new Date(d.timestamp);
//                 return date.toLocaleTimeString('de-DE', { 
//                     hour: '2-digit', 
//                     minute: '2-digit' 
//                 });
//             });
            
//             // Y-Achse: Temperaturwerte
//             const temps = data.map(d => d.temperature);
            
//             // Altes Diagramm zerstören (falls vorhanden)
//             if (chart) chart.destroy();
            
//             // Neues Diagramm zeichnen (rote Linie)
//             const ctx = document.getElementById('tempChart').getContext('2d');
//             chart = new Chart(ctx, {
//                 type: 'line',
//                 data: {
//                     labels: times,
//                     datasets: [{
//                         label: 'Temperatur (°C)',
//                         data: temps,
//                         borderColor: '#ff4444',        // ROTE Linie
//                         backgroundColor: 'rgba(255, 68, 68, 0.1)',  // Leichter roter Hintergrund
//                         borderWidth: 2,
//                         fill: true,
//                         tension: 0.4,                  // Leichte Kurvenglättung
//                         pointRadius: 2,
//                         pointHoverRadius: 5,
//                         pointBackgroundColor: '#ff4444'
//                     }]
//                 },
//                 options: {
//                     responsive: true,
//                     maintainAspectRatio: true,
//                     plugins: {
//                         legend: {
//                             labels: { color: '#ffffff' }  // Weiße Legende
//                         },
//                         tooltip: {
//                             mode: 'index',
//                             intersect: false
//                         }
//                     },
//                     scales: {
//                         x: {
//                             ticks: { 
//                                 color: '#ffffff',
//                                 maxRotation: 45,
//                                 minRotation: 45
//                             },
//                             grid: { color: 'rgba(255, 255, 255, 0.1)' }
//                         },
//                         y: {
//                             ticks: { color: '#ffffff' },
//                             grid: { color: 'rgba(255, 255, 255, 0.1)' }
//                         }
//                     }
//                 }
//             });
//         }
//     } catch (error) {
//         console.error('Fehler beim Laden des Temperaturverlaufs:', error);
//     }
// }

// /**
//  * HTML Escape gegen XSS-Angriffe
//  * @param {string} text - Der zu escapende Text
//  * @returns {string} - Escapeter Text
//  */
// function escapeHtml(text) {
//     const div = document.createElement('div');
//     div.textContent = text;
//     return div.innerHTML;
// }

// // ============================================
// // AUTOMATISCHE AKTUALISIERUNG
// // ============================================
// // Alle 10 Sekunden werden alle Daten neu geladen
// setInterval(() => {
//     fetchLatest();
//     fetchStats();
//     fetchDevicesStatus();
//     fetchLWTStats();
//     fetchHistory();
//     fetchFirmwareInfo();
// }, 10000);

// // ============================================
// // INITIALES LADEN BEIM SEITENSTART
// // ============================================
// fetchLatest();
// fetchStats();
// fetchDevicesStatus();
// fetchLWTStats();
// fetchHistory();
// fetchFirmwareInfo();

// // Console-Ausgabe für Debugging
// console.log('🌡️ Dashboard gestartet - Aktualisiert alle 10 Sekunden');

/**
 * ============================================
 * IoT DASHBOARD - JAVASCRIPT
 * ============================================
 * 
 * Version: 3.0 - Korrigierte API-Endpunkte
 * Datum: 06.05.2026
 * 
 * Änderungen:
 * - API_BASE auf richtigen Pfad gesetzt
 * - Fehlerbehandlung verbessert
 * - Debug-Logs hinzugefügt
 * ============================================
 */

// API Basis-URL - muss mit Backend übereinstimmen!
// Dein Nginx proxied /api/ zu http://api_backend:5000/api/
const API_BASE = '/api';

// Chart.js Diagramm-Instanz
let chart = null;

// ============================================
// HILFSFUNKTIONEN
// ============================================

/**
 * API Call mit Fehlerbehandlung
 */
async function apiCall(endpoint) {
    try {
        const url = `${API_BASE}${endpoint}`;
        console.log(`📡 API Call: ${url}`);
        
        const response = await fetch(url);
        
        if (!response.ok) {
            if (response.status === 404) {
                console.warn(`⚠️ Endpoint nicht gefunden: ${endpoint}`);
                return null;
            }
            throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json();
        console.log(`✅ ${endpoint}:`, data);
        return data;
    } catch (error) {
        console.error(`❌ Fehler bei ${endpoint}:`, error);
        return null;
    }
}

// ============================================
// 1. AKTUELLE TEMPERATUR
// ============================================

async function fetchLatest() {
    const data = await apiCall('/latest');
    
    if (data && !data.error) {
        // Temperatur (ROT, GROSS)
        const tempElement = document.getElementById('current-temp');
        if (tempElement) {
            tempElement.innerHTML = data.temperature.toFixed(2) + ' °C';
        }
        
        // Geräte-ID
        const deviceElement = document.getElementById('current-device');
        if (deviceElement) {
            deviceElement.innerHTML = '📟 Gerät: ' + data.device_id;
        }
        
        // Letzte Messung (GELB, GRÖSSER)
        const timeElement = document.getElementById('current-time');
        if (timeElement && data.timestamp) {
            const formattedDate = new Date(data.timestamp).toLocaleString('de-DE', {
                day: '2-digit',
                month: '2-digit',
                year: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            });
            timeElement.innerHTML = '🕐 Letzte Messung: ' + formattedDate;
        }
    } else {
        console.warn('Keine aktuellen Temperaturdaten');
        const tempElement = document.getElementById('current-temp');
        if (tempElement) tempElement.innerHTML = '--.- °C';
    }
}

// ============================================
// 2. STATISTIKEN
// ============================================

async function fetchStats() {
    const data = await apiCall('/stats?hours=24');
    
    if (data && !data.error) {
        const minEl = document.getElementById('min-temp');
        const maxEl = document.getElementById('max-temp');
        const avgEl = document.getElementById('avg-temp');
        const countEl = document.getElementById('count');
        
        if (minEl) minEl.innerHTML = data.min_temp?.toFixed(2) || '--';
        if (maxEl) maxEl.innerHTML = data.max_temp?.toFixed(2) || '--';
        if (avgEl) avgEl.innerHTML = data.avg_temp?.toFixed(2) || '--';
        if (countEl) countEl.innerHTML = data.count || 0;
    }
}

// ============================================
// 3. GERÄTESTATUS
// ============================================

async function fetchDevicesStatus() {
    const data = await apiCall('/devices/status');
    const container = document.getElementById('devices-list');
    
    if (!container) return;
    
    if (data && !data.error && data.length > 0) {
        let html = '';
        
        data.forEach(device => {
            const statusClass = device.status === 'online' ? 'online' : 'offline';
            const statusText = device.status === 'online' ? '🟢 Online' : '🔴 Offline';
            
            let rssiClass = '';
            if (device.last_rssi) {
                if (device.last_rssi > -60) rssiClass = 'signal-good';
                else if (device.last_rssi > -70) rssiClass = 'signal-medium';
                else rssiClass = 'signal-bad';
            }
            
            html += `
                <div class="device-item">
                    <strong>📟 ${escapeHtml(device.device_id)}</strong><br>
                    Status: <span class="${statusClass}">${statusText}</span><br>
                    📶 RSSI: <span class="${rssiClass}">${device.last_rssi || '--'} dBm</span><br>
                    💾 Heap: ${device.last_free_heap || '--'} bytes<br>
                    🕐 Letzte Nachricht: ${device.last_seen ? new Date(device.last_seen).toLocaleString() : 'never'}
                </div>
            `;
        });
        
        container.innerHTML = html;
    } else {
        container.innerHTML = '<div class="device-item">Keine Geräte gefunden</div>';
    }
}

// ============================================
// 4. LWT STATISTIKEN
// ============================================

async function fetchLWTStats() {
    const data = await apiCall('/lwt/stats');
    
    if (data && !data.error) {
        const totalEl = document.getElementById('total-devices');
        const onlineEl = document.getElementById('online-devices');
        const offlineEl = document.getElementById('offline-devices');
        const avgRssiEl = document.getElementById('avg-rssi');
        
        if (totalEl) totalEl.innerHTML = data.total_devices || 0;
        if (onlineEl) onlineEl.innerHTML = data.online_devices || 0;
        if (offlineEl) offlineEl.innerHTML = data.offline_devices || 0;
        if (avgRssiEl) avgRssiEl.innerHTML = data.avg_rssi || '--';
    }
}

// ============================================
// 5. FIRMWARE INFO
// ============================================

async function fetchFirmwareInfo() {
    const data = await apiCall('/firmware/version');
    const container = document.getElementById('firmware-info');
    
    if (!container) return;
    
    if (data && !data.error) {
        const sizeKB = (data.size / 1024).toFixed(2);
        container.innerHTML = `
            📦 Version: <strong>${data.version}</strong><br>
            📏 Größe: ${sizeKB} KB<br>
            🔑 MD5: ${data.md5?.substring(0, 16) || '---'}...
        `;
    } else {
        container.innerHTML = '📦 Keine Firmware vorhanden';
    }
}

// ============================================
// 6. TEMPERATURVERLAUF (DIAGRAMM)
// ============================================

async function fetchHistory() {
    const data = await apiCall('/history?hours=24&limit=200');
    
    if (data && !data.error && data.length > 0) {
        const times = data.map(d => {
            const date = new Date(d.timestamp);
            return date.toLocaleTimeString('de-DE', { 
                hour: '2-digit', 
                minute: '2-digit' 
            });
        });
        
        const temps = data.map(d => d.temperature);
        
        // Altes Diagramm zerstören
        if (chart) chart.destroy();
        
        // Neues Diagramm zeichnen
        const ctx = document.getElementById('tempChart');
        if (ctx) {
            chart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: times,
                    datasets: [{
                        label: 'Temperatur (°C)',
                        data: temps,
                        borderColor: '#ff4444',
                        backgroundColor: 'rgba(255, 68, 68, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.4,
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
                            labels: { color: '#ffffff' }
                        }
                    },
                    scales: {
                        x: {
                            ticks: { 
                                color: '#ffffff',
                                maxRotation: 45,
                                minRotation: 45,
                                autoSkip: true,
                                maxTicksLimit: 12
                            },
                            grid: { color: 'rgba(255, 255, 255, 0.1)' }
                        },
                        y: {
                            ticks: { color: '#ffffff' },
                            grid: { color: 'rgba(255, 255, 255, 0.1)' },
                            title: {
                                display: true,
                                text: 'Temperatur (°C)',
                                color: '#ffffff'
                            }
                        }
                    }
                }
            });
            console.log(`📊 Diagramm gezeichnet mit ${data.length} Datenpunkten`);
        }
    } else {
        console.warn('Keine History-Daten für Diagramm');
    }
}

// ============================================
// 7. FIRMWARE UPLOAD
// ============================================

async function uploadFirmware() {
    const fileInput = document.getElementById('firmware-file');
    const versionInput = document.getElementById('firmware-version');
    const statusDiv = document.getElementById('upload-status');
    
    if (!fileInput || !fileInput.files.length) {
        if (statusDiv) showStatus('❌ Bitte wähle eine Firmware Datei aus', '#ff6666');
        return;
    }
    
    const file = fileInput.files[0];
    const version = versionInput?.value.trim() || '1.0.0';
    
    const formData = new FormData();
    formData.append('file', file);
    formData.append('version', version);
    
    if (statusDiv) showStatus('📤 Upload läuft...', '#FFC107');
    
    try {
        const response = await fetch(`${API_BASE}/firmware/upload`, {
            method: 'POST',
            body: formData
        });
        const data = await response.json();
        
        if (response.ok) {
            showStatus(`✅ Upload erfolgreich (Version ${data.version})`, '#4CAF50');
            fetchFirmwareInfo();
        } else {
            showStatus(`❌ Fehler: ${data.error}`, '#ff6666');
        }
    } catch (error) {
        showStatus(`❌ Upload fehlgeschlagen: ${error.message}`, '#ff6666');
    }
}

// ============================================
// 8. OTA UPDATE AUSLÖSEN
// ============================================

async function triggerOTA() {
    const btn = event?.target;
    if (btn) {
        const originalText = btn.innerHTML;
        btn.innerHTML = '⏳ Wird ausgelöst...';
        btn.disabled = true;
        
        // Hier müsste ein MQTT Befehl an den ESP8266 gesendet werden
        // Aktuell: Simulation
        setTimeout(() => {
            alert('🚀 OTA Update wurde ausgelöst!\n\nDas ESP8266 wird die Firmware herunterladen.');
            btn.innerHTML = originalText;
            btn.disabled = false;
        }, 2000);
    }
}

// ============================================
// 9. HILFSFUNKTIONEN
// ============================================

function showStatus(message, color) {
    const statusDiv = document.getElementById('upload-status');
    if (statusDiv) {
        statusDiv.innerHTML = message;
        statusDiv.style.color = color;
        setTimeout(() => {
            if (statusDiv.innerHTML === message) {
                statusDiv.innerHTML = '';
            }
        }, 5000);
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ============================================
// DASHBOARD INITIALISIERUNG
// ============================================

// Alle 10 Sekunden aktualisieren
setInterval(() => {
    console.log('🔄 Automatische Aktualisierung...');
    fetchLatest();
    fetchStats();
    fetchDevicesStatus();
    fetchLWTStats();
    fetchHistory();
    fetchFirmwareInfo();
}, 10000);

// Initiales Laden
console.log('🌡️ Dashboard gestartet v3.0');
fetchLatest();
fetchStats();
fetchDevicesStatus();
fetchLWTStats();
fetchHistory();
fetchFirmwareInfo();