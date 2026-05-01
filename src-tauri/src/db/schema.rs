use rusqlite::Connection;

pub fn init(conn: &Connection) -> rusqlite::Result<()> {
    conn.execute_batch(
        "CREATE TABLE IF NOT EXISTS workflows (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            nodes TEXT NOT NULL DEFAULT '[]',
            edges TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS recent_files (
            path TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            opened_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS profiles (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            fingerprint TEXT NOT NULL DEFAULT '{}',
            user_data_dir TEXT NOT NULL DEFAULT '',
            proxy TEXT,
            os_target TEXT NOT NULL DEFAULT 'windows',
            browser_config TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );",
    )?;
    // Migration: add browser_config column if missing
    let _ = conn.execute(
        "ALTER TABLE profiles ADD COLUMN browser_config TEXT NOT NULL DEFAULT '{}'",
        [],
    );
    Ok(())
}
