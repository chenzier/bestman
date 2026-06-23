use std::collections::hash_map::DefaultHasher;
use std::hash::{Hash, Hasher};
use std::path::{Path, PathBuf};

use anyhow::{Result, bail};
use image::{GenericImageView, Rgba, RgbaImage};

use crate::vessels::manifest::VesselManifest;

pub fn render_preview(manifest: &VesselManifest, animation: &str, output: &Path) -> Result<()> {
    ensure_placeholder_sheet(manifest)?;
    let anim = manifest
        .animations
        .get(animation)
        .or_else(|| manifest.animations.get("idle"))
        .ok_or_else(|| anyhow::anyhow!("missing animation {animation}"))?;
    let frame_idx = *anim
        .frames
        .first()
        .ok_or_else(|| anyhow::anyhow!("animation has no frames"))?;
    let frame = extract_frame(manifest, frame_idx)?;
    if let Some(parent) = output.parent() {
        std::fs::create_dir_all(parent)?;
    }
    frame.save(output)?;
    Ok(())
}

pub fn export_animation_frames(
    manifest: &VesselManifest,
    animation: &str,
    output_dir: &Path,
) -> Result<Vec<PathBuf>> {
    ensure_placeholder_sheet(manifest)?;
    let anim = manifest
        .animations
        .get(animation)
        .or_else(|| manifest.animations.get("idle"))
        .ok_or_else(|| anyhow::anyhow!("missing animation {animation}"))?;
    std::fs::create_dir_all(output_dir)?;
    let mut paths = Vec::new();
    for (idx, frame_idx) in anim.frames.iter().enumerate() {
        let frame = extract_frame(manifest, *frame_idx)?;
        let path = output_dir.join(format!("{animation}-{idx:03}.png"));
        frame.save(&path)?;
        paths.push(path);
    }
    Ok(paths)
}

pub struct FrameCache {
    root: PathBuf,
}

impl FrameCache {
    pub fn new(root: PathBuf) -> Self {
        Self { root }
    }

    pub fn frame_path(&self, manifest: &VesselManifest, frame_idx: u32) -> Result<PathBuf> {
        ensure_placeholder_sheet(manifest)?;
        let key = cache_key(manifest)?;
        let dir = self.root.join(key);
        std::fs::create_dir_all(&dir)?;
        let path = dir.join(format!("frame-{frame_idx:03}.png"));
        if !path.exists() {
            let frame = extract_frame(manifest, frame_idx)?;
            frame.save(&path)?;
        }
        Ok(path)
    }

    pub fn first_animation_frame(
        &self,
        manifest: &VesselManifest,
        animation: &str,
    ) -> Result<PathBuf> {
        let anim = manifest
            .animations
            .get(animation)
            .or_else(|| manifest.animations.get("idle"))
            .ok_or_else(|| anyhow::anyhow!("missing animation {animation}"))?;
        let frame_idx = *anim
            .frames
            .first()
            .ok_or_else(|| anyhow::anyhow!("animation has no frames"))?;
        self.frame_path(manifest, frame_idx)
    }

    pub fn animation_frames(
        &self,
        manifest: &VesselManifest,
        animation: &str,
    ) -> Result<Vec<PathBuf>> {
        let anim = manifest
            .animations
            .get(animation)
            .or_else(|| manifest.animations.get("idle"))
            .ok_or_else(|| anyhow::anyhow!("missing animation {animation}"))?;
        anim.frames
            .iter()
            .map(|frame_idx| self.frame_path(manifest, *frame_idx))
            .collect()
    }
}

pub fn ensure_placeholder_sheet(manifest: &VesselManifest) -> Result<()> {
    let path = manifest.spritesheet_abs_path();
    if path.exists() {
        return Ok(());
    }
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    let w = manifest.frame.width * manifest.frame.columns;
    let h = manifest.frame.height * manifest.frame.rows;
    let mut img = RgbaImage::new(w, h);
    for idx in 0..manifest.frame.columns * manifest.frame.rows {
        let col = idx % manifest.frame.columns;
        let row = idx / manifest.frame.columns;
        draw_placeholder_ship(
            &mut img,
            col * manifest.frame.width,
            row * manifest.frame.height,
            manifest.frame.width,
            manifest.frame.height,
            idx,
        );
    }
    img.save(path)?;
    Ok(())
}

fn cache_key(manifest: &VesselManifest) -> Result<String> {
    let sheet = manifest.spritesheet_abs_path();
    let metadata = std::fs::metadata(&sheet)?;
    let mut hasher = DefaultHasher::new();
    manifest.id.hash(&mut hasher);
    sheet.hash(&mut hasher);
    metadata.len().hash(&mut hasher);
    manifest.frame.width.hash(&mut hasher);
    manifest.frame.height.hash(&mut hasher);
    manifest.frame.columns.hash(&mut hasher);
    manifest.frame.rows.hash(&mut hasher);
    Ok(format!("{:016x}", hasher.finish()))
}

fn extract_frame(manifest: &VesselManifest, frame_idx: u32) -> Result<RgbaImage> {
    let sheet_path = manifest.spritesheet_abs_path();
    let sheet = image::open(&sheet_path)?;
    let expected_w = manifest.frame.width * manifest.frame.columns;
    let expected_h = manifest.frame.height * manifest.frame.rows;
    if sheet.dimensions() != (expected_w, expected_h) {
        bail!(
            "spritesheet dimensions mismatch: got {:?}, expected {:?}",
            sheet.dimensions(),
            (expected_w, expected_h)
        );
    }
    let col = frame_idx % manifest.frame.columns;
    let row = frame_idx / manifest.frame.columns;
    Ok(sheet
        .crop_imm(
            col * manifest.frame.width,
            row * manifest.frame.height,
            manifest.frame.width,
            manifest.frame.height,
        )
        .to_rgba8())
}

fn draw_placeholder_ship(img: &mut RgbaImage, ox: u32, oy: u32, w: u32, h: u32, idx: u32) {
    let bg = Rgba([18, 72, 92, 255]);
    let water = Rgba([32, 132, 150, 255]);
    let hull = Rgba([112, 60, 32, 255]);
    let hull_dark = Rgba([70, 36, 22, 255]);
    let sail = Rgba([250, 242, 210, 255]);
    let sail_shadow = Rgba([220, 210, 180, 255]);
    let lantern = Rgba([255, 210, 88, 255]);
    for y in 0..h {
        for x in 0..w {
            img.put_pixel(ox + x, oy + y, bg);
        }
    }
    let bob = ((idx % 4) as i32 - 1).abs() as u32;
    for y in (h * 3 / 4)..(h * 3 / 4 + 4) {
        for x in (w / 5)..(w * 4 / 5) {
            if (x + idx) % 9 < 5 {
                img.put_pixel(ox + x, oy + y, water);
            }
        }
    }
    let mast_x = w / 2;
    for y in h / 5..h * 3 / 4 {
        for dx in 0..3 {
            img.put_pixel(ox + mast_x + dx, oy + y + bob, hull_dark);
        }
    }
    for y in h / 5..h / 2 {
        let span = (y - h / 5) * 2;
        for x in mast_x.saturating_sub(span)..mast_x {
            img.put_pixel(ox + x, oy + y + bob, sail);
        }
        for x in mast_x..(mast_x + span / 2).min(w - 1) {
            img.put_pixel(ox + x, oy + y + bob, sail_shadow);
        }
    }
    for y in h * 2 / 3..h * 4 / 5 {
        let inset = (y - h * 2 / 3) * 2;
        for x in (w / 5 + inset)..(w * 4 / 5).saturating_sub(inset) {
            img.put_pixel(ox + x, oy + y + bob, hull);
        }
    }
    for y in h * 4 / 5..h * 4 / 5 + 4 {
        for x in w / 4..w * 3 / 4 {
            img.put_pixel(ox + x, oy + y + bob, hull_dark);
        }
    }
    for dy in 0..6 {
        for dx in 0..6 {
            if dx * dx + dy * dy < 25 {
                img.put_pixel(ox + w * 3 / 5 + dx, oy + h * 3 / 5 + dy + bob, lantern);
            }
        }
    }
}
