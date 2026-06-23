use std::path::Path;

use anyhow::Result;
use base64::Engine;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ImageProtocol {
    Kitty,
    Sixel,
    None,
}

pub fn detect_from_env(term: Option<&str>, term_program: Option<&str>) -> ImageProtocol {
    let term = term.unwrap_or("").to_lowercase();
    let term_program = term_program.unwrap_or("").to_lowercase();
    if term.contains("kitty")
        || term_program.contains("ghostty")
        || term_program.contains("wezterm")
        || term_program.contains("kitty")
    {
        ImageProtocol::Kitty
    } else if term.contains("sixel") || term_program.contains("foot") {
        ImageProtocol::Sixel
    } else {
        ImageProtocol::None
    }
}

pub fn detect_current() -> ImageProtocol {
    detect_from_env(
        std::env::var("TERM").ok().as_deref(),
        std::env::var("TERM_PROGRAM").ok().as_deref(),
    )
}

pub fn kitty_inline_png(path: &Path, image_id: u32) -> Result<String> {
    let bytes = std::fs::read(path)?;
    let encoded = base64::engine::general_purpose::STANDARD.encode(bytes);
    Ok(format!("\x1b_Ga=T,f=100,i={image_id},m=0;{encoded}\x1b\\"))
}

pub fn kitty_delete(image_id: u32) -> String {
    format!("\x1b_Ga=d,d=i,i={image_id}\x1b\\")
}
