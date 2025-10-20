-- Performance Index Migration for Gemlaunch.fun
-- Date: October 20, 2025
-- Purpose: Add database indexes following DeFi best practices
-- 
-- IMPORTANT: This migration uses CREATE INDEX CONCURRENTLY to avoid blocking writes
-- Run this script against the PostgreSQL database to apply performance optimizations

-- ============================================================================
-- Token Model Indexes
-- ============================================================================

-- Index for marketplace sorting by creation date (newest first)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_token_created_at 
ON token USING btree (created_at);

-- Composite index for filtered marketplace queries (active vs graduated tokens)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_token_graduated_created 
ON token USING btree (is_graduated, created_at);

-- Index for blockchain traceability and fraud detection
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_token_deployment_tx 
ON token USING btree (deployment_tx);

-- ============================================================================
-- TradeEvent Model Indexes
-- ============================================================================

-- Composite index for time-series queries (price charts, bonding curve calculations)
-- Using DESC on timestamp for efficient latest-first queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trade_event_token_time 
ON trade_event USING btree (token_id, timestamp DESC);

-- ============================================================================
-- Verification & Performance Testing
-- ============================================================================

-- Verify indexes were created
SELECT 
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
AND (
    indexname LIKE 'idx_token_%' 
    OR indexname LIKE 'idx_trade_event_%'
)
ORDER BY tablename, indexname;

-- Show table sizes and index usage
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS total_size,
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) AS table_size,
    pg_size_pretty(pg_indexes_size(schemaname||'.'||tablename)) AS indexes_size
FROM pg_tables
WHERE schemaname = 'public'
AND tablename IN ('token', 'trade_event', 'holding')
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
