-- schema.sql
-- Project: n8n_0523_2114
-- Purpose: Initial logical/physical schema for users/events/registrations/messages/audit_logs
-- Notes:
-- 1) PostgreSQL 14+
-- 2) Backward-compatible, additive-first design
-- 3) PII follows ciphertext + hash dual-track strategy

BEGIN;

-- =========================================================
-- Extensions
-- =========================================================
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- =========================================================
-- Common trigger for updated_at
-- =========================================================
CREATE OR REPLACE FUNCTION trg_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- =========================================================
-- users
-- =========================================================
CREATE TABLE IF NOT EXISTS users (
  id BIGSERIAL PRIMARY KEY,
  user_no VARCHAR(32) NOT NULL UNIQUE,

  display_name VARCHAR(100) NOT NULL,
  avatar_url TEXT,
  gender SMALLINT,
  birth_year SMALLINT,
  city_code VARCHAR(20) NOT NULL DEFAULT '510100',
  status SMALLINT NOT NULL DEFAULT 1,

  phone_ciphertext BYTEA,
  phone_hash CHAR(64),
  phone_mask VARCHAR(32),

  email_ciphertext BYTEA,
  email_hash CHAR(64),
  email_mask VARCHAR(128),

  real_name_ciphertext BYTEA,
  real_name_hash CHAR(64),

  id_doc_ciphertext BYTEA,
  id_doc_hash CHAR(64),

  last_login_at TIMESTAMPTZ,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,

  CONSTRAINT chk_users_gender CHECK (gender IS NULL OR gender IN (0,1,2)),
  CONSTRAINT chk_users_birth_year CHECK (birth_year IS NULL OR (birth_year BETWEEN 1900 AND EXTRACT(YEAR FROM NOW())::INT)),
  CONSTRAINT chk_users_deleted_consistency CHECK ((is_deleted = FALSE AND deleted_at IS NULL) OR (is_deleted = TRUE AND deleted_at IS NOT NULL))
);

CREATE UNIQUE INDEX IF NOT EXISTS uk_users_phone_hash ON users(phone_hash) WHERE phone_hash IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uk_users_email_hash ON users(email_hash) WHERE email_hash IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uk_users_id_doc_hash ON users(id_doc_hash) WHERE id_doc_hash IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_users_city_status ON users(city_code, status) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at);

DROP TRIGGER IF EXISTS trg_users_updated_at ON users;
CREATE TRIGGER trg_users_updated_at
BEFORE UPDATE ON users
FOR EACH ROW EXECUTE FUNCTION trg_set_updated_at();

-- =========================================================
-- events
-- =========================================================
CREATE TABLE IF NOT EXISTS events (
  id BIGSERIAL PRIMARY KEY,
  event_no VARCHAR(32) NOT NULL UNIQUE,
  organizer_user_id BIGINT NOT NULL,

  title VARCHAR(200) NOT NULL,
  description TEXT,
  category VARCHAR(50) NOT NULL,

  city_code VARCHAR(20) NOT NULL DEFAULT '510100',
  district VARCHAR(100),
  venue_name VARCHAR(200),
  venue_address TEXT,
  geo_lat NUMERIC(9,6),
  geo_lng NUMERIC(9,6),

  start_time TIMESTAMPTZ NOT NULL,
  end_time TIMESTAMPTZ NOT NULL,
  signup_deadline TIMESTAMPTZ NOT NULL,

  capacity INTEGER NOT NULL,
  registered_count INTEGER NOT NULL DEFAULT 0,
  waitlist_count INTEGER NOT NULL DEFAULT 0,

  fee_cents INTEGER NOT NULL DEFAULT 0,
  currency CHAR(3) NOT NULL DEFAULT 'CNY',

  status SMALLINT NOT NULL DEFAULT 1,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,

  CONSTRAINT fk_events_organizer FOREIGN KEY (organizer_user_id) REFERENCES users(id),
  CONSTRAINT chk_events_time CHECK (start_time < end_time),
  CONSTRAINT chk_events_deadline CHECK (signup_deadline <= start_time),
  CONSTRAINT chk_events_capacity CHECK (capacity > 0),
  CONSTRAINT chk_events_registered_count CHECK (registered_count >= 0 AND registered_count <= capacity),
  CONSTRAINT chk_events_waitlist_count CHECK (waitlist_count >= 0),
  CONSTRAINT chk_events_fee CHECK (fee_cents >= 0),
  CONSTRAINT chk_events_currency CHECK (currency ~ '^[A-Z]{3}$'),
  CONSTRAINT chk_events_deleted_consistency CHECK ((is_deleted = FALSE AND deleted_at IS NULL) OR (is_deleted = TRUE AND deleted_at IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS idx_events_city_start_status ON events(city_code, start_time, status) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_events_category_start ON events(category, start_time) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_events_organizer ON events(organizer_user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_signup_deadline ON events(signup_deadline) WHERE status = 1 AND is_deleted = FALSE;

DROP TRIGGER IF EXISTS trg_events_updated_at ON events;
CREATE TRIGGER trg_events_updated_at
BEFORE UPDATE ON events
FOR EACH ROW EXECUTE FUNCTION trg_set_updated_at();

-- =========================================================
-- registrations
-- =========================================================
CREATE TABLE IF NOT EXISTS registrations (
  id BIGSERIAL PRIMARY KEY,
  registration_no VARCHAR(32) NOT NULL UNIQUE,
  event_id BIGINT NOT NULL,
  user_id BIGINT NOT NULL,

  status SMALLINT NOT NULL DEFAULT 1,
  source VARCHAR(30) NOT NULL DEFAULT 'app',
  remark VARCHAR(500),

  canceled_at TIMESTAMPTZ,
  checked_in_at TIMESTAMPTZ,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,

  CONSTRAINT fk_registrations_event FOREIGN KEY (event_id) REFERENCES events(id),
  CONSTRAINT fk_registrations_user FOREIGN KEY (user_id) REFERENCES users(id),
  CONSTRAINT chk_registrations_status CHECK (status IN (1,2,3,4)),
  CONSTRAINT chk_registrations_deleted_consistency CHECK ((is_deleted = FALSE AND deleted_at IS NULL) OR (is_deleted = TRUE AND deleted_at IS NOT NULL)),
  CONSTRAINT uk_registrations_event_user_active UNIQUE (event_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_registrations_user_status_time ON registrations(user_id, status, created_at DESC) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_registrations_event_status_time ON registrations(event_id, status, created_at DESC) WHERE is_deleted = FALSE;

DROP TRIGGER IF EXISTS trg_registrations_updated_at ON registrations;
CREATE TRIGGER trg_registrations_updated_at
BEFORE UPDATE ON registrations
FOR EACH ROW EXECUTE FUNCTION trg_set_updated_at();

-- =========================================================
-- messages
-- =========================================================
CREATE TABLE IF NOT EXISTS messages (
  id BIGSERIAL PRIMARY KEY,
  event_id BIGINT NOT NULL,
  sender_user_id BIGINT NOT NULL,

  content_ciphertext BYTEA NOT NULL,
  content_hash CHAR(64),
  content_mask TEXT,

  message_type SMALLINT NOT NULL DEFAULT 1,
  reply_to_message_id BIGINT,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  deleted_at TIMESTAMPTZ,

  CONSTRAINT fk_messages_event FOREIGN KEY (event_id) REFERENCES events(id),
  CONSTRAINT fk_messages_sender FOREIGN KEY (sender_user_id) REFERENCES users(id),
  CONSTRAINT fk_messages_reply FOREIGN KEY (reply_to_message_id) REFERENCES messages(id),
  CONSTRAINT chk_messages_type CHECK (message_type IN (1,2,3)),
  CONSTRAINT chk_messages_deleted_consistency CHECK ((is_deleted = FALSE AND deleted_at IS NULL) OR (is_deleted = TRUE AND deleted_at IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS idx_messages_event_created ON messages(event_id, created_at DESC) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_messages_sender_created ON messages(sender_user_id, created_at DESC);

DROP TRIGGER IF EXISTS trg_messages_updated_at ON messages;
CREATE TRIGGER trg_messages_updated_at
BEFORE UPDATE ON messages
FOR EACH ROW EXECUTE FUNCTION trg_set_updated_at();

-- =========================================================
-- audit_logs (append-only)
-- =========================================================
CREATE TABLE IF NOT EXISTS audit_logs (
  id BIGSERIAL PRIMARY KEY,
  event_id UUID NOT NULL DEFAULT gen_random_uuid(),
  event_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  actor_type VARCHAR(20) NOT NULL,
  actor_id VARCHAR(100) NOT NULL,
  role_snapshot JSONB,

  action VARCHAR(50) NOT NULL,
  resource_type VARCHAR(30) NOT NULL,
  resource_id VARCHAR(100),

  pii_scope VARCHAR(10),
  purpose_code VARCHAR(30),
  result VARCHAR(10) NOT NULL,

  client_ip INET,
  trace_id VARCHAR(100),
  before_hash CHAR(64),
  after_hash CHAR(64),
  metadata JSONB,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  CONSTRAINT chk_audit_actor_type CHECK (actor_type IN ('human','service','system')),
  CONSTRAINT chk_audit_result CHECK (result IN ('SUCCESS','FAIL')),
  CONSTRAINT chk_audit_pii_scope CHECK (pii_scope IS NULL OR pii_scope IN ('S1','S2','S3'))
);

CREATE UNIQUE INDEX IF NOT EXISTS uk_audit_logs_event_id ON audit_logs(event_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_time ON audit_logs(event_time DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_actor_time ON audit_logs(actor_id, event_time DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action_time ON audit_logs(action, event_time DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_resource ON audit_logs(resource_type, resource_id);

-- append-only guard
CREATE OR REPLACE FUNCTION trg_block_audit_logs_mutation()
RETURNS TRIGGER AS $$
BEGIN
  RAISE EXCEPTION 'audit_logs is append-only; UPDATE/DELETE are forbidden';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_audit_logs_no_update ON audit_logs;
CREATE TRIGGER trg_audit_logs_no_update
BEFORE UPDATE ON audit_logs
FOR EACH ROW EXECUTE FUNCTION trg_block_audit_logs_mutation();

DROP TRIGGER IF EXISTS trg_audit_logs_no_delete ON audit_logs;
CREATE TRIGGER trg_audit_logs_no_delete
BEFORE DELETE ON audit_logs
FOR EACH ROW EXECUTE FUNCTION trg_block_audit_logs_mutation();

COMMIT;
