use rusqlite::{params, Connection};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Workflow {
    pub id: String,
    pub name: String,
    pub nodes: serde_json::Value,
    pub edges: serde_json::Value,
    pub created_at: String,
    pub updated_at: String,
}

pub fn create(conn: &Connection, wf: &Workflow) -> rusqlite::Result<()> {
    conn.execute(
        "INSERT INTO workflows (id, name, nodes, edges, created_at, updated_at) VALUES (?1, ?2, ?3, ?4, ?5, ?6)",
        params![wf.id, wf.name, wf.nodes.to_string(), wf.edges.to_string(), wf.created_at, wf.updated_at],
    )?;
    Ok(())
}

pub fn get(conn: &Connection, id: &str) -> rusqlite::Result<Option<Workflow>> {
    let mut stmt = conn.prepare("SELECT id, name, nodes, edges, created_at, updated_at FROM workflows WHERE id = ?1")?;
    let mut rows = stmt.query(params![id])?;
    match rows.next()? {
        Some(row) => {
            let nodes_str: String = row.get(2)?;
            let edges_str: String = row.get(3)?;
            Ok(Some(Workflow {
                id: row.get(0)?,
                name: row.get(1)?,
                nodes: serde_json::from_str(&nodes_str).unwrap_or_default(),
                edges: serde_json::from_str(&edges_str).unwrap_or_default(),
                created_at: row.get(4)?,
                updated_at: row.get(5)?,
            }))
        }
        None => Ok(None),
    }
}

pub fn list(conn: &Connection) -> rusqlite::Result<Vec<Workflow>> {
    let mut stmt = conn.prepare("SELECT id, name, nodes, edges, created_at, updated_at FROM workflows ORDER BY updated_at DESC")?;
    let rows = stmt.query_map([], |row| {
        let nodes_str: String = row.get(2)?;
        let edges_str: String = row.get(3)?;
        Ok(Workflow {
            id: row.get(0)?,
            name: row.get(1)?,
            nodes: serde_json::from_str(&nodes_str).unwrap_or_default(),
            edges: serde_json::from_str(&edges_str).unwrap_or_default(),
            created_at: row.get(4)?,
            updated_at: row.get(5)?,
        })
    })?;
    rows.collect()
}

pub fn update(conn: &Connection, wf: &Workflow) -> rusqlite::Result<()> {
    conn.execute(
        "UPDATE workflows SET name = ?1, nodes = ?2, edges = ?3, updated_at = ?4 WHERE id = ?5",
        params![wf.name, wf.nodes.to_string(), wf.edges.to_string(), wf.updated_at, wf.id],
    )?;
    Ok(())
}

pub fn delete(conn: &Connection, id: &str) -> rusqlite::Result<()> {
    conn.execute("DELETE FROM workflows WHERE id = ?1", params![id])?;
    Ok(())
}

pub fn export_json(conn: &Connection) -> rusqlite::Result<String> {
    let workflows = list(conn)?;
    Ok(serde_json::to_string_pretty(&workflows).unwrap_or_default())
}

pub fn import_json(conn: &Connection, json: &str) -> Result<usize, Box<dyn std::error::Error>> {
    let workflows: Vec<Workflow> = serde_json::from_str(json)?;
    let count = workflows.len();
    for wf in &workflows {
        conn.execute(
            "INSERT OR REPLACE INTO workflows (id, name, nodes, edges, created_at, updated_at) VALUES (?1, ?2, ?3, ?4, ?5, ?6)",
            params![wf.id, wf.name, wf.nodes.to_string(), wf.edges.to_string(), wf.created_at, wf.updated_at],
        )?;
    }
    Ok(count)
}
