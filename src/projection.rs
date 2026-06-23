use std::path::Path;

use anyhow::{Result, bail};
use rusqlite::{Connection, params};

use crate::events::{EventKind, StoredEvent, VesselAnimation};

#[derive(Debug, Clone, PartialEq)]
pub struct Dashboard {
    pub initialized: bool,
    pub total_days: u32,
    pub position: u32,
    pub completed_days: u32,
    pub coins: i32,
    pub trust: i32,
    pub mood: i32,
    pub streak: u32,
    pub current_vessel: String,
    pub animation: VesselAnimation,
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
                position INTEGER NOT NULL DEFAULT 0,
                completed_days INTEGER NOT NULL DEFAULT 0,
                coins INTEGER NOT NULL DEFAULT 0,
                trust INTEGER NOT NULL DEFAULT 20,
                mood INTEGER NOT NULL DEFAULT 60,
                streak INTEGER NOT NULL DEFAULT 0,
                current_vessel TEXT NOT NULL DEFAULT 'starter_sloop',
                animation TEXT NOT NULL DEFAULT 'idle'
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
            INSERT OR IGNORE INTO app_state (id) VALUES (1);
            "#,
        )?;
        Ok(())
    }

    pub fn rebuild(&mut self, events: Vec<StoredEvent>) -> Result<()> {
        let tx = self.conn.transaction()?;
        tx.execute("DELETE FROM logs", [])?;
        tx.execute("DELETE FROM purchases", [])?;
        tx.execute(
            "UPDATE app_state SET initialized=0,total_days=120,position=0,completed_days=0,coins=0,trust=20,mood=60,streak=0,current_vessel='starter_sloop',animation='idle' WHERE id=1",
            [],
        )?;

        for event in events {
            match event.kind {
                EventKind::VoyageInitialized {
                    total_days,
                    vessel_id,
                    ..
                } => {
                    tx.execute(
                        "UPDATE app_state SET initialized=1,total_days=?,current_vessel=?,animation='waiting' WHERE id=1",
                        params![total_days, vessel_id],
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
                        "UPDATE app_state SET position=?,completed_days=completed_days+1,coins=coins+?,trust=MIN(100,MAX(0,trust+?)),mood=MIN(100,MAX(0,mood+?)),streak=streak+1,animation=? WHERE id=1",
                        params![new_position, coins, trust_delta, mood_delta, animation_name(animation)],
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
                        "UPDATE app_state SET mood=MIN(100,MAX(0,mood+?)),streak=streak+1,animation=? WHERE id=1",
                        params![mood_delta, animation_name(animation)],
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
                        "UPDATE app_state SET animation=? WHERE id=1",
                        params![animation_name(animation)],
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
                EventKind::ShopItemPurchased { item_id, cost } => {
                    tx.execute(
                        "UPDATE app_state SET coins=coins-? WHERE id=1",
                        params![cost],
                    )?;
                    tx.execute(
                        "INSERT OR REPLACE INTO purchases (item_id) VALUES (?)",
                        params![item_id],
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
            "SELECT initialized,total_days,position,completed_days,coins,trust,mood,streak,current_vessel,animation FROM app_state WHERE id=1",
        )?;
        let row = stmt.query_row([], |row| {
            Ok(Dashboard {
                initialized: row.get::<_, i32>(0)? == 1,
                total_days: row.get::<_, u32>(1)?,
                position: row.get::<_, u32>(2)?,
                completed_days: row.get::<_, u32>(3)?,
                coins: row.get(4)?,
                trust: row.get(5)?,
                mood: row.get(6)?,
                streak: row.get::<_, u32>(7)?,
                current_vessel: row.get(8)?,
                animation: animation_from_name(row.get::<_, String>(9)?.as_str())
                    .unwrap_or(VesselAnimation::Idle),
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
        Ok(Dashboard { latest_log, ..row })
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
