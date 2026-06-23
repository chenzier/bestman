use std::collections::{HashMap, HashSet};
use std::path::{Path, PathBuf};

use anyhow::{Result, bail};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct VesselManifest {
    pub id: String,
    pub display_name: String,
    pub description: String,
    pub spritesheet_path: PathBuf,
    pub frame: FrameSpec,
    pub animations: HashMap<String, AnimationSpec>,
    #[serde(skip)]
    pub base_dir: PathBuf,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct FrameSpec {
    pub width: u32,
    pub height: u32,
    pub columns: u32,
    pub rows: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct AnimationSpec {
    pub frames: Vec<u32>,
    pub fps: f32,
    pub looped: bool,
    pub fallback: String,
}

impl VesselManifest {
    pub fn load(path: &Path) -> Result<Self> {
        let text = std::fs::read_to_string(path)?;
        let mut manifest: VesselManifest = serde_json::from_str(&text)?;
        manifest.base_dir = path
            .parent()
            .ok_or_else(|| anyhow::anyhow!("manifest has no parent"))?
            .to_path_buf();
        manifest.validate()?;
        Ok(manifest)
    }

    pub fn spritesheet_abs_path(&self) -> PathBuf {
        self.base_dir.join(&self.spritesheet_path)
    }

    pub fn validate(&self) -> Result<()> {
        if self.id.trim().is_empty() {
            bail!("vessel id cannot be empty");
        }
        if self.spritesheet_path.is_absolute()
            || self
                .spritesheet_path
                .components()
                .any(|c| matches!(c, std::path::Component::ParentDir))
        {
            bail!("spritesheetPath must stay inside vessel directory");
        }
        if self.frame.width == 0
            || self.frame.height == 0
            || self.frame.columns == 0
            || self.frame.rows == 0
        {
            bail!("frame geometry must be non-zero");
        }
        if self.frame.width > 512 || self.frame.height > 512 {
            bail!("frame too large");
        }
        let frame_count = self.frame.columns * self.frame.rows;
        let required: HashSet<&str> = ["idle", "sailing", "resting", "celebrating"]
            .into_iter()
            .collect();
        for name in required {
            if !self.animations.contains_key(name) {
                bail!("missing required animation {name}");
            }
        }
        for (name, anim) in &self.animations {
            if anim.frames.is_empty() {
                bail!("animation {name} has no frames");
            }
            if !(anim.fps.is_finite() && anim.fps > 0.0 && anim.fps <= 30.0) {
                bail!("animation {name} has invalid fps");
            }
            if !self.animations.contains_key(&anim.fallback) {
                bail!("animation {name} fallback missing");
            }
            if anim.frames.iter().any(|idx| *idx >= frame_count) {
                bail!("animation {name} references out-of-range frame");
            }
        }
        Ok(())
    }
}
