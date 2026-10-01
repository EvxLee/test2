SET search_path TO master_dashboard;

CREATE TABLE IF NOT EXISTS board_config (
    id              SERIAL PRIMARY KEY,
    board_key       VARCHAR(100) NOT NULL UNIQUE,
    label           VARCHAR(200) NOT NULL,
    category        VARCHAR(50)  NOT NULL,
    year            INTEGER,
    display_order   INTEGER NOT NULL DEFAULT 0,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    monday_board_id VARCHAR(50),
    env_var_name    VARCHAR(200),
    mapper_type     VARCHAR(100),
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_board_config_is_active
    ON board_config (is_active);

CREATE INDEX IF NOT EXISTS idx_board_config_category
    ON board_config (category);

CREATE INDEX IF NOT EXISTS idx_board_config_mapper_type
    ON board_config (mapper_type);

-- Keep existing admin edits, but fill in missing seed metadata on older rows.
-- monday_board_id stays admin-controlled once set in the table.
INSERT INTO board_config (board_key, label, category, year, display_order, is_active, monday_board_id, env_var_name, mapper_type) VALUES
    -- GCED / Pre-CAP cycles
    ('precap_2024_cycle5', 'Pre-CAP 2024 Cycle 5', 'gced', 2024,  1, TRUE, NULL,        'MONDAY_BOARD_PRECAP_2024_CYCLE5_ID', 'gced'),
    ('precap_2024_cycle6', 'Pre-CAP 2024 Cycle 6', 'gced', 2024,  2, TRUE, NULL,        'MONDAY_BOARD_PRECAP_2024_CYCLE6_ID', 'gced'),
    ('precap_2024_cycle7', 'Pre-CAP 2024 Cycle 7', 'gced', 2024,  3, TRUE, NULL,        'MONDAY_BOARD_PRECAP_2024_CYCLE7_ID', 'gced'),
    ('cycle1_2025',       'Cycle 1',              'gced', 2025,  4, TRUE, '1000000014', 'MONDAY_BOARD_PRECAP_2025_CYCLE1_ID', 'gced'),
    ('cycle2_2025',       'Cycle 2',              'gced', 2025,  5, TRUE, '1000000015', 'MONDAY_BOARD_PRECAP_2025_CYCLE2_ID', 'gced'),
    ('cycle3_2025',       'Cycle 3',              'gced', 2025,  6, TRUE, '1000000016', 'MONDAY_BOARD_PRECAP_2025_CYCLE3_ID', 'gced'),
    ('cycle4_2025',       'Cycle 4',              'gced', 2025,  7, TRUE, '1000000017', 'MONDAY_BOARD_PRECAP_2025_CYCLE4_ID', 'gced'),
    ('cycle5_2025',       'Cycle 5',              'gced', 2025,  8, TRUE, '1000000018', 'MONDAY_BOARD_PRECAP_2025_CYCLE5_ID', 'gced'),
    ('cycle6_2025',       'Cycle 6',              'gced', 2025,  9, TRUE, '1000000019', 'MONDAY_BOARD_PRECAP_2025_CYCLE6_ID', 'gced'),
    ('cycle7_2025',       'Cycle 7',              'gced', 2025, 10, TRUE, '10000000020','MONDAY_BOARD_PRECAP_2025_CYCLE7_ID', 'gced'),
    ('cycle1_2026',       'Cycle 1',              'gced', 2026, 11, TRUE, '10000000021','MONDAY_BOARD_PRECAP_2026_CYCLE1_ID', 'gced'),
    ('precap_2026_cycle2', 'Pre-CAP 2026 Cycle 2', 'gced', 2026, 12, TRUE, NULL,        'MONDAY_BOARD_PRECAP_2026_CYCLE2_ID', 'gced'),
    ('precap_2026_cycle3', 'Pre-CAP 2026 Cycle 3', 'gced', 2026, 13, TRUE, NULL,        'MONDAY_BOARD_PRECAP_2026_CYCLE3_ID', 'gced'),
    ('precap_2026_cycle4', 'Pre-CAP 2026 Cycle 4', 'gced', 2026, 14, TRUE, NULL,        'MONDAY_BOARD_PRECAP_2026_CYCLE4_ID', 'gced'),
    ('precap_2026_cycle5', 'Pre-CAP 2026 Cycle 5', 'gced', 2026, 15, TRUE, NULL,        'MONDAY_BOARD_PRECAP_2026_CYCLE5_ID', 'gced'),
    ('precap_2026_cycle6', 'Pre-CAP 2026 Cycle 6', 'gced', 2026, 16, TRUE, NULL,        'MONDAY_BOARD_PRECAP_2026_CYCLE6_ID', 'gced'),
    ('precap_2026_cycle7', 'Pre-CAP 2026 Cycle 7', 'gced', 2026, 17, TRUE, NULL,        'MONDAY_BOARD_PRECAP_2026_CYCLE7_ID', 'gced'),

    -- GCED backend ingestion boards
    ('gced_mftf25_cycle1', 'GCED MFTF25 Cycle 1', 'gced_ingest', NULL, 20, TRUE, NULL,          'MONDAY_BOARD_GCED_MFTF25_CYCLE1_ID', 'gced'),
    ('gced_mftf25_cycle2', 'GCED MFTF25 Cycle 2', 'gced_ingest', NULL, 21, TRUE, NULL,          'MONDAY_BOARD_GCED_MFTF25_CYCLE2_ID', 'gced'),
    ('gced_mftf25_cycle3', 'GCED MFTF25 Cycle 3', 'gced_ingest', NULL, 22, TRUE, NULL,          'MONDAY_BOARD_GCED_MFTF25_CYCLE3_ID', 'gced'),
    ('gced_mftf25_cycle4', 'GCED MFTF25 Cycle 4', 'gced_ingest', NULL, 23, TRUE, '10000000012', 'MONDAY_BOARD_GCED_MFTF25_CYCLE4_ID', 'gced'),
    ('gced_mftf25_cycle5', 'GCED MFTF25 Cycle 5', 'gced_ingest', NULL, 24, TRUE, '10000000013', 'MONDAY_BOARD_GCED_MFTF25_CYCLE5_ID', 'gced'),
    ('gced_mftf25_cycle6', 'GCED MFTF25 Cycle 6', 'gced_ingest', NULL, 25, TRUE, NULL,          'MONDAY_BOARD_GCED_MFTF25_CYCLE6_ID', 'gced'),
    ('gced_mftf25_cycle7', 'GCED MFTF25 Cycle 7', 'gced_ingest', NULL, 26, TRUE, NULL,          'MONDAY_BOARD_GCED_MFTF25_CYCLE7_ID', 'gced'),
    ('gced_mftf26_cycle1', 'GCED MFTF26 Cycle 1', 'gced_ingest', NULL, 27, TRUE, NULL,          'MONDAY_BOARD_GCED_MFTF26_CYCLE1_ID', 'gced'),

    -- Incubation and project boards
    ('incubation_ai',        'Incubation AI',         'incubation', NULL, 40, TRUE, '10000000005', 'MONDAY_BOARD_INCUBATION_AI_ID', 'incubation'),
    ('incubation_cleantech', 'Incubation Clean Tech', 'incubation', NULL, 41, TRUE, '10000000004', 'MONDAY_BOARD_INCUBATION_CLEAN_TECH_ID', 'incubation'),
    ('incubation_health',    'Incubation Healthcare', 'incubation', NULL, 42, TRUE, '10000000006', 'MONDAY_BOARD_INCUBATION_HEALTHCARE_ID', 'incubation'),
    ('incubation_projects',  'Incubation Projects',   'incubation', NULL, 43, TRUE, '1000000001',  'MONDAY_BOARD_INCUBATION_PROJECTS_ID', 'incubation_projects'),
    ('pjt_it',               'PJT Board IT',          'incubation', NULL, 44, TRUE, NULL,          'MONDAY_BOARD_PJT_IT', 'pjt_it'),

    -- Contract, proposal, marketing, and file boards
    ('projects',              'Projects',              'other', NULL, 60, TRUE, '10000000007', 'MONDAY_BOARD_MARKETING_VENTURES_PROJECTS_ID', 'new_ventures'),
    ('contracts',             'Contracts',             'other', NULL, 61, TRUE, '10000000008', 'MONDAY_BOARD_CONTRACT_STATUS_ID', 'contract_status'),
    ('contract_status_2',     'Contracts 2',           'other', NULL, 62, TRUE, '10000000009', 'MONDAY_BOARD_CONTRACT_STATUS_2_ID', 'contract_status'),
    ('new_venture_proposals', 'New Venture Proposals', 'other', NULL, 63, TRUE, '10000000010', 'MONDAY_BOARD_NEW_VENTURE_PROPOSALS_ID', 'new_venture_proposals'),
    ('korean',                'Regional',              'other', NULL, 64, TRUE, '10000000011', 'MONDAY_BOARD_KOREAN_ID', 'korean'),
    ('default',               'Default Monday Board',  'other', NULL, 65, TRUE, NULL,          'MONDAY_BOARD_ID', NULL),
    ('ai_locate_file',        'AI Locate File',        'files', NULL, 80, TRUE, NULL,          'MONDAY_BOARD_AI_LOCATE_FILE_ID', 'ai_locate_file')
ON CONFLICT (board_key) DO UPDATE SET
    label = COALESCE(board_config.label, EXCLUDED.label),
    category = COALESCE(board_config.category, EXCLUDED.category),
    year = COALESCE(board_config.year, EXCLUDED.year),
    display_order = COALESCE(board_config.display_order, EXCLUDED.display_order),
    is_active = COALESCE(board_config.is_active, EXCLUDED.is_active),
    monday_board_id = COALESCE(board_config.monday_board_id, EXCLUDED.monday_board_id),
    env_var_name = COALESCE(board_config.env_var_name, EXCLUDED.env_var_name),
    mapper_type = COALESCE(board_config.mapper_type, EXCLUDED.mapper_type),
    updated_at = now();
