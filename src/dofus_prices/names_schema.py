"""SQL of the item-name reference table and of the named views (pure constants)."""

NAMES_SCHEMA_STATEMENTS = (
    """CREATE TABLE IF NOT EXISTS items (
        item_id INTEGER PRIMARY KEY, name_fr TEXT NOT NULL, level INTEGER,
        type_fr TEXT NOT NULL DEFAULT '')""",
    """CREATE TABLE IF NOT EXISTS servers (
        server_id INTEGER PRIMARY KEY, name_fr TEXT NOT NULL, game_type_id INTEGER,
        game_type_fr TEXT NOT NULL DEFAULT '', community_id INTEGER)""",
    # Every lot_prices column plus the name; 'N/A' marks an id missing from items.
    """CREATE VIEW IF NOT EXISTS lot_prices_named AS
        SELECT lot.*, COALESCE(items.name_fr, 'N/A') AS item_name,
               items.level AS item_level, items.type_fr AS item_type
        FROM lot_prices AS lot LEFT JOIN items ON items.item_id = lot.item_id""",
    # Every market_stats column except points_json (the price curve), to keep it light.
    """CREATE VIEW IF NOT EXISTS market_stats_named AS
        SELECT stats.id, stats.item_id, stats.server, stats.period, stats.median, stats.mean,
               stats.sold_count, stats.server_updated_at, stats.last_purchase_at,
               stats.captured_at, COALESCE(items.name_fr, 'N/A') AS item_name,
               items.level AS item_level, items.type_fr AS item_type
        FROM market_stats AS stats LEFT JOIN items ON items.item_id = stats.item_id""",
    # One row per item id seen in prices or statistics but absent from items.
    """CREATE VIEW IF NOT EXISTS unknown_items AS
        SELECT item_id, SUM(lot_rows) AS lot_price_rows, SUM(stats_rows) AS stats_rows,
               MIN(first_seen) AS first_seen, MAX(last_seen) AS last_seen
        FROM (
            SELECT item_id, COUNT(*) AS lot_rows, 0 AS stats_rows,
                   MIN(captured_at) AS first_seen, MAX(captured_at) AS last_seen
            FROM lot_prices GROUP BY item_id
            UNION ALL
            SELECT item_id, 0, COUNT(*), MIN(captured_at), MAX(captured_at)
            FROM market_stats GROUP BY item_id)
        WHERE item_id NOT IN (SELECT item_id FROM items)
        GROUP BY item_id ORDER BY item_id""",
)
