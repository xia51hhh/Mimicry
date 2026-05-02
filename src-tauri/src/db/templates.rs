use rusqlite::{params, Connection};
use serde::{Deserialize, Serialize};
use tracing::warn;

fn parse_json_or_default(s: &str, field: &str, id: &str) -> serde_json::Value {
    serde_json::from_str(s).unwrap_or_else(|e| {
        warn!("Failed to parse {} for template {}: {}", field, id, e);
        serde_json::Value::Array(vec![])
    })
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Template {
    pub id: String,
    pub name: String,
    pub description: String,
    pub category: String,
    pub nodes: serde_json::Value,
    pub edges: serde_json::Value,
    pub tags: serde_json::Value,
    pub created_at: String,
    pub updated_at: String,
}

pub fn create(conn: &Connection, t: &Template) -> rusqlite::Result<()> {
    conn.execute(
        "INSERT INTO templates (id, name, description, category, nodes, edges, tags, created_at, updated_at) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9)",
        params![t.id, t.name, t.description, t.category, t.nodes.to_string(), t.edges.to_string(), t.tags.to_string(), t.created_at, t.updated_at],
    )?;
    Ok(())
}

pub fn get(conn: &Connection, id: &str) -> rusqlite::Result<Option<Template>> {
    let mut stmt = conn.prepare(
        "SELECT id, name, description, category, nodes, edges, tags, created_at, updated_at FROM templates WHERE id = ?1",
    )?;
    let mut rows = stmt.query(params![id])?;
    match rows.next()? {
        Some(row) => {
            let id_val: String = row.get(0)?;
            let nodes_str: String = row.get(4)?;
            let edges_str: String = row.get(5)?;
            let tags_str: String = row.get(6)?;
            Ok(Some(Template {
                id: id_val.clone(),
                name: row.get(1)?,
                description: row.get(2)?,
                category: row.get(3)?,
                nodes: parse_json_or_default(&nodes_str, "nodes", &id_val),
                edges: parse_json_or_default(&edges_str, "edges", &id_val),
                tags: parse_json_or_default(&tags_str, "tags", &id_val),
                created_at: row.get(7)?,
                updated_at: row.get(8)?,
            }))
        }
        None => Ok(None),
    }
}

pub fn list(conn: &Connection) -> rusqlite::Result<Vec<Template>> {
    let mut stmt = conn.prepare(
        "SELECT id, name, description, category, nodes, edges, tags, created_at, updated_at FROM templates ORDER BY updated_at DESC",
    )?;
    let rows = stmt.query_map([], |row| {
        let id_val: String = row.get(0)?;
        let nodes_str: String = row.get(4)?;
        let edges_str: String = row.get(5)?;
        let tags_str: String = row.get(6)?;
        Ok(Template {
            id: id_val.clone(),
            name: row.get(1)?,
            description: row.get(2)?,
            category: row.get(3)?,
            nodes: parse_json_or_default(&nodes_str, "nodes", &id_val),
            edges: parse_json_or_default(&edges_str, "edges", &id_val),
            tags: parse_json_or_default(&tags_str, "tags", &id_val),
            created_at: row.get(7)?,
            updated_at: row.get(8)?,
        })
    })?;
    rows.collect()
}

pub fn update(conn: &Connection, t: &Template) -> rusqlite::Result<()> {
    conn.execute(
        "UPDATE templates SET name = ?1, description = ?2, category = ?3, nodes = ?4, edges = ?5, tags = ?6, updated_at = ?7 WHERE id = ?8",
        params![t.name, t.description, t.category, t.nodes.to_string(), t.edges.to_string(), t.tags.to_string(), t.updated_at, t.id],
    )?;
    Ok(())
}

pub fn delete(conn: &Connection, id: &str) -> rusqlite::Result<()> {
    conn.execute("DELETE FROM templates WHERE id = ?1", params![id])?;
    Ok(())
}
