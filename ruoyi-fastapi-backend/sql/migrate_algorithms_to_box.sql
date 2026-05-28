-- Migration: move all three built-in algorithms to external_box runtime
-- Run this against existing databases to switch algorithm execution to edge boxes.

UPDATE xuzhou_alg SET alg_runtime_type = 'external_box' WHERE alg_runtime_type = 'local';

-- Verify
SELECT alg_id, alg_name, alg_serial, alg_runtime_type FROM xuzhou_alg;
