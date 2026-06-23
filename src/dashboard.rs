use std::path::{Path, PathBuf};

use anyhow::Result;
use image::{Rgba, RgbaImage};
use ratatui::Terminal;
use ratatui::backend::TestBackend;
use ratatui::layout::{Constraint, Direction, Layout};
use ratatui::style::{Color, Modifier, Style};
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, Borders, Paragraph};

use crate::app::BestmanApp;
use crate::map::Route;
use crate::projection::{Dashboard, animation_name};
use crate::terminal_image;
use crate::vessels::catalog::VesselCatalog;
use crate::vessels::render::FrameCache;

pub struct DashboardRender {
    pub text: String,
    pub companion_frame: PathBuf,
}

pub fn build_dashboard_render(app: &BestmanApp) -> Result<DashboardRender> {
    let dash = app.projection.dashboard()?;
    let companion_frame = companion_frame_path(app, &dash)?;
    let text = render_snapshot(&dash, &companion_frame, 88, 32)?;
    Ok(DashboardRender {
        text,
        companion_frame,
    })
}

pub fn render_snapshot(
    dash: &Dashboard,
    companion_frame: &Path,
    width: u16,
    height: u16,
) -> Result<String> {
    let backend = TestBackend::new(width, height);
    let mut terminal = Terminal::new(backend)?;
    terminal.draw(|frame| {
        let root = Layout::default()
            .direction(Direction::Vertical)
            .constraints([
                Constraint::Length(9),
                Constraint::Length(16),
                Constraint::Min(5),
            ])
            .split(frame.area());
        let top = Layout::default()
            .direction(Direction::Horizontal)
            .constraints([Constraint::Length(42), Constraint::Min(20)])
            .split(root[0]);

        let companion = Paragraph::new(vec![
            Line::from(vec![
                Span::styled("vessel ", Style::default().fg(Color::DarkGray)),
                Span::styled(&dash.current_vessel, Style::default().fg(Color::Cyan)),
            ]),
            Line::from(format!("state  {:?}", dash.animation)),
            Line::from(format!("image  {}", companion_frame.display())),
            Line::from(format!("proto  {:?}", terminal_image::detect_current())),
        ])
        .block(
            Block::default()
                .title(" Companion Vessel ")
                .borders(Borders::ALL)
                .border_style(Style::default().fg(Color::Cyan)),
        );
        frame.render_widget(companion, top[0]);

        let stats = Paragraph::new(vec![
            Line::from(vec![
                Span::styled("DAY ", Style::default().add_modifier(Modifier::BOLD)),
                Span::raw(format!("{} / {}", dash.position, dash.total_days)),
            ]),
            Line::from(format!("coins  {}", dash.coins)),
            Line::from(format!("trust  {}    mood {}", dash.trust, dash.mood)),
            Line::from(format!("streak {}", dash.streak)),
        ])
        .block(Block::default().title(" Today ").borders(Borders::ALL));
        frame.render_widget(stats, top[1]);

        let map = Route::generate(dash.total_days).render_ascii(dash.position);
        frame.render_widget(
            Paragraph::new(map).block(Block::default().title(" Route ").borders(Borders::ALL)),
            root[1],
        );

        let log = dash.latest_log.as_deref().unwrap_or("No logs yet.");
        frame.render_widget(
            Paragraph::new(log).block(Block::default().title(" Log ").borders(Borders::ALL)),
            root[2],
        );
    })?;
    Ok(terminal.backend().to_string())
}

pub fn companion_frame_path(app: &BestmanApp, dash: &Dashboard) -> Result<PathBuf> {
    let catalog = VesselCatalog::load_with_user_dir(&app.paths.home.join("vessels"))?;
    let fallback = app.paths.cache.join("current-vessel-preview.png");
    if let Some(vessel) = catalog.find(&dash.current_vessel) {
        let cache = FrameCache::new(app.paths.cache.join("vessel-frames"));
        cache.first_animation_frame(vessel, animation_name(dash.animation))
    } else {
        Ok(fallback)
    }
}

pub fn export_dashboard_png(app: &BestmanApp, output: &Path) -> Result<()> {
    let dash = app.projection.dashboard()?;
    let companion_frame = companion_frame_path(app, &dash)?;
    export_dashboard_png_with_frame(app, output, &companion_frame)
}

pub fn export_dashboard_png_with_frame(
    app: &BestmanApp,
    output: &Path,
    companion_frame: &Path,
) -> Result<()> {
    let dash = app.projection.dashboard()?;
    let companion = image::open(&companion_frame)?.to_rgba8();
    let mut img = RgbaImage::from_pixel(900, 560, Rgba([13, 38, 48, 255]));

    fill_rect(&mut img, 24, 24, 852, 178, Rgba([18, 58, 70, 255]));
    fill_rect(&mut img, 24, 224, 852, 260, Rgba([14, 72, 88, 255]));
    fill_rect(&mut img, 24, 504, 852, 34, Rgba([18, 58, 70, 255]));
    blit(&mut img, &companion, 52, 48);

    draw_text_blocks(
        &mut img,
        220,
        48,
        &[
            "BESTMAN COMPANION",
            &format!("VESSEL {}", dash.current_vessel),
            &format!("STATE {:?}", dash.animation),
            &format!("DAY {} / {}", dash.position, dash.total_days),
            &format!(
                "COINS {}  TRUST {}  MOOD {}",
                dash.coins, dash.trust, dash.mood
            ),
        ],
        Rgba([232, 246, 236, 255]),
    );
    draw_route(
        &mut img,
        &Route::generate(dash.total_days),
        dash.position,
        50,
        250,
    );
    let log_line = if dash.latest_log.is_some() {
        "LOG READY"
    } else {
        "NO LOGS YET"
    };
    draw_text_blocks(&mut img, 48, 512, &[log_line], Rgba([210, 228, 220, 255]));

    if let Some(parent) = output.parent() {
        std::fs::create_dir_all(parent)?;
    }
    img.save(output)?;
    Ok(())
}

pub fn export_dashboard_frames(app: &BestmanApp, output_dir: &Path) -> Result<Vec<PathBuf>> {
    let dash = app.projection.dashboard()?;
    let catalog = VesselCatalog::load_with_user_dir(&app.paths.home.join("vessels"))?;
    let Some(vessel) = catalog.find(&dash.current_vessel) else {
        return Ok(Vec::new());
    };
    let animation = animation_name(dash.animation);
    let raw_dir = output_dir.join("vessel-frames");
    let frame_paths = crate::vessels::render::export_animation_frames(vessel, animation, &raw_dir)?;
    let dashboard_dir = output_dir.join("dashboard");
    std::fs::create_dir_all(&dashboard_dir)?;
    let mut out = Vec::new();
    for (idx, frame_path) in frame_paths.iter().enumerate() {
        let path = dashboard_dir.join(format!("dashboard-{idx:03}.png"));
        export_dashboard_png_with_frame(app, &path, frame_path)?;
        out.push(path);
    }
    Ok(out)
}

fn fill_rect(img: &mut RgbaImage, x: u32, y: u32, w: u32, h: u32, color: Rgba<u8>) {
    for yy in y..(y + h).min(img.height()) {
        for xx in x..(x + w).min(img.width()) {
            img.put_pixel(xx, yy, color);
        }
    }
}

fn blit(dst: &mut RgbaImage, src: &RgbaImage, x: u32, y: u32) {
    for sy in 0..src.height() {
        for sx in 0..src.width() {
            let px = src.get_pixel(sx, sy);
            if px.0[3] > 0 && x + sx < dst.width() && y + sy < dst.height() {
                dst.put_pixel(x + sx, y + sy, *px);
            }
        }
    }
}

fn draw_route(img: &mut RgbaImage, route: &Route, position: u32, ox: u32, oy: u32) {
    let cell = 16;
    for y in 0..route.height {
        for x in 0..route.width {
            let color = if (x + y) % 2 == 0 {
                Rgba([20, 100, 118, 255])
            } else {
                Rgba([18, 92, 110, 255])
            };
            fill_rect(img, ox + x * cell, oy + y * cell, cell - 1, cell - 1, color);
        }
    }
    for (idx, &(x, y)) in route.points.iter().enumerate() {
        let color = if idx as u32 <= position {
            Rgba([236, 190, 92, 255])
        } else {
            Rgba([92, 142, 152, 255])
        };
        fill_rect(img, ox + x * cell + 4, oy + y * cell + 4, 8, 8, color);
    }
    if let Some(&(x, y)) = route.points.get(position.saturating_sub(1) as usize) {
        fill_rect(
            img,
            ox + x * cell + 2,
            oy + y * cell + 2,
            12,
            12,
            Rgba([255, 238, 120, 255]),
        );
    }
}

fn draw_text_blocks(img: &mut RgbaImage, x: u32, y: u32, lines: &[&str], color: Rgba<u8>) {
    for (idx, line) in lines.iter().enumerate() {
        draw_tiny_text(img, x, y + idx as u32 * 22, line, color);
    }
}

fn draw_tiny_text(img: &mut RgbaImage, x: u32, y: u32, text: &str, color: Rgba<u8>) {
    let mut cx = x;
    for ch in text.to_ascii_uppercase().chars().take(80) {
        if ch == ' ' {
            cx += 8;
            continue;
        }
        draw_glyph(img, cx, y, ch, color);
        cx += 8;
    }
}

fn draw_glyph(img: &mut RgbaImage, x: u32, y: u32, ch: char, color: Rgba<u8>) {
    let rows = glyph_rows(ch);
    for (gy, row) in rows.iter().enumerate() {
        for (gx, bit) in row.chars().enumerate() {
            if bit == '1' {
                fill_rect(img, x + gx as u32, y + gy as u32 * 2, 1, 2, color);
            }
        }
    }
}

fn glyph_rows(ch: char) -> [&'static str; 7] {
    match ch {
        'A' => [
            "01110", "10001", "10001", "11111", "10001", "10001", "10001",
        ],
        'B' => [
            "11110", "10001", "10001", "11110", "10001", "10001", "11110",
        ],
        'C' => [
            "01111", "10000", "10000", "10000", "10000", "10000", "01111",
        ],
        'D' => [
            "11110", "10001", "10001", "10001", "10001", "10001", "11110",
        ],
        'E' => [
            "11111", "10000", "10000", "11110", "10000", "10000", "11111",
        ],
        'F' => [
            "11111", "10000", "10000", "11110", "10000", "10000", "10000",
        ],
        'G' => [
            "01111", "10000", "10000", "10011", "10001", "10001", "01110",
        ],
        'H' => [
            "10001", "10001", "10001", "11111", "10001", "10001", "10001",
        ],
        'I' => [
            "11111", "00100", "00100", "00100", "00100", "00100", "11111",
        ],
        'J' => [
            "00111", "00010", "00010", "00010", "10010", "10010", "01100",
        ],
        'K' => [
            "10001", "10010", "10100", "11000", "10100", "10010", "10001",
        ],
        'L' => [
            "10000", "10000", "10000", "10000", "10000", "10000", "11111",
        ],
        'M' => [
            "10001", "11011", "10101", "10101", "10001", "10001", "10001",
        ],
        'N' => [
            "10001", "11001", "10101", "10011", "10001", "10001", "10001",
        ],
        'O' => [
            "01110", "10001", "10001", "10001", "10001", "10001", "01110",
        ],
        'P' => [
            "11110", "10001", "10001", "11110", "10000", "10000", "10000",
        ],
        'Q' => [
            "01110", "10001", "10001", "10001", "10101", "10010", "01101",
        ],
        'R' => [
            "11110", "10001", "10001", "11110", "10100", "10010", "10001",
        ],
        'S' => [
            "01111", "10000", "10000", "01110", "00001", "00001", "11110",
        ],
        'T' => [
            "11111", "00100", "00100", "00100", "00100", "00100", "00100",
        ],
        'U' => [
            "10001", "10001", "10001", "10001", "10001", "10001", "01110",
        ],
        'V' => [
            "10001", "10001", "10001", "10001", "01010", "01010", "00100",
        ],
        'W' => [
            "10001", "10001", "10001", "10101", "10101", "10101", "01010",
        ],
        'X' => [
            "10001", "01010", "00100", "00100", "00100", "01010", "10001",
        ],
        'Y' => [
            "10001", "01010", "00100", "00100", "00100", "00100", "00100",
        ],
        'Z' => [
            "11111", "00001", "00010", "00100", "01000", "10000", "11111",
        ],
        '0' => [
            "01110", "10001", "10011", "10101", "11001", "10001", "01110",
        ],
        '1' => [
            "00100", "01100", "00100", "00100", "00100", "00100", "01110",
        ],
        '2' => [
            "01110", "10001", "00001", "00010", "00100", "01000", "11111",
        ],
        '3' => [
            "11110", "00001", "00001", "01110", "00001", "00001", "11110",
        ],
        '4' => [
            "00010", "00110", "01010", "10010", "11111", "00010", "00010",
        ],
        '5' => [
            "11111", "10000", "10000", "11110", "00001", "00001", "11110",
        ],
        '6' => [
            "01110", "10000", "10000", "11110", "10001", "10001", "01110",
        ],
        '7' => [
            "11111", "00001", "00010", "00100", "01000", "01000", "01000",
        ],
        '8' => [
            "01110", "10001", "10001", "01110", "10001", "10001", "01110",
        ],
        '9' => [
            "01110", "10001", "10001", "01111", "00001", "00001", "01110",
        ],
        ':' => [
            "00000", "00100", "00100", "00000", "00100", "00100", "00000",
        ],
        '/' => [
            "00001", "00010", "00010", "00100", "01000", "01000", "10000",
        ],
        '-' => [
            "00000", "00000", "00000", "11111", "00000", "00000", "00000",
        ],
        '_' => [
            "00000", "00000", "00000", "00000", "00000", "00000", "11111",
        ],
        '.' => [
            "00000", "00000", "00000", "00000", "00000", "01100", "01100",
        ],
        _ => [
            "11111", "10001", "00010", "00100", "00100", "00000", "00100",
        ],
    }
}
