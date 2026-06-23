use anyhow::Result;

pub fn mock_narrative(prompt: &str) -> Result<String> {
    Ok(format!("LLM航海日志：{prompt} 风很轻，船灯亮着。"))
}
