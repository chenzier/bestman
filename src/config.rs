use std::path::Path;

use anyhow::Result;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct BestmanConfig {
    pub voyage: VoyageConfig,
    pub companion: CompanionConfig,
    pub llm: LlmConfig,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct VoyageConfig {
    pub total_days: u32,
    pub daily_task: String,
    pub rest_days: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct CompanionConfig {
    pub current_vessel: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct LlmConfig {
    pub enabled: bool,
    pub model: String,
}

impl Default for BestmanConfig {
    fn default() -> Self {
        Self {
            voyage: VoyageConfig {
                total_days: 120,
                daily_task: "未设置 - 运行 init 设置每日任务".to_string(),
                rest_days: vec!["sun".to_string()],
            },
            companion: CompanionConfig {
                current_vessel: "starter_sloop".to_string(),
            },
            llm: LlmConfig {
                enabled: false,
                model: "gpt-4o-mini".to_string(),
            },
        }
    }
}

impl BestmanConfig {
    pub fn load_or_default(path: &Path) -> Result<Self> {
        if path.exists() {
            let text = std::fs::read_to_string(path)?;
            Ok(toml::from_str(&text)?)
        } else {
            Ok(Self::default())
        }
    }

    pub fn save(&self, path: &Path) -> Result<()> {
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent)?;
        }
        std::fs::write(path, toml::to_string_pretty(self)?)?;
        Ok(())
    }
}
