use std::fs::{File, OpenOptions};
use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;

use anyhow::{Context, Result};
use chrono::{DateTime, NaiveDate, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct StoredEvent {
    pub id: Uuid,
    pub created_at: DateTime<Utc>,
    pub kind: EventKind,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum EventKind {
    VoyageInitialized {
        start_date: NaiveDate,
        total_days: u32,
        daily_task: String,
        rest_days: Vec<String>,
        vessel_id: String,
    },
    DailyCheckInCompleted {
        date: NaiveDate,
        level: CompletionLevel,
        task_note: String,
        dice_distance: u32,
        old_position: u32,
        new_position: u32,
        coins_breakdown: Vec<CoinAward>,
        treasures: Vec<String>,
        milestones: Vec<String>,
        trust_delta: i32,
        mood_delta: i32,
        animation: VesselAnimation,
        template_narrative: String,
    },
    DaySkipped {
        date: NaiveDate,
        reason: String,
        mood_delta: i32,
        animation: VesselAnimation,
        template_narrative: String,
    },
    RestDayObserved {
        date: NaiveDate,
        animation: VesselAnimation,
        template_narrative: String,
    },
    PlanCreated {
        date: NaiveDate,
        goal: String,
        tasks: Vec<String>,
    },
    PlanAdjusted {
        date: NaiveDate,
        daily_task: String,
        reason: String,
    },
    CoinsGranted {
        date: NaiveDate,
        amount: i32,
        reason: String,
    },
    VesselChanged {
        vessel_id: String,
    },
    VesselEquipped {
        vessel_id: String,
    },
    ShopItemPurchased {
        item_id: String,
        kind: ShopItemKind,
        cost: i32,
    },
    NarrativeGenerated {
        target_event_id: Uuid,
        text: String,
        model: String,
        prompt_version: String,
    },
    RecapGenerated {
        date: NaiveDate,
        #[serde(default = "default_recap_period")]
        period: RecapPeriod,
        text: String,
        model: String,
        prompt_version: String,
    },
    MilestoneEpicGenerated {
        date: NaiveDate,
        milestone: String,
        text: String,
        model: String,
        prompt_version: String,
    },
    CaptainChatGenerated {
        date: NaiveDate,
        user_message: String,
        text: String,
        model: String,
        prompt_version: String,
    },
    WeightRecorded {
        date: NaiveDate,
        weight_kg: f64,
        note: Option<String>,
    },
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum CompletionLevel {
    Light,
    Normal,
    Full,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum VesselAnimation {
    Idle,
    Waiting,
    Sailing,
    Happy,
    Resting,
    Celebrating,
    Treasure,
    LowEnergy,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ShopItemKind {
    Vessel,
    Skin,
    Decoration,
    Animation,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum RecapPeriod {
    Week,
    Month,
    All,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct CoinAward {
    pub reason: String,
    pub amount: i32,
}

fn default_recap_period() -> RecapPeriod {
    RecapPeriod::All
}

impl StoredEvent {
    pub fn new(kind: EventKind) -> Self {
        Self {
            id: Uuid::now_v7(),
            created_at: Utc::now(),
            kind,
        }
    }
}

pub struct EventStore {
    path: PathBuf,
}

impl EventStore {
    pub fn open(path: PathBuf) -> Result<Self> {
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent)?;
        }
        if !path.exists() {
            File::create(&path)?;
        }
        Ok(Self { path })
    }

    pub fn append(&self, event: StoredEvent) -> Result<StoredEvent> {
        let mut file = OpenOptions::new()
            .append(true)
            .create(true)
            .open(&self.path)?;
        let line = serde_json::to_string(&event)?;
        writeln!(file, "{line}")?;
        Ok(event)
    }

    pub fn read_all(&self) -> Result<Vec<StoredEvent>> {
        let file = File::open(&self.path)?;
        let reader = BufReader::new(file);
        let mut events = Vec::new();
        for (idx, line) in reader.lines().enumerate() {
            let line = line?;
            if line.trim().is_empty() {
                continue;
            }
            let event: StoredEvent = serde_json::from_str(&line)
                .with_context(|| format!("invalid event json at line {}", idx + 1))?;
            events.push(event);
        }
        Ok(events)
    }
}
