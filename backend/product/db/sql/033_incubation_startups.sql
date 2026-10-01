CREATE TABLE IF NOT EXISTS master_dashboard.incubation_startups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    monday_board_id TEXT NOT NULL,
    monday_item_id  TEXT NOT NULL,

    startup_name TEXT,
    cycle_name   TEXT,

    status TEXT,
    lead_name TEXT,
    fund_interested BOOLEAN,
    marketing_interested BOOLEAN,
    comments TEXT,

    cmbu_label TEXT,
    project_id UUID REFERENCES master_dashboard.projects(id),

    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_incubation_item
ON master_dashboard.incubation_startups (monday_board_id, monday_item_id);
