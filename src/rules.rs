use anyhow::{Result, bail};
use chrono::{Datelike, NaiveDate};
use rand::Rng;

use crate::config::BestmanConfig;
use crate::events::{CoinAward, CompletionLevel, EventKind, StoredEvent, VesselAnimation};
use crate::map::milestone_names;
use crate::projection::Dashboard;

pub fn init_event(config: &BestmanConfig, start_date: NaiveDate) -> StoredEvent {
    StoredEvent::new(EventKind::VoyageInitialized {
        start_date,
        total_days: config.voyage.total_days,
        daily_task: config.voyage.daily_task.clone(),
        rest_days: config.voyage.rest_days.clone(),
        vessel_id: config.companion.current_vessel.clone(),
    })
}

pub fn check_in_event(
    config: &BestmanConfig,
    dashboard: &Dashboard,
    date: NaiveDate,
    level: CompletionLevel,
    task_note: String,
    forced_dice: Option<u32>,
) -> Result<StoredEvent> {
    if !dashboard.initialized {
        bail!("voyage is not initialized");
    }
    if dashboard.last_action_date == Some(date) {
        bail!("today is already recorded; use tomorrow's check-in to continue");
    }
    let dice_distance = match forced_dice {
        Some(n @ 1..=3) => n,
        Some(other) => bail!("dice must be 1..=3, got {other}"),
        None => rand::rng().random_range(1..=3),
    };
    let old_position = dashboard.position;
    let new_position = (old_position + dice_distance).min(config.voyage.total_days);
    let milestones = milestone_names(old_position, new_position, config.voyage.total_days);
    let treasures = treasure_hits(old_position, new_position);

    let mut coins_breakdown = vec![CoinAward {
        reason: "daily_check_in".to_string(),
        amount: match level {
            CompletionLevel::Light => 7,
            CompletionLevel::Normal => 10,
            CompletionLevel::Full => 12,
        },
    }];
    if !milestones.is_empty() {
        coins_breakdown.push(CoinAward {
            reason: "milestone".to_string(),
            amount: 50 * milestones.len() as i32,
        });
    }
    if !treasures.is_empty() {
        coins_breakdown.push(CoinAward {
            reason: "treasure".to_string(),
            amount: 30 * treasures.len() as i32,
        });
    }

    let next_streak = dashboard.streak.saturating_add(1);
    let animation = if !milestones.is_empty() {
        VesselAnimation::Celebrating
    } else if !treasures.is_empty() {
        VesselAnimation::Treasure
    } else if next_streak >= 7 && next_streak % 7 == 0 {
        VesselAnimation::Happy
    } else {
        VesselAnimation::Sailing
    };
    let (trust_delta, mood_delta) = match level {
        CompletionLevel::Light => (1, 2),
        CompletionLevel::Normal => (2, 4),
        CompletionLevel::Full => (3, 7),
    };

    let template_narrative = if matches!(animation, VesselAnimation::Happy) {
        format!(
            "第 {} 天，{}完成。连续 {} 天的节奏被稳稳接住，小帆船把灯调亮了一些。",
            new_position,
            level_name(level),
            next_streak
        )
    } else {
        format!(
            "第 {} 天，{}完成。小帆船升起灯，向前航行 {} 格。",
            new_position,
            level_name(level),
            dice_distance
        )
    };

    Ok(StoredEvent::new(EventKind::DailyCheckInCompleted {
        date,
        level,
        task_note,
        dice_distance,
        old_position,
        new_position,
        coins_breakdown,
        treasures,
        milestones,
        trust_delta,
        mood_delta,
        animation,
        template_narrative,
    }))
}

pub fn skip_or_rest_event(
    config: &BestmanConfig,
    dashboard: &Dashboard,
    date: NaiveDate,
    reason: String,
) -> Result<StoredEvent> {
    if !dashboard.initialized {
        bail!("voyage is not initialized");
    }
    if dashboard.last_action_date == Some(date) {
        bail!("today is already recorded; no second rest/skip is needed");
    }
    if is_rest_day(config, date) {
        Ok(StoredEvent::new(EventKind::RestDayObserved {
            date,
            animation: VesselAnimation::Resting,
            template_narrative: "今天是计划休息日，小帆船停在安静港湾里补给。".to_string(),
        }))
    } else {
        let mood_after = dashboard.mood + -2;
        let low_energy = dashboard.last_action_kind.as_deref() == Some("skip") || mood_after <= 45;
        Ok(StoredEvent::new(EventKind::DaySkipped {
            date,
            reason,
            mood_delta: -2,
            animation: if low_energy {
                VesselAnimation::LowEnergy
            } else {
                VesselAnimation::Resting
            },
            template_narrative: if low_energy {
                "今天继续放慢节奏，小帆船把灯压低，没有催促，只提醒你明天可以从轻量开始。"
                    .to_string()
            } else {
                "今天使用一次休整，小帆船收起帆，没有责备，只是在港口等你。".to_string()
            },
        }))
    }
}

pub fn purchase_event(dashboard: &Dashboard, item_id: String, cost: i32) -> Result<StoredEvent> {
    if dashboard.coins < cost {
        bail!("not enough coins");
    }
    Ok(StoredEvent::new(EventKind::ShopItemPurchased {
        item_id,
        cost,
    }))
}

pub fn change_vessel_event(vessel_id: String) -> StoredEvent {
    StoredEvent::new(EventKind::VesselChanged { vessel_id })
}

pub fn narrative_generated_event(
    target_event_id: uuid::Uuid,
    text: String,
    model: String,
) -> StoredEvent {
    StoredEvent::new(EventKind::NarrativeGenerated {
        target_event_id,
        text,
        model,
        prompt_version: "v1".to_string(),
    })
}

fn is_rest_day(config: &BestmanConfig, date: NaiveDate) -> bool {
    let weekday = date.weekday().to_string().to_lowercase();
    let short = &weekday[..3];
    config
        .voyage
        .rest_days
        .iter()
        .any(|d| d.to_lowercase() == short)
}

fn treasure_hits(old_position: u32, new_position: u32) -> Vec<String> {
    [18, 42, 75, 110]
        .into_iter()
        .filter(|pos| old_position < *pos && new_position >= *pos)
        .map(|pos| format!("漂流宝箱 {pos}"))
        .collect()
}

fn level_name(level: CompletionLevel) -> &'static str {
    match level {
        CompletionLevel::Light => "轻量",
        CompletionLevel::Normal => "标准",
        CompletionLevel::Full => "完整",
    }
}
