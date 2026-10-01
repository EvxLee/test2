CREATE INDEX IF NOT EXISTS ix_monday_items_board ON monday.items(board_id);
CREATE INDEX IF NOT EXISTS ix_monday_items_active ON monday.items(is_active);
CREATE INDEX IF NOT EXISTS ix_monday_props_col ON monday.item_properties(column_id);