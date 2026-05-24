-- Migration: V1__init_schema.sql
-- Database: SQLite
-- Strategy: backward-compatible baseline schema for MVP
-- Includes: users, profiles, activities, enrollments, subscriptions, payments (simulation), messages (optional MVP)
-- Soft delete: is_deleted + deleted_at on all business tables

-- =========================
-- UP
-- =========================
PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT NOT NULL,
    email TEXT,
    password_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'disabled', 'banned')),
    last_login_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    is_deleted INTEGER NOT NULL DEFAULT 0 CHECK (is_deleted IN (0,1)),
    deleted_at TEXT,
    UNIQUE (phone),
    UNIQUE (email)
);

CREATE TABLE IF NOT EXISTS profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    display_name TEXT NOT NULL,
    gender TEXT CHECK (gender IN ('male', 'female', 'other', 'unknown')) DEFAULT 'unknown',
    birth_date TEXT,
    city TEXT DEFAULT '成都',
    district TEXT,
    bio TEXT,
    emergency_contact_name TEXT,
    emergency_contact_phone TEXT,
    avatar_url TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    is_deleted INTEGER NOT NULL DEFAULT 0 CHECK (is_deleted IN (0,1)),
    deleted_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT,
    UNIQUE (user_id)
);

CREATE TABLE IF NOT EXISTS activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organizer_user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    category TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    enroll_deadline TEXT,
    location_name TEXT,
    address TEXT,
    latitude REAL,
    longitude REAL,
    capacity INTEGER NOT NULL CHECK (capacity > 0),
    enrolled_count INTEGER NOT NULL DEFAULT 0 CHECK (enrolled_count >= 0),
    fee_cents INTEGER NOT NULL DEFAULT 0 CHECK (fee_cents >= 0),
    status TEXT NOT NULL DEFAULT 'published' CHECK (status IN ('draft', 'published', 'closed', 'cancelled', 'finished')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    is_deleted INTEGER NOT NULL DEFAULT 0 CHECK (is_deleted IN (0,1)),
    deleted_at TEXT,
    FOREIGN KEY (organizer_user_id) REFERENCES users(id) ON DELETE RESTRICT,
    CHECK (end_time >= start_time)
);

CREATE TABLE IF NOT EXISTS enrollments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'enrolled' CHECK (status IN ('enrolled', 'cancelled', 'waitlisted', 'checked_in')),
    source TEXT DEFAULT 'app',
    remark TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    is_deleted INTEGER NOT NULL DEFAULT 0 CHECK (is_deleted IN (0,1)),
    deleted_at TEXT,
    FOREIGN KEY (activity_id) REFERENCES activities(id) ON DELETE RESTRICT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    plan_code TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'expired', 'cancelled', 'paused')),
    start_at TEXT NOT NULL,
    end_at TEXT NOT NULL,
    auto_renew INTEGER NOT NULL DEFAULT 0 CHECK (auto_renew IN (0,1)),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    is_deleted INTEGER NOT NULL DEFAULT 0 CHECK (is_deleted IN (0,1)),
    deleted_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT,
    CHECK (end_at >= start_at)
);

CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    subscription_id INTEGER,
    enrollment_id INTEGER,
    biz_type TEXT NOT NULL CHECK (biz_type IN ('subscription', 'activity')),
    provider TEXT NOT NULL DEFAULT 'mock',
    out_trade_no TEXT NOT NULL,
    amount_cents INTEGER NOT NULL CHECK (amount_cents >= 0),
    currency TEXT NOT NULL DEFAULT 'CNY',
    status TEXT NOT NULL DEFAULT 'created' CHECK (status IN ('created', 'paid', 'failed', 'refunded', 'closed')),
    paid_at TEXT,
    failure_reason TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    is_deleted INTEGER NOT NULL DEFAULT 0 CHECK (is_deleted IN (0,1)),
    deleted_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT,
    FOREIGN KEY (subscription_id) REFERENCES subscriptions(id) ON DELETE SET NULL,
    FOREIGN KEY (enrollment_id) REFERENCES enrollments(id) ON DELETE SET NULL,
    UNIQUE (out_trade_no)
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender_user_id INTEGER NOT NULL,
    receiver_user_id INTEGER,
    activity_id INTEGER,
    channel_type TEXT NOT NULL DEFAULT 'direct' CHECK (channel_type IN ('direct', 'activity')),
    content TEXT NOT NULL,
    content_type TEXT NOT NULL DEFAULT 'text' CHECK (content_type IN ('text', 'image', 'system')),
    read_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    is_deleted INTEGER NOT NULL DEFAULT 0 CHECK (is_deleted IN (0,1)),
    deleted_at TEXT,
    FOREIGN KEY (sender_user_id) REFERENCES users(id) ON DELETE RESTRICT,
    FOREIGN KEY (receiver_user_id) REFERENCES users(id) ON DELETE RESTRICT,
    FOREIGN KEY (activity_id) REFERENCES activities(id) ON DELETE SET NULL,
    CHECK (
      (channel_type = 'direct' AND receiver_user_id IS NOT NULL) OR
      (channel_type = 'activity' AND activity_id IS NOT NULL)
    )
);

-- =========================
-- Indexes (query-oriented)
-- =========================

-- users
CREATE INDEX IF NOT EXISTS idx_users_status_deleted ON users(status, is_deleted);
CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at);

-- profiles
CREATE INDEX IF NOT EXISTS idx_profiles_city_deleted ON profiles(city, is_deleted);

-- activities: list by status/time, organizer queries, deadline filtering
CREATE INDEX IF NOT EXISTS idx_activities_status_start_deleted ON activities(status, start_time, is_deleted);
CREATE INDEX IF NOT EXISTS idx_activities_organizer_status_deleted ON activities(organizer_user_id, status, is_deleted);
CREATE INDEX IF NOT EXISTS idx_activities_deadline_status ON activities(enroll_deadline, status);

-- enrollments: avoid duplicates and support participant list / user history
CREATE UNIQUE INDEX IF NOT EXISTS uk_enrollments_activity_user_active
ON enrollments(activity_id, user_id)
WHERE is_deleted = 0;
CREATE INDEX IF NOT EXISTS idx_enrollments_user_status_deleted ON enrollments(user_id, status, is_deleted);
CREATE INDEX IF NOT EXISTS idx_enrollments_activity_status_deleted ON enrollments(activity_id, status, is_deleted);

-- subscriptions
CREATE INDEX IF NOT EXISTS idx_subscriptions_user_status_deleted ON subscriptions(user_id, status, is_deleted);
CREATE INDEX IF NOT EXISTS idx_subscriptions_end_at_status ON subscriptions(end_at, status);

-- payments
CREATE INDEX IF NOT EXISTS idx_payments_user_status_created ON payments(user_id, status, created_at);
CREATE INDEX IF NOT EXISTS idx_payments_subscription ON payments(subscription_id);
CREATE INDEX IF NOT EXISTS idx_payments_enrollment ON payments(enrollment_id);

-- messages
CREATE INDEX IF NOT EXISTS idx_messages_receiver_read_created ON messages(receiver_user_id, read_at, created_at);
CREATE INDEX IF NOT EXISTS idx_messages_activity_created ON messages(activity_id, created_at);
CREATE INDEX IF NOT EXISTS idx_messages_sender_created ON messages(sender_user_id, created_at);

COMMIT;

-- =========================
-- DOWN
-- =========================
-- NOTE: execute separately for rollback
-- BEGIN TRANSACTION;
-- DROP INDEX IF EXISTS idx_messages_sender_created;
-- DROP INDEX IF EXISTS idx_messages_activity_created;
-- DROP INDEX IF EXISTS idx_messages_receiver_read_created;
-- DROP INDEX IF EXISTS idx_payments_enrollment;
-- DROP INDEX IF EXISTS idx_payments_subscription;
-- DROP INDEX IF EXISTS idx_payments_user_status_created;
-- DROP INDEX IF EXISTS idx_subscriptions_end_at_status;
-- DROP INDEX IF EXISTS idx_subscriptions_user_status_deleted;
-- DROP INDEX IF EXISTS idx_enrollments_activity_status_deleted;
-- DROP INDEX IF EXISTS idx_enrollments_user_status_deleted;
-- DROP INDEX IF EXISTS uk_enrollments_activity_user_active;
-- DROP INDEX IF EXISTS idx_activities_deadline_status;
-- DROP INDEX IF EXISTS idx_activities_organizer_status_deleted;
-- DROP INDEX IF EXISTS idx_activities_status_start_deleted;
-- DROP INDEX IF EXISTS idx_profiles_city_deleted;
-- DROP INDEX IF EXISTS idx_users_created_at;
-- DROP INDEX IF EXISTS idx_users_status_deleted;
-- DROP TABLE IF EXISTS messages;
-- DROP TABLE IF EXISTS payments;
-- DROP TABLE IF EXISTS subscriptions;
-- DROP TABLE IF EXISTS enrollments;
-- DROP TABLE IF EXISTS activities;
-- DROP TABLE IF EXISTS profiles;
-- DROP TABLE IF EXISTS users;
-- COMMIT;
