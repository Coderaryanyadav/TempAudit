-- 004_user_onboarding_and_firm_profile.sql
-- Adds support for User Invitation/Activation flows and Setup Wizard state tracking.
-- This migration is applied via backend/migrations/runner.py, which inspects the existing
-- schema and skips column/index creation when a legacy database already contains these fields.

-- 1. Ensure user onboarding columns exist in users table
ALTER TABLE users ADD COLUMN designation TEXT;
ALTER TABLE users ADD COLUMN status TEXT DEFAULT 'ACTIVE'; -- ACTIVE, INVITED, DISABLED, LOCKED
ALTER TABLE users ADD COLUMN activation_token TEXT;
ALTER TABLE users ADD COLUMN activation_expires_at TEXT;

-- 2. User Activation Index
CREATE INDEX IF NOT EXISTS idx_users_activation_token ON users(activation_token);
CREATE INDEX IF NOT EXISTS idx_users_status ON users(status);
