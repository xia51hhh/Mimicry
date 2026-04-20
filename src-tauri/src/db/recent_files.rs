use rusqlite::{params, Connection};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RecentFile {
    pub path: String,
    pub name: String,
    pub opened_at: String,
}

pub fn upsert(conn: &Connection, file: &RecentFile) -> rusqlite::Result<()> {
    conn.execute(
        "INSERT OR REPLACE INTO recent_files (path, name, opened_at) VALUES (?1, ?2, ?3)",
        params![file.path, file.name, file.opened_at],
    )?;
    Ok(())
}

pub fn list(conn: &Connection, limit: usize) -> rusqlite::Result<Vec<RecentFile>> {
    let mut stmt = conn.prepare(
        "SELECT path, name, opened_at FROM recent_files ORDER BY opened_at DESC LIMIT ?1",
    )?;
    let rows = stmt.query_map(params![limit as i64], |row| {
        Ok(RecentFile {
            path: row.get(0)?,
            name: row.get(1)?,
            opened_at: row.get(2)?,
        })
    })?;
    rows.collect()
}

pub fn remove(conn: &Connection, path: &str) -> rusqlite::Result<()> {
    conn.execute("DELETE FROM recent_files WHERE path = ?1", params![path])?;
    Ok(())
}

pub fn clear(conn: &Connection) -> rusqlite::Result<()> {
    conn.execute("DELETE FROM recent_files", [])?;
    Ok(())
}
