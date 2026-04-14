-- postgres/init.sql
-- Flexible Tabelle für verschiedene Sensortypen

CREATE TABLE IF NOT EXISTS sensor_data (
    id BIGSERIAL PRIMARY KEY,
    device_id VARCHAR(64) NOT NULL,
    device_type VARCHAR(32),
    sensor_type VARCHAR(32),
    value DECIMAL(10,2),
    unit VARCHAR(16),
    raw_payload JSONB,                    -- Vollständiges JSON für Flexibilität
    received_at TIMESTAMPTZ DEFAULT NOW(),
    created_at BIGINT
);

CREATE TABLE IF NOT EXISTS device_status (
    device_id VARCHAR(64) PRIMARY KEY,
    status VARCHAR(20),
    last_seen TIMESTAMPTZ DEFAULT NOW(),
    last_rssi INTEGER,
    last_free_heap INTEGER,
    firmware_version VARCHAR(20),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indizes
CREATE INDEX idx_sensor_data_device_time ON sensor_data(device_id, received_at DESC);
CREATE INDEX idx_sensor_data_type ON sensor_data(sensor_type, received_at DESC);
CREATE INDEX idx_sensor_data_json ON sensor_data USING GIN (raw_payload);