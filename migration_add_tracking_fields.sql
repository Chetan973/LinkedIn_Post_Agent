-- Migration: Add Post Tracking and Idempotency Fields
--
-- This migration adds support for:
-- 1. Idempotency key (prevent duplicate posts)
-- 2. LinkedIn post ID tracking (manage published posts)
-- 3. Published timestamp (audit trail)
-- 4. Error reason (debugging)
--
-- Safe to run multiple times (uses IF NOT EXISTS)

-- Add idempotency_key column (for duplicate prevention)
ALTER TABLE posts
ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(255) UNIQUE;

-- Add linkedin_post_id column (track published post on LinkedIn)
ALTER TABLE posts
ADD COLUMN IF NOT EXISTS linkedin_post_id VARCHAR(255) UNIQUE;

-- Add published_at column (when post was published)
ALTER TABLE posts
ADD COLUMN IF NOT EXISTS published_at TIMESTAMP WITH TIME ZONE;

-- Add error_reason column (debugging failed publishes)
ALTER TABLE posts
ADD COLUMN IF NOT EXISTS error_reason TEXT;

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_posts_idempotency_key
ON posts(idempotency_key);

CREATE INDEX IF NOT EXISTS idx_posts_linkedin_post_id
ON posts(linkedin_post_id);

-- Verify migration
SELECT
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'posts'
ORDER BY ordinal_position;

-- Expected output:
-- post_id | bigint | NO
-- user_id | bigint | NO
-- topic | character varying | NO
-- draft_content | text | YES
-- final_content | text | YES
-- status | character varying | NO
-- idempotency_key | character varying | YES         ← NEW
-- linkedin_post_id | character varying | YES        ← NEW
-- published_at | timestamp with time zone | YES     ← NEW
-- error_reason | text | YES                         ← NEW
-- created_at | timestamp with time zone | NO
-- updated_at | timestamp with time zone | NO
