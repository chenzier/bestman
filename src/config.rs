use std::path::Path;

use anyhow::Result;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct BestmanConfig {
    #[serde(default)]
    pub voyage: VoyageConfig,
    #[serde(default)]
    pub companion: CompanionConfig,
    #[serde(default)]
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
    #[serde(default)]
    pub enabled: bool,
    #[serde(default = "default_llm_provider")]
    pub provider: String,
    #[serde(default = "default_llm_base_url")]
    pub base_url: String,
    #[serde(default = "default_llm_api_key_env")]
    pub api_key_env: String,
    #[serde(default = "default_llm_model")]
    pub model: String,
    #[serde(default = "default_prompt_version")]
    pub prompt_version: String,
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
                provider: default_llm_provider(),
                base_url: default_llm_base_url(),
                api_key_env: default_llm_api_key_env(),
                model: default_llm_model(),
                prompt_version: default_prompt_version(),
            },
        }
    }
}

impl Default for VoyageConfig {
    fn default() -> Self {
        Self {
            total_days: 120,
            daily_task: "未设置 - 运行 init 设置每日任务".to_string(),
            rest_days: vec!["sun".to_string()],
        }
    }
}

impl Default for CompanionConfig {
    fn default() -> Self {
        Self {
            current_vessel: "starter_sloop".to_string(),
        }
    }
}

impl Default for LlmConfig {
    fn default() -> Self {
        Self {
            enabled: false,
            provider: default_llm_provider(),
            base_url: default_llm_base_url(),
            api_key_env: default_llm_api_key_env(),
            model: default_llm_model(),
            prompt_version: default_prompt_version(),
        }
    }
}

fn default_llm_provider() -> String {
    "openai_compatible".to_string()
}

fn default_llm_base_url() -> String {
    "https://api.openai.com/v1".to_string()
}

fn default_llm_api_key_env() -> String {
    "OPENAI_API_KEY".to_string()
}

fn default_llm_model() -> String {
    "gpt-4o-mini".to_string()
}

fn default_prompt_version() -> String {
    "bestman-v2-narrative".to_string()
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
