use rusqlite::{params, Connection};
use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct Profile {
    pub id: String,
    pub name: String,
    pub fingerprint: serde_json::Value,
    pub user_data_dir: String,
    pub proxy: Option<serde_json::Value>,
    pub os_target: String,
    pub created_at: String,
    pub updated_at: String,
}

pub fn list(conn: &Connection) -> rusqlite::Result<Vec<Profile>> {
    let mut stmt = conn.prepare(
        "SELECT id, name, fingerprint, user_data_dir, proxy, os_target, created_at, updated_at
         FROM profiles ORDER BY updated_at DESC",
    )?;
    let rows = stmt.query_map([], |row| {
        let fp_str: String = row.get(2)?;
        let proxy_str: Option<String> = row.get(4)?;
        Ok(Profile {
            id: row.get(0)?,
            name: row.get(1)?,
            fingerprint: serde_json::from_str(&fp_str)
                .unwrap_or(serde_json::Value::Object(Default::default())),
            user_data_dir: row.get(3)?,
            proxy: proxy_str.and_then(|s| serde_json::from_str(&s).ok()),
            os_target: row.get(5)?,
            created_at: row.get(6)?,
            updated_at: row.get(7)?,
        })
    })?;
    rows.collect()
}

pub fn get(conn: &Connection, id: &str) -> rusqlite::Result<Option<Profile>> {
    let mut stmt = conn.prepare(
        "SELECT id, name, fingerprint, user_data_dir, proxy, os_target, created_at, updated_at
         FROM profiles WHERE id = ?",
    )?;
    let mut rows = stmt.query_map(params![id], |row| {
        let fp_str: String = row.get(2)?;
        let proxy_str: Option<String> = row.get(4)?;
        Ok(Profile {
            id: row.get(0)?,
            name: row.get(1)?,
            fingerprint: serde_json::from_str(&fp_str)
                .unwrap_or(serde_json::Value::Object(Default::default())),
            user_data_dir: row.get(3)?,
            proxy: proxy_str.and_then(|s| serde_json::from_str(&s).ok()),
            os_target: row.get(5)?,
            created_at: row.get(6)?,
            updated_at: row.get(7)?,
        })
    })?;
    rows.next().transpose()
}

pub fn create(conn: &Connection, profile: &Profile) -> rusqlite::Result<()> {
    conn.execute(
        "INSERT INTO profiles (id, name, fingerprint, user_data_dir, proxy, os_target, created_at, updated_at)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)",
        params![
            profile.id,
            profile.name,
            serde_json::to_string(&profile.fingerprint).unwrap_or_default(),
            profile.user_data_dir,
            profile.proxy.as_ref().map(|p| serde_json::to_string(p).unwrap_or_default()),
            profile.os_target,
            profile.created_at,
            profile.updated_at,
        ],
    )?;
    Ok(())
}

pub fn update(conn: &Connection, profile: &Profile) -> rusqlite::Result<()> {
    conn.execute(
        "UPDATE profiles SET name=?2, fingerprint=?3, user_data_dir=?4, proxy=?5, os_target=?6, updated_at=?7
         WHERE id=?1",
        params![
            profile.id,
            profile.name,
            serde_json::to_string(&profile.fingerprint).unwrap_or_default(),
            profile.user_data_dir,
            profile.proxy.as_ref().map(|p| serde_json::to_string(p).unwrap_or_default()),
            profile.os_target,
            profile.updated_at,
        ],
    )?;
    Ok(())
}

pub fn delete(conn: &Connection, id: &str) -> rusqlite::Result<()> {
    conn.execute("DELETE FROM profiles WHERE id = ?", params![id])?;
    Ok(())
}
