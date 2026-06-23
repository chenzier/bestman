use anyhow::{Context, Result, bail};
use serde_json::Value;

use crate::config::LlmConfig;

pub fn mock_narrative(prompt: &str) -> Result<String> {
    Ok(format!("LLM航海日志：{prompt} 风很轻，船灯亮着。"))
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct GeneratedNarrative {
    pub text: String,
    pub model: String,
    pub prompt_version: String,
}

pub fn generate_narrative(config: &LlmConfig, prompt: &str) -> Result<GeneratedNarrative> {
    if !config.enabled {
        bail!("llm is disabled");
    }
    let api_key = std::env::var(&config.api_key_env)
        .with_context(|| format!("missing API key env {}", config.api_key_env))?;
    let url = format!("{}/chat/completions", config.base_url.trim_end_matches('/'));
    let request = build_openai_chat_request(&config.model, prompt, &config.prompt_version);
    let response: Value = ureq::post(&url)
        .set("Authorization", &format!("Bearer {api_key}"))
        .set("Content-Type", "application/json")
        .send_json(request)?
        .into_json()?;
    let text = parse_openai_chat_response(&response)?;
    Ok(GeneratedNarrative {
        text,
        model: config.model.clone(),
        prompt_version: config.prompt_version.clone(),
    })
}

pub fn build_openai_chat_request(model: &str, prompt: &str, prompt_version: &str) -> Value {
    serde_json::json!({
        "model": model,
        "metadata": {
            "prompt_version": prompt_version
        },
        "messages": [
            {
                "role": "system",
                "content": "You write short, warm bestman pet-vessel fitness voyage logs. Do not change coins, position, mood, trust, rewards, or rules."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.7
    })
}

pub fn parse_openai_chat_response(value: &Value) -> Result<String> {
    let text = value
        .get("choices")
        .and_then(|choices| choices.as_array())
        .and_then(|choices| choices.first())
        .and_then(|choice| choice.get("message"))
        .and_then(|message| message.get("content"))
        .and_then(|content| content.as_str())
        .map(str::trim)
        .filter(|text| !text.is_empty())
        .ok_or_else(|| anyhow::anyhow!("llm response did not contain message content"))?;
    Ok(text.to_string())
}
