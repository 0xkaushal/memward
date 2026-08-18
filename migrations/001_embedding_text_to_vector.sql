-- Migration 001: Convert memories.embedding from TEXT (JSON string) to pgvector VECTOR(1536)
--
-- Run this once against the Supabase Postgres database before restarting the app.
-- Requires pgvector extension to already be enabled (Supabase enables it by default).
--
-- The existing JSON string embeddings are cast to the native vector type.
-- Rows with NULL or empty/invalid embeddings are left as NULL.

-- Ensure pgvector extension is present
CREATE EXTENSION IF NOT EXISTS vector;

-- Step 1: Add a new vector column alongside the old text column
ALTER TABLE memories ADD COLUMN IF NOT EXISTS embedding_vec vector(1536);

-- Step 2: Migrate existing data — cast JSON text arrays to vector
--   Rows where embedding is NULL, empty, or '[]' are left as NULL.
UPDATE memories
SET embedding_vec = embedding::vector
WHERE embedding IS NOT NULL
  AND embedding != ''
  AND embedding != '[]'
  AND embedding != 'null';

-- Step 3: Drop the old text column
ALTER TABLE memories DROP COLUMN IF EXISTS embedding;

-- Step 4: Rename the new column to the canonical name
ALTER TABLE memories RENAME COLUMN embedding_vec TO embedding;

-- Step 5: Create an IVFFlat index for approximate cosine similarity search.
--   lists=100 is a reasonable default for up to ~1M rows.
--   Adjust lists based on row count: lists ≈ sqrt(rows) is a common heuristic.
CREATE INDEX IF NOT EXISTS memories_embedding_ivfflat_idx
    ON memories
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
