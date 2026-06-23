use std::path::Path;

use anyhow::{Result, bail};
use chrono::NaiveDate;
use rusqlite::{Connection, params};

use crate::events::{EventKind, StoredEvent, VesselAnimation};

#[derive(Debug, Clone, PartialEq)]
pub struct Dashboard {
    pub initialized: bool,
    pub total_days: u32,
    pub daily_task: String,
    pub position: u32,
    pub completed_days: u32,
    pub coins: i32,
    pub trust: i32,
    pub mood: i32,
    pub streak: u32,
    pub current_vessel: String,
    pub animation: VesselAnimation,
    pub owned_items: Vec<String>,
    pub owned_vessels: Vec<String>,
    pub last_action_date: Option<NaiveDate>,
    pub last_action_kind: Option<String>,
    pub latest_log: Option<String>,
}

pub struct Projection {
    conn: Connection,
}

impl Projection {
    pub fn open(path: &Path) -> Result<Self> {
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent)?;
        }
        let conn = Connection::open(path)?;
        let this = Self { conn };
        this.init()?;
        Ok(this)
    }

    fn init(&self) -> Result<()> {
        self.conn.execute_batch(
            r#"
            CREATE TABLE IF NOT EXISTS app_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                initialized INTEGER NOT NULL DEFAULT 0,
                total_days INTEGER NOT NULL DEFAULT 120,
                daily_task TEXT NOT NULL DEFAULT '未设置 - 运行 init 设置每日任务',
                position INTEGER NOT NULL DEFAULT 0,
                completed_days INTEGER NOT NULL DEFAULT 0,
                coins INTEGER NOT NULL DEFAULT 0,
                trust INTEGER NOT NULL DEFAULT 20,
                mood INTEGER NOT NULL DEFAULT 60,
                streak INTEGER NOT NULL DEFAULT 0,
                current_vessel TEXT NOT NULL DEFAULT 'starter_sloop',
                animation TEXT NOT NULL DEFAULT 'idle',
                last_action_date TEXT,
                last_action_kind TEXT
            );
            CREATE TABLE IF NOT EXISTS logs (
                event_id TEXT PRIMARY KEY,
                date TEXT NOT NULL,
                text TEXT NOT NULL,
                source TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS purchases (
                item_id TEXT PRIMARY KEY
            );
            CREATE TABLE IF NOT EXISTS owned_items (
                item_id TEXT PRIMARY KEY,
                kind TEXT NOT NULL
            );
            INSERT OR IGNORE INTO app_state (id) VALUES (1);
            "#,
        )?;
        add_column_if_missing(
            &self.conn,
            "app_state",
            "daily_task",
            "TEXT NOT NULL DEFAULT '未设置 - 运行 init 设置每日任务'",
        )?;
        add_column_if_missing(&self.conn, "app_state", "last_action_date", "TEXT")?;
        add_column_if_missing(&self.conn, "app_state", "last_action_kind", "TEXT")?;
        Ok(())
    }

    pub fn rebuild(&mut self, events: Vec<StoredEvent>) -> Result<()> {
        let tx = self.conn.transaction()?;
        tx.execute("DELETE FROM logs", [])?;
        tx.execute("DELETE FROM purchases", [])?;
        tx.execute("DELETE FROM owned_items", [])?;
        tx.execute(
            "UPDATE app_state SET initialized=0,total_days=120,daily_task='未设置 - 运行 init 设置每日任务',position=0,completed_days=0,coins=0,trust=20,mood=60,streak=0,current_vessel='starter_sloop',animation='idle',last_action_date=NULL,last_action_kind=NULL WHERE id=1",
            [],
        )?;

        for event in events {
            match event.kind {
                EventKind::VoyageInitialized {
                    total_days,
                    daily_task,
                    vessel_id,
                    ..
                } => {
                    tx.execute(
                        "UPDATE app_state SET initialized=1,total_days=?,daily_task=?,current_vessel=?,animation='waiting' WHERE id=1",
                        params![total_days, daily_task, vessel_id],
                    )?;
                    tx.execute(
                        "INSERT OR IGNORE INTO owned_items (item_id,kind) VALUES (?,'vessel')",
                        params![vessel_id],
                    )?;
                }
                EventKind::DailyCheckInCompleted {
                    date,
                    new_position,
                    coins_breakdown,
                    trust_delta,
                    mood_delta,
                    animation,
                    template_narrative,
                    ..
                } => {
                    let coins: i32 = coins_breakdown.iter().map(|c| c.amount).sum();
                    tx.execute(
                        "UPDATE app_state SET position=?,completed_days=completed_days+1,coins=coins+?,trust=MIN(100,MAX(0,trust+?)),mood=MIN(100,MAX(0,mood+?)),streak=streak+1,animation=?,last_action_date=?,last_action_kind='check_in' WHERE id=1",
                        params![new_position, coins, trust_delta, mood_delta, animation_name(animation), date.to_string()],
                    )?;
                    tx.execute(
                        "INSERT OR REPLACE INTO logs (event_id,date,text,source) VALUES (?,?,?,'template')",
                        params![event.id.to_string(), date.to_string(), template_narrative],
                    )?;
                }
                EventKind::DaySkipped {
                    date,
                    mood_delta,
                    animation,
                    template_narrative,
                    ..
                } => {
                    tx.execute(
                        "UPDATE app_state SET mood=MIN(100,MAX(0,mood+?)),streak=0,animation=?,last_action_date=?,last_action_kind='skip' WHERE id=1",
                        params![mood_delta, animation_name(animation), date.to_string()],
                    )?;
                    tx.execute(
                        "INSERT OR REPLACE INTO logs (event_id,date,text,source) VALUES (?,?,?,'template')",
                        params![event.id.to_string(), date.to_string(), template_narrative],
                    )?;
                }
                EventKind::RestDayObserved {
                    date,
                    animation,
                    template_narrative,
                } => {
                    tx.execute(
                        "UPDATE app_state SET animation=?,last_action_date=?,last_action_kind='rest' WHERE id=1",
                        params![animation_name(animation), date.to_string()],
                    )?;
                    tx.execute(
                        "INSERT OR REPLACE INTO logs (event_id,date,text,source) VALUES (?,?,?,'template')",
                        params![event.id.to_string(), date.to_string(), template_narrative],
                    )?;
                }
                EventKind::VesselChanged { vessel_id } => {
                    tx.execute(
                        "UPDATE app_state SET current_vessel=?,animation='happy' WHERE id=1",
                        params![vessel_id],
                    )?;
                }
                EventKind::VesselEquipped { vessel_id } => {
                    tx.execute(
                        "UPDATE app_state SET current_vessel=?,animation='happy' WHERE id=1",
                        params![vessel_id],
                    )?;
                }
                EventKind::ShopItemPurchased {
                    item_id,
                    kind,
                    cost,
                } => {
                    tx.execute(
                        "UPDATE app_state SET coins=coins-? WHERE id=1",
                        params![cost],
                    )?;
                    tx.execute(
                        "INSERT OR REPLACE INTO purchases (item_id) VALUES (?)",
                        params![item_id],
                    )?;
                    tx.execute(
                        "INSERT OR REPLACE INTO owned_items (item_id,kind) VALUES (?,?)",
                        params![item_id, shop_item_kind_name(kind)],
                    )?;
                }
                EventKind::NarrativeGenerated {
                    target_event_id,
                    text,
                    ..
                } => {
                    tx.execute(
                        "UPDATE logs SET text=?, source='llm' WHERE event_id=?",
                        params![text, target_event_id.to_string()],
                    )?;
                }
            }
        }
        tx.commit()?;
        Ok(())
    }

    pub fn dashboard(&self) -> Result<Dashboard> {
        let mut stmt = self.conn.prepare(
            "SELECT initialized,total_days,daily_task,position,completed_days,coins,trust,mood,streak,current_vessel,animation,last_action_date,last_action_kind FROM app_state WHERE id=1",
        )?;
        let row = stmt.query_row([], |row| {
            let last_action_date = row
                .get::<_, Option<String>>(11)?
                .and_then(|date| NaiveDate::parse_from_str(&date, "%Y-%m-%d").ok());
            Ok(Dashboard {
                initialized: row.get::<_, i32>(0)? == 1,
                total_days: row.get::<_, u32>(1)?,
                daily_task: row.get(2)?,
                position: row.get::<_, u32>(3)?,
                completed_days: row.get::<_, u32>(4)?,
                coins: row.get(5)?,
                trust: row.get(6)?,
                mood: row.get(7)?,
                streak: row.get::<_, u32>(8)?,
                current_vessel: row.get(9)?,
                animation: animation_from_name(row.get::<_, String>(10)?.as_str())
                    .unwrap_or(VesselAnimation::Idle),
                owned_items: Vec::new(),
                owned_vessels: Vec::new(),
                last_action_date,
                last_action_kind: row.get(12)?,
                latest_log: None,
            })
        })?;

        let latest_log = self
            .conn
            .query_row(
                "SELECT text FROM logs ORDER BY date DESC, event_id DESC LIMIT 1",
                [],
                |row| row.get::<_, String>(0),
            )
            .ok();
        let owned_items = self.query_owned_items(None)?;
        let owned_vessels = self.query_owned_items(Some("vessel"))?;
        Ok(Dashboard {
            latest_log,
            owned_items,
            owned_vessels,
            ..row
        })
    }

    fn query_owned_items(&self, kind: Option<&str>) -> Result<Vec<String>> {
        let sql = if kind.is_some() {
            "SELECT item_id FROM owned_items WHERE kind=? ORDER BY item_id"
        } else {
            "SELECT item_id FROM owned_items ORDER BY item_id"
        };
        let mut stmt = self.conn.prepare(sql)?;
        let mut out = Vec::new();
        if let Some(kind) = kind {
            let rows = stmt.query_map(params![kind], |row| row.get::<_, String>(0))?;
            for row in rows {
                out.push(row?);
            }
        } else {
            let rows = stmt.query_map([], |row| row.get::<_, String>(0))?;
            for row in rows {
                out.push(row?);
            }
        }
        Ok(out)
    }
}

pub fn animation_name(animation: VesselAnimation) -> &'static str {
    match animation {
        VesselAnimation::Idle => "idle",
        VesselAnimation::Waiting => "waiting",
        VesselAnimation::Sailing => "sailing",
        VesselAnimation::Happy => "happy",
        VesselAnimation::Resting => "resting",
        VesselAnimation::Celebrating => "celebrating",
        VesselAnimation::Treasure => "treasure",
        VesselAnimation::LowEnergy => "low_energy",
    }
}

fn shop_item_kind_name(kind: crate::events::ShopItemKind) -> &'static str {
    match kind {
        crate::events::ShopItemKind::Vessel => "vessel",
        crate::events::ShopItemKind::Skin => "skin",
        crate::events::ShopItemKind::Decoration => "decoration",
        crate::events::ShopItemKind::Animation => "animation",
    }
}

pub fn animation_from_name(name: &str) -> Result<VesselAnimation> {
    Ok(match name {
        "idle" => VesselAnimation::Idle,
        "waiting" => VesselAnimation::Waiting,
        "sailing" => VesselAnimation::Sailing,
        "happy" => VesselAnimation::Happy,
        "resting" => VesselAnimation::Resting,
        "celebrating" => VesselAnimation::Celebrating,
        "treasure" => VesselAnimation::Treasure,
        "low_energy" => VesselAnimation::LowEnergy,
        other => bail!("unknown animation {other}"),
    })
}

fn add_column_if_missing(
    conn: &Connection,
    table: &str,
    column: &str,
    definition: &str,
) -> Result<()> {
    let exists: i64 = conn.query_row(
        "SELECT COUNT(*) FROM pragma_table_info(?) WHERE name = ?",
        params![table, column],
        |row| row.get(0),
    )?;
    if exists == 0 {
        conn.execute(
            &format!("ALTER TABLE {table} ADD COLUMN {column} {definition}"),
            [],
        )?;
    }
    Ok(())
}
