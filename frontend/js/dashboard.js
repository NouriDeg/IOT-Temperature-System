/**
 * ============================================
 * IoT DASHBOARD - ALLE GERÄTE TEMPERATUREN
 * ============================================
 * 
 * Version: 6.0
 * Datum: 16.08.2026
 * 
 * Funktionen:
 * - Alle Geräte mit aktuellen Temperaturen
 * - Statistik (Min, Max, Avg, Count)
 * - LWT Status (Online/Offline)
 * - Geräte Status Liste
 * - OTA Firmware Management
 * - Temperaturverlauf Diagramm
 * ============================================
 */

// ============================================
// GLOBALE KONSTANTEN & VARIABLEN
// ============================================

// Basis-URL für alle API-Aufrufe (relativer Pfad, da Frontend und Backend über Nginx verbunden sind)
const API_BASE = '/api';

// Chart.js Diagramm-Instanz (wird später initialisiert)
let chart = null;

// ============================================
// 1. API HELPER - Zentrale Funktion für alle API-Aufrufe
// ============================================

/**
 * Führt einen asynchronen API-Aufruf durch und gibt die JSON-Daten zurück.
 * Bei Fehlern wird null zurückgegeben und der Fehler in der Konsole geloggt.
 * 
 * @param {string} endpoint - Der API-Endpunkt (z.B. '/devices/status')
 * @returns {Promise<Object|null>} Die JSON-Antwort oder null bei Fehler
 */
async function apiCall(endpoint) {
    try {
        // Vollständige URL aus Basis und Endpunkt zusammensetzen
        const url = `${API_BASE}${endpoint}`;
        
        // Debug-Ausgabe in der Browser-Konsole (für Fehlersuche)
        console.log(`📡 API Call: ${url}`);
        
        // HTTP GET Request an den Server senden
        const response = await fetch(url);
        
        // Prüfen ob die Antwort erfolgreich war (Status 200-299)
        if (!response.ok) {
            // Bei 404 (Not Found) geben wir null zurück, ohne Fehler zu werfen
            if (response.status === 404) return null;
            // Bei anderen Fehlern werfen wir eine Exception
            throw new Error(`HTTP ${response.status}`);
        }
        
        // JSON-Daten aus der Antwort parsen und zurückgeben
        return await response.json();
    } catch (error) {
        // Fehler in der Konsole ausgeben
        console.error(`❌ Fehler bei ${endpoint}:`, error);
        // null zurückgeben, damit der Aufrufer nicht abstürzt
        return null;
    }
}

// ============================================
// 2. AKTUELLE TEMPERATUREN (ALLE GERÄTE)
// ============================================

/**
 * Ruft alle Geräte mit ihren aktuellen Temperaturen ab und zeigt sie an.
 * Diese Funktion wird beim Start und alle 10 Sekunden aufgerufen.
 */
async function fetchCurrentTemperatures() {
    // Debug-Ausgabe
    console.log('🔄 Lade aktuelle Temperaturen...');
    
    // HTML-Container für die Temperatur-Anzeige finden
    const container = document.getElementById('current-temps-container');
    
    // Sicherheitsprüfung: Wenn der Container nicht existiert, abbrechen
    if (!container) {
        console.error('❌ Container #current-temps-container nicht gefunden!');
        return;
    }

    // API-Aufruf: Alle Geräte mit Status und Temperatur abrufen
    const devices = await apiCall('/devices/status');
    
    // Prüfen ob Geräte vorhanden sind
    if (!devices || devices.length === 0) {
        // Fehlermeldung im Container anzeigen
        container.innerHTML = '<div class="loading">⚠️ Keine Geräte gefunden</div>';
        return;
    }

    // Debug: Anzahl der gefundenen Geräte anzeigen
    console.log(`📊 ${devices.length} Geräte gefunden`);

    // HTML-Code für alle Geräte zusammenbauen
    let html = '';
    
    // Jedes Gerät durchlaufen und eine Zeile im HTML erstellen
    devices.forEach(device => {
        // Prüfen ob das Gerät online ist (Status aus der API)
        const isOnline = device.status === 'online';
        
        // Temperatur auslesen (kann null oder undefined sein)
        const temp = device.last_temperature;
        
        // Temperatur formatieren: Bei Online und vorhandenem Wert mit 2 Nachkommastellen, sonst "--"
        const tempDisplay = isOnline && temp !== null && temp !== undefined 
            ? temp.toFixed(2) 
            : '--';
        
        // CSS-Klasse für Online/Offline-Status
        const statusClass = isOnline ? 'online' : 'offline';
        
        // Anzeigetext für Status (mit Emoji)
        const statusText = isOnline ? '🟢 Online' : '🔴 Offline';
        
        // Letzte Nachricht formatieren: Datum in deutsches Format umwandeln
        const lastSeen = device.last_seen 
            ? new Date(device.last_seen).toLocaleString('de-DE') 
            : 'Nie';

        // HTML-Zeile für dieses Gerät erstellen
        html += `
            <div class="current-temp-item">
                <span class="device-id">📟 ${escapeHtml(device.device_id)}</span>
                <span class="device-temp ${!isOnline ? 'offline' : ''}">${tempDisplay} °C</span>
                <span class="device-status ${statusClass}">${statusText}</span>
                <span class="last-seen">${lastSeen}</span>
            </div>
        `;
    });

    // HTML-Code in den Container einfügen
    container.innerHTML = html;
    
    // Debug: Erfolgsmeldung
    console.log('✅ Aktuelle Temperaturen gerendert');
}

// ============================================
// 3. STATISTIK (letzte 24h)
// ============================================

/**
 * Ruft statistische Kennzahlen der letzten 24 Stunden ab und zeigt sie an.
 * Werte: Minimum, Maximum, Durchschnitt, Anzahl Messungen
 */
async function fetchStats() {
    // API-Aufruf: Statistiken für die letzten 24 Stunden
    const data = await apiCall('/stats?hours=24');
    
    // Prüfen ob Daten vorhanden sind
    if (data && !data.error) {
        // Jedes Statistik-Feld im HTML aktualisieren
        // Falls kein Wert vorhanden, wird "--" angezeigt
        document.getElementById('min-temp').textContent = data.min_temp?.toFixed(2) || '--';
        document.getElementById('max-temp').textContent = data.max_temp?.toFixed(2) || '--';
        document.getElementById('avg-temp').textContent = data.avg_temp?.toFixed(2) || '--';
        document.getElementById('count').textContent = data.count || 0;
    }
}

// ============================================
// 4. LWT STATUS (Last Will Testament)
// ============================================

/**
 * Ruft LWT-Statistiken ab: Gesamtgeräte, Online/Offline, durchschnittliche RSSI.
 * LWT = Last Will Testament - ein Mechanismus, der den Online-Status der Geräte überwacht.
 */
async function fetchLWTStats() {
    // API-Aufruf: LWT-Statistiken
    const data = await apiCall('/lwt/stats');
    
    if (data && !data.error) {
        // Alle LWT-Felder im HTML aktualisieren
        document.getElementById('total-devices').textContent = data.total_devices || 0;
        document.getElementById('online-devices').textContent = data.online_devices || 0;
        document.getElementById('offline-devices').textContent = data.offline_devices || 0;
        document.getElementById('avg-rssi').textContent = data.avg_rssi?.toFixed(2) || '--';
    }
}

// ============================================
// 5. GERÄTE STATUS (DETAILLISTE)
// ============================================

/**
 * Zeigt eine detaillierte Liste aller Geräte mit Status, Temperatur, RSSI, Heap und letzter Nachricht.
 * Diese Liste wird in der mittleren Karte des Dashboards angezeigt.
 */
async function fetchDevicesStatus() {
    // HTML-Container für die Geräteliste finden
    const container = document.getElementById('devices-list');
    if (!container) return;

    // API-Aufruf: Alle Geräte mit Status
    const devices = await apiCall('/devices/status');
    
    // Prüfen ob Geräte vorhanden sind
    if (!devices || devices.length === 0) {
        container.innerHTML = '<div class="loading">⚠️ Keine Geräte gefunden</div>';
        return;
    }

    // HTML-Code für die Geräteliste zusammenbauen
    let html = '';
    devices.forEach(device => {
        // Status prüfen
        const isOnline = device.status === 'online';
        const statusClass = isOnline ? 'online' : 'offline';
        const statusText = isOnline ? '🟢 Online' : '🔴 Offline';
        
        // Temperatur formatieren
        const temp = device.last_temperature;
        const tempDisplay = isOnline && temp !== null && temp !== undefined 
            ? temp.toFixed(2) 
            : '--';
        
        // Letzte Nachricht formatieren
        const lastSeen = device.last_seen 
            ? new Date(device.last_seen).toLocaleString('de-DE') 
            : 'Nie';

        // HTML-Eintrag für dieses Gerät erstellen
        html += `
            <div class="device-item">
                <!-- Geräte-ID (fett) -->
                <div class="device-name">📟 ${escapeHtml(device.device_id)}</div>
                <!-- Status, Temperatur, RSSI, Heap in einer Zeile -->
                <div>
                    Status: <span class="device-status ${statusClass}">${statusText}</span>
                    &nbsp;|&nbsp; 🌡️ ${tempDisplay} °C
                    &nbsp;|&nbsp; 📶 ${device.last_rssi || '--'} dBm
                    &nbsp;|&nbsp; 💾 ${device.last_free_heap || '--'} bytes
                </div>
                <!-- Letzte Nachricht (kleiner, grau) -->
                <div class="device-details">🕐 Letzte Nachricht: ${lastSeen}</div>
            </div>
        `;
    });

    // HTML in den Container einfügen
    container.innerHTML = html;
}

// ============================================
// 6. TEMPERATURVERLAUF (DIAGRAMM)
// ============================================

/**
 * Ruft den Temperaturverlauf der letzten 24 Stunden ab und zeichnet ein Diagramm mit Chart.js.
 * Die Daten werden als Zeitreihe dargestellt.
 */
async function fetchHistory() {
    // API-Aufruf: Historische Daten (max. 200 Punkte)
    const data = await apiCall('/history?hours=24&limit=200');
    
    // Prüfen ob Daten vorhanden sind
    if (data && data.length > 0) {
        // Zeitstempel für die X-Achse extrahieren (nur Uhrzeit)
        const times = data.map(d => {
            const date = new Date(d.timestamp);
            // Format: "HH:MM" (z.B. "14:30")
            return date.toLocaleTimeString('de-DE', { 
                hour: '2-digit', 
                minute: '2-digit' 
            });
        });
        
        // Temperaturwerte für die Y-Achse extrahieren
        const temps = data.map(d => d.temperature);

        // Altes Diagramm zerstören (falls vorhanden), um Speicherlecks zu vermeiden
        if (chart) chart.destroy();

        // Canvas-Element für das Diagramm finden
        const ctx = document.getElementById('tempChart');
        if (ctx) {
            // Neues Chart.js-Diagramm erstellen
            chart = new Chart(ctx, {
                // Diagramm-Typ: Liniendiagramm
                type: 'line',
                data: {
                    labels: times,           // X-Achse: Zeitstempel
                    datasets: [{
                        label: 'Temperatur (°C)',
                        data: temps,         // Y-Achse: Temperaturwerte
                        borderColor: '#ff4444',        // Linienfarbe: Rot
                        backgroundColor: 'rgba(255, 68, 68, 0.1)', // Füllfarbe: Rot mit Transparenz
                        borderWidth: 2,                 // Liniendicke
                        fill: true,                     // Fläche unter der Linie füllen
                        tension: 0.4,                   // Kurvenglättung (0.4 = leicht gerundet)
                        pointRadius: 2,                 // Größe der Datenpunkte
                        pointHoverRadius: 5,            // Größe beim Hovern
                        pointBackgroundColor: '#ff4444' // Farbe der Datenpunkte
                    }]
                },
                options: {
                    // Diagramm reagiert auf Fenstergrößenänderungen
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {
                        // Legende (oben rechts)
                        legend: {
                            labels: { color: '#ffffff' } // Weiße Schrift
                        }
                    },
                    scales: {
                        // X-Achse (Zeit)
                        x: {
                            ticks: { 
                                color: '#ffffff',        // Weiße Schrift
                                maxRotation: 45,         // Max. Drehung der Labels
                                minRotation: 45,         // Min. Drehung der Labels
                                autoSkip: true,          // Labels automatisch ausdünnen
                                maxTicksLimit: 12        // Max. 12 Labels anzeigen
                            },
                            grid: { color: 'rgba(255, 255, 255, 0.1)' } // Helle Gitterlinien
                        },
                        // Y-Achse (Temperatur)
                        y: {
                            ticks: { color: '#ffffff' }, // Weiße Schrift
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
            // Debug: Anzahl der Datenpunkte ausgeben
            console.log(`📊 Diagramm gezeichnet mit ${data.length} Datenpunkten`);
        }
    }
}

// ============================================
// 7. OTA FIRMWARE MANAGEMENT
// ============================================

/**
 * Ruft Informationen über die aktuelle Firmware ab (Version, Größe, MD5).
 * Wird in der OTA-Karte angezeigt.
 */
async function fetchFirmwareInfo() {
    // API-Aufruf: Firmware-Informationen
    const data = await apiCall('/firmware/version');
    const container = document.getElementById('firmware-info');
    if (!container) return;

    if (data && !data.error) {
        // Größe von Bytes in KB umrechnen
        const sizeKB = (data.size / 1024).toFixed(2);
        // HTML für die Firmware-Info erstellen
        container.innerHTML = `
            📦 Version: <strong>${data.version}</strong><br>
            📏 Größe: ${sizeKB} KB<br>
            🔑 MD5: ${data.md5?.substring(0, 16) || '---'}...
        `;
    } else {
        // Keine Firmware vorhanden
        container.innerHTML = '📦 Keine Firmware vorhanden';
    }
}

/**
 * Lädt eine neue Firmware-Datei (.bin) auf den Server hoch.
 * Wird über den "Firmware hochladen" Button ausgelöst.
 */
async function uploadFirmware() {
    // HTML-Elemente aus dem Formular holen
    const fileInput = document.getElementById('firmware-file');
    const versionInput = document.getElementById('firmware-version');
    const statusDiv = document.getElementById('upload-status');

    // Prüfen ob eine Datei ausgewählt wurde
    if (!fileInput || !fileInput.files.length) {
        showStatus('❌ Bitte wähle eine Firmware Datei aus', '#ff6666');
        return;
    }

    // Datei und Version auslesen
    const file = fileInput.files[0];
    const version = versionInput?.value.trim() || '1.0.0';

    // FormData für den Upload vorbereiten (multipart/form-data)
    const formData = new FormData();
    formData.append('file', file);
    formData.append('version', version);

    // Status: Upload läuft
    showStatus('📤 Upload läuft...', '#FFC107');

    try {
        // POST Request an den Upload-Endpunkt
        const response = await fetch(`${API_BASE}/firmware/upload`, {
            method: 'POST',
            body: formData
        });
        const data = await response.json();

        // Erfolg oder Fehler anzeigen
        if (response.ok) {
            showStatus(`✅ Upload erfolgreich (Version ${data.version})`, '#4CAF50');
            fetchFirmwareInfo(); // Firmware-Info aktualisieren
        } else {
            showStatus(`❌ Fehler: ${data.error}`, '#ff6666');
        }
    } catch (error) {
        showStatus(`❌ Upload fehlgeschlagen: ${error.message}`, '#ff6666');
    }
}

/**
 * Löst ein OTA-Update für alle Geräte aus.
 * Aktuell wird nur eine Bestätigung angezeigt (Simulation).
 */
function triggerOTA() {
    // Alert anzeigen (später durch echten MQTT-Befehl ersetzbar)
    alert('🚀 OTA Update wurde ausgelöst!\n\nDas ESP8266 wird die Firmware herunterladen und installieren.');
}

// ============================================
// 8. HILFSFUNKTIONEN
// ============================================

/**
 * Zeigt eine Statusmeldung im Upload-Bereich an.
 * Die Meldung verschwindet nach 5 Sekunden automatisch.
 * 
 * @param {string} message - Die anzuzeigende Nachricht
 * @param {string} color - Die Farbe des Texts (CSS-Farbwert)
 */
function showStatus(message, color) {
    const statusDiv = document.getElementById('upload-status');
    if (statusDiv) {
        // Nachricht und Farbe setzen
        statusDiv.innerHTML = message;
        statusDiv.style.color = color;
        // Nach 5 Sekunden löschen (nur wenn keine neue Nachricht kam)
        setTimeout(() => {
            if (statusDiv.innerHTML === message) {
                statusDiv.innerHTML = '';
            }
        }, 5000);
    }
}

/**
 * Entfernt gefährliche HTML-Zeichen aus einem Text, um XSS-Angriffe zu verhindern.
 * Wandelt z.B. "<" in "&lt;" um.
 * 
 * @param {string} text - Der zu bereinigende Text
 * @returns {string} Der bereinigte Text
 */
function escapeHtml(text) {
    // Temporäres DIV-Element erstellen
    const div = document.createElement('div');
    // Text als reinen Text setzen (automatische Escaping)
    div.textContent = text;
    // HTML-kodierten Text zurückgeben
    return div.innerHTML;
}

// ============================================
// 9. DASHBOARD INITIALISIERUNG
// ============================================

// Debug: Startmeldung in der Konsole
console.log('🌡️ Dashboard v6.0 gestartet');

// --------------------------------------------
// INITIALES LADEN (beim ersten Seitenaufruf)
// --------------------------------------------

// Alle Daten einmalig beim Start laden
fetchCurrentTemperatures();   // Aktuelle Temperaturen aller Geräte
fetchStats();                // Statistik der letzten 24h
fetchLWTStats();             // LWT Status (Online/Offline)
fetchDevicesStatus();        // Detaillierte Geräteliste
fetchHistory();              // Temperaturverlauf (Diagramm)
fetchFirmwareInfo();         // OTA Firmware Informationen

// --------------------------------------------
// LIVE-UPDATE (alle 10 Sekunden)
// --------------------------------------------

/**
 * Automatische Aktualisierung aller Daten im 10-Sekunden-Takt.
 * So bleibt das Dashboard immer auf dem neuesten Stand.
 */
setInterval(() => {
    // Debug: Aktualisierung in der Konsole anzeigen
    console.log('🔄 Automatische Aktualisierung...');
    
    // Alle Daten neu laden
    fetchCurrentTemperatures();
    fetchStats();
    fetchLWTStats();
    fetchDevicesStatus();
    fetchHistory();
    fetchFirmwareInfo();
}, 10000); // 10.000 Millisekunden = 10 Sekunden

// ============================================
// ENDE DER DASHBOARD.JS
// ============================================