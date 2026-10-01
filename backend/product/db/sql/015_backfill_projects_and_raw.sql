SET search_path TO master_dashboard, monday;

CREATE OR REPLACE FUNCTION monday.hydrate_from_staging() RETURNS void
LANGUAGE plpgsql AS $$
BEGIN
    ----------------------------------------------------------------
    -- 1) Hydrate monday.items from monday_staging.items_norm
    --    (Keep the newer, cleaner version from 015)
    ----------------------------------------------------------------
    WITH ranked AS (
        SELECT
            board_id,
            item_id,
            raw_json,
            run_id,
            ROW_NUMBER() OVER (
                PARTITION BY item_id
                ORDER BY (board_id IS NULL) ASC,
                         run_id DESC
            ) AS rn
        FROM monday_staging.items_norm
    ),
    latest_items AS (
        SELECT board_id, item_id, raw_json
        FROM ranked
        WHERE rn = 1
    )
    INSERT INTO monday.items (board_id, monday_id, name, raw_json, created_at)
    SELECT
        COALESCE(
            li.board_id,
            NULLIF((li.raw_json->'board'->>'id')::bigint, NULL)
        ) AS board_id,
        li.item_id::bigint                          AS monday_id,
        COALESCE(li.raw_json->>'name','(untitled)') AS name,
        li.raw_json                                  AS raw_json,
        NOW()                                        AS created_at
    FROM latest_items li
    ON CONFLICT (monday_id) DO UPDATE
    SET name       = EXCLUDED.name,
        raw_json   = EXCLUDED.raw_json,
        board_id   = COALESCE(monday.items.board_id, EXCLUDED.board_id),
        updated_at = NOW();

    ----------------------------------------------------------------
    -- 2) Hydrate monday.item_properties from column_values
    --    (Use the CORRECT logic from 013 that matches your JSON)
    ----------------------------------------------------------------
    WITH exploded AS (
        SELECT
            inorm.item_id,
            cv,
            ROW_NUMBER() OVER (
                PARTITION BY inorm.item_id,
                COALESCE(
                    cv->>'column_id',
                    cv->>'id',
                    cv->>'columnId'
                )
                ORDER BY inorm.run_id DESC
            ) AS rn
        FROM monday_staging.items_norm inorm
        CROSS JOIN LATERAL jsonb_array_elements(inorm.raw_json->'column_values') AS cv
    ),
    latest_props AS (
        SELECT
            item_id AS monday_item_id,

            COALESCE(
                cv->>'column_id',
                cv->>'id',
                cv->>'columnId'
            ) AS column_id,

            NULLIF(
                COALESCE(
                    cv->>'raw_text',
                    cv->'parsed'->>'text',
                    cv->>'text'
                ), ''
            ) AS value_text,

            CASE WHEN (cv->>'raw_text') ~ '^[+-]?([0-9]*[.])?[0-9]+$'
                THEN (cv->>'raw_text')::numeric END AS value_number,

            CASE WHEN (cv->>'raw_text') ~ '^\d{4}-\d{2}-\d{2}$'
                THEN (cv->>'raw_text')::date END AS value_date,

            cv          AS raw_json,
            cv->>'title' AS title
        FROM exploded
        WHERE rn = 1
          AND COALESCE(
                cv->>'column_id',
                cv->>'id',
                cv->>'columnId'
              ) IS NOT NULL
    )
    INSERT INTO monday.item_properties (
        monday_item_id,
        column_id,
        value_text,
        value_number,
        value_date,
        raw_json,
        title
    )
    SELECT
        monday_item_id,
        column_id,
        value_text,
        value_number,
        value_date,
        raw_json,
        title
    FROM latest_props
    ON CONFLICT (monday_item_id, column_id) DO UPDATE
    SET value_text   = EXCLUDED.value_text,
        value_number = EXCLUDED.value_number,
        value_date   = EXCLUDED.value_date,
        raw_json     = EXCLUDED.raw_json,
        title        = EXCLUDED.title;

    ----------------------------------------------------------------
    -- 3) Hydrate monday.item_assignees from people/assignee columns
    --    (Use the newer parsed.personsAndTeams logic from 013)
    ----------------------------------------------------------------
    WITH exploded_people AS (
        SELECT
            inorm.item_id,
            cv,
            ROW_NUMBER() OVER (
                PARTITION BY inorm.item_id, (cv->>'title')
                ORDER BY inorm.run_id DESC
            ) AS rn
        FROM monday_staging.items_norm inorm
        CROSS JOIN LATERAL jsonb_array_elements(inorm.raw_json->'column_values') AS cv
        WHERE (cv->>'title') ILIKE '%assignee%'
           OR (cv->>'title') ILIKE '%people%'
    ),
    latest_people AS (
        SELECT
            ep.item_id AS monday_item_id,
            (jsonb_array_elements(
                COALESCE(
                    ep.cv->'parsed'->'personsAndTeams',
                    '[]'::jsonb
                )
            )->>'id')::bigint AS monday_user_id
        FROM exploded_people ep
        WHERE ep.rn = 1
    )
    INSERT INTO monday.item_assignees (monday_item_id, monday_user_id)
    SELECT DISTINCT
        monday_item_id,
        monday_user_id
    FROM latest_people
    WHERE monday_user_id IS NOT NULL
    ON CONFLICT (monday_item_id, monday_user_id) DO NOTHING;

END;
$$;
