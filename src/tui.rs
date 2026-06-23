use anyhow::Result;
use chrono::Local;
use crossterm::cursor::{Hide, MoveTo, Show};
use crossterm::event::{Event, KeyCode, KeyEvent, KeyModifiers, poll, read};
use crossterm::terminal::{
    EnterAlternateScreen, LeaveAlternateScreen, disable_raw_mode, enable_raw_mode,
};
use crossterm::{execute, queue};
use ratatui::Terminal;
use ratatui::backend::CrosstermBackend;
use ratatui::layout::{Alignment, Constraint, Direction, Layout, Rect};
use ratatui::style::{Color, Modifier, Style};
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, Borders, Gauge, Paragraph};
use std::io::{self, Stdout, Write};
use std::path::PathBuf;
use std::time::Duration;

use crate::app::BestmanApp;
use crate::dashboard::companion_frame_path;
use crate::events::{CompletionLevel, VesselAnimation};
use crate::projection::Dashboard;
use crate::projection::animation_name;
use crate::rules;
use crate::terminal_image::{self, ImageProtocol};
use crate::vessels::catalog::VesselCatalog;
use crate::vessels::render::FrameCache;

#[derive(Debug, Clone)]
pub struct LiveTuiOptions {
    pub ticks: Option<u16>,
    pub tick_ms: u64,
    pub alt_screen: bool,
    pub raw_mode: bool,
    pub script: Option<String>,
    pub forced_dice: Option<u32>,
    pub images: bool,
    pub force_kitty_images: bool,
    pub image_id: u32,
}

impl Default for LiveTuiOptions {
    fn default() -> Self {
        Self {
            ticks: None,
            tick_ms: 120,
            alt_screen: true,
            raw_mode: true,
            script: None,
            forced_dice: None,
            images: false,
            force_kitty_images: false,
            image_id: 9001,
        }
    }
}

pub fn render_static_dashboard(app: &BestmanApp) -> Result<()> {
    let dash = app.projection.dashboard()?;
    let _ = companion_frame_path(app, &dash)?;
    println!("{}", render_pet_snapshot(&dash, false, 0, Some(1), 96, 32)?);
    Ok(())
}

pub fn run_live_dashboard(app: &mut BestmanApp, options: LiveTuiOptions) -> Result<()> {
    let mut stdout = io::stdout();
    if options.raw_mode {
        enable_raw_mode()?;
    }
    if options.alt_screen {
        execute!(stdout, EnterAlternateScreen, Hide)?;
    }

    let result = run_live_dashboard_inner(app, options.clone(), stdout);

    let mut cleanup_stdout = io::stdout();
    if options.alt_screen {
        let _ = execute!(cleanup_stdout, Show, LeaveAlternateScreen);
    }
    if options.raw_mode {
        let _ = disable_raw_mode();
    }

    result
}

fn run_live_dashboard_inner(
    app: &mut BestmanApp,
    options: LiveTuiOptions,
    stdout: Stdout,
) -> Result<()> {
    let mut image_protocol = if options.force_kitty_images {
        ImageProtocol::Kitty
    } else if options.images {
        terminal_image::detect_current()
    } else {
        ImageProtocol::None
    };
    let mut image_frames = Vec::new();
    let mut last_image_frame_key: Option<String> = None;
    let backend = CrosstermBackend::new(stdout);
    let mut terminal = Terminal::new(backend)?;
    let tick_limit = options.ticks.map(|ticks| ticks.max(1));
    let scripted_actions = options
        .script
        .unwrap_or_default()
        .chars()
        .collect::<Vec<_>>();
    let mut tick: usize = 0;
    let mut notice: Option<String> = None;
    loop {
        if let Some(limit) = tick_limit {
            if tick >= limit as usize {
                break;
            }
        }
        if let Some(action) = scripted_actions.get(tick).copied() {
            match apply_action(app, action, options.forced_dice) {
                UiAction::Continue => {}
                UiAction::Quit => break,
                UiAction::Notice(message) => notice = Some(message),
            }
        } else if options.raw_mode {
            match handle_pending_input(app, options.forced_dice)? {
                UiAction::Continue => {}
                UiAction::Quit => break,
                UiAction::Notice(message) => notice = Some(message),
            }
        }

        let dash = app.projection.dashboard()?;
        terminal.draw(|frame| {
            draw_pet_dashboard(
                frame,
                &dash,
                image_protocol == ImageProtocol::Kitty,
                tick + 1,
                tick_limit,
                notice.as_deref(),
            );
        })?;
        if image_protocol == ImageProtocol::Kitty {
            let image_result = (|| -> Result<()> {
                refresh_image_frames(app, &mut image_frames, &mut last_image_frame_key)?;
                let size = terminal.size()?;
                let origin = companion_image_origin(Rect::new(0, 0, size.width, size.height));
                if tick % image_frame_stride(options.tick_ms) == 0 {
                    queue!(terminal.backend_mut(), MoveTo(origin.0, origin.1))?;
                    write_kitty_frame(
                        terminal.backend_mut(),
                        &image_frames,
                        tick,
                        options.image_id,
                    )?;
                }
                Ok(())
            })();
            if let Err(err) = image_result {
                image_protocol = ImageProtocol::None;
                notice = Some(format!("Image mode disabled: {err}"));
            }
        }
        tick = tick.saturating_add(1);
        if scripted_actions.is_empty() && options.raw_mode {
            match wait_for_next_frame(app, options.forced_dice, options.tick_ms)? {
                UiAction::Continue => {}
                UiAction::Quit => break,
                UiAction::Notice(message) => notice = Some(message),
            }
        } else if options.tick_ms > 0 && (!options.raw_mode || !scripted_actions.is_empty()) {
            std::thread::sleep(Duration::from_millis(options.tick_ms));
        }
    }
    if image_protocol == ImageProtocol::Kitty {
        let writer = terminal.backend_mut();
        write!(writer, "{}", terminal_image::kitty_delete(options.image_id))?;
        writer.flush()?;
    }
    terminal.show_cursor()?;
    Ok(())
}

#[derive(Debug, Clone, PartialEq, Eq)]
enum UiAction {
    Continue,
    Quit,
    Notice(String),
}

fn handle_pending_input(app: &mut BestmanApp, forced_dice: Option<u32>) -> Result<UiAction> {
    while poll(Duration::from_millis(0))? {
        if let Event::Key(key) = read()? {
            let action = handle_key(app, key, forced_dice);
            if !matches!(action, UiAction::Continue) {
                return Ok(action);
            }
        }
    }
    Ok(UiAction::Continue)
}

fn wait_for_next_frame(
    app: &mut BestmanApp,
    forced_dice: Option<u32>,
    tick_ms: u64,
) -> Result<UiAction> {
    let wait = Duration::from_millis(tick_ms);
    if poll(wait)? {
        if let Event::Key(key) = read()? {
            let action = handle_key(app, key, forced_dice);
            if !matches!(action, UiAction::Continue) {
                return Ok(action);
            }
        }
        return handle_pending_input(app, forced_dice);
    }
    Ok(UiAction::Continue)
}

fn handle_key(app: &mut BestmanApp, key: KeyEvent, forced_dice: Option<u32>) -> UiAction {
    if key.modifiers.contains(KeyModifiers::CONTROL) && matches!(key.code, KeyCode::Char('c')) {
        return UiAction::Quit;
    }
    let action = match key.code {
        KeyCode::Char(ch) => ch,
        KeyCode::Esc => 'q',
        _ => '\0',
    };
    apply_action(app, action, forced_dice)
}

fn image_frame_stride(tick_ms: u64) -> usize {
    let frame_ms = tick_ms.max(1);
    ((240 / frame_ms).max(1)) as usize
}

fn render_pet_snapshot(
    dash: &Dashboard,
    images_enabled: bool,
    tick: usize,
    ticks: Option<u16>,
    width: u16,
    height: u16,
) -> Result<String> {
    let backend = ratatui::backend::TestBackend::new(width, height);
    let mut terminal = Terminal::new(backend)?;
    terminal.draw(|frame| draw_pet_dashboard(frame, dash, images_enabled, tick, ticks, None))?;
    Ok(strip_test_backend_quotes(&terminal.backend().to_string()))
}

fn strip_test_backend_quotes(text: &str) -> String {
    let mut out = String::new();
    for (idx, line) in text.lines().enumerate() {
        if idx > 0 {
            out.push('\n');
        }
        let cleaned = line
            .split("\" Hidden by multi-width symbols:")
            .next()
            .unwrap_or(line)
            .trim_matches('"');
        out.push_str(cleaned);
    }
    out
}

fn draw_pet_dashboard(
    frame: &mut ratatui::Frame<'_>,
    dash: &Dashboard,
    images_enabled: bool,
    tick: usize,
    ticks: Option<u16>,
    notice: Option<&str>,
) {
    let area = frame.area();
    let areas = dashboard_areas(area);
    let progress = progress_ratio(dash);

    let title = Line::from(vec![
        Span::styled(
            "Bestman",
            Style::default()
                .fg(Color::Cyan)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw("  "),
        Span::styled(
            state_text(dash.animation),
            Style::default().fg(animation_color(dash.animation)),
        ),
    ]);
    let summary = Line::from(vec![
        Span::raw(format!("Day {} / {}", dash.position, dash.total_days)),
        Span::raw("   "),
        Span::styled(
            format!("{} coins", dash.coins),
            Style::default().fg(Color::Yellow),
        ),
        Span::raw("   "),
        Span::styled(
            format!("Mood {}", dash.mood),
            Style::default().fg(Color::Green),
        ),
        Span::raw("   "),
        Span::styled(
            format!("Trust {}", dash.trust),
            Style::default().fg(Color::LightBlue),
        ),
    ]);
    frame.render_widget(
        Paragraph::new(vec![title, summary])
            .alignment(Alignment::Center)
            .block(Block::default().borders(Borders::BOTTOM)),
        areas.header,
    );

    let stage_lines = if images_enabled {
        vec![
            Line::raw(""),
            Line::raw(""),
            Line::raw(""),
            Line::styled(
                "Your companion is here.",
                Style::default().fg(Color::DarkGray),
            ),
            Line::raw(""),
            Line::styled("~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~", Style::default().fg(Color::Blue)),
        ]
    } else {
        ascii_ship_lines(dash.animation)
    };
    frame.render_widget(
        Paragraph::new(stage_lines)
            .alignment(Alignment::Center)
            .block(
                Block::default()
                    .title(format!(" {} ", vessel_name(&dash.current_vessel)))
                    .borders(Borders::ALL)
                    .border_style(Style::default().fg(Color::Cyan)),
            ),
        areas.companion,
    );

    let today_recorded = dash.last_action_date == Some(Local::now().date_naive());
    let mut action_lines = vec![
        Line::styled(
            "Today",
            Style::default()
                .fg(Color::White)
                .add_modifier(Modifier::BOLD),
        ),
        Line::raw(""),
        Line::styled(
            today_message(dash, today_recorded),
            Style::default().fg(Color::LightGreen),
        ),
        Line::from(vec![
            Span::styled("Task ", Style::default().fg(Color::DarkGray)),
            Span::raw(dash.daily_task.clone()),
        ]),
        Line::raw(""),
        Line::from(vec![
            Span::styled("Streak ", Style::default().fg(Color::DarkGray)),
            Span::raw(dash.streak.to_string()),
        ]),
        Line::from(vec![
            Span::styled("Vessel ", Style::default().fg(Color::DarkGray)),
            Span::raw(vessel_name(&dash.current_vessel)),
        ]),
    ];
    if let Some(notice) = notice {
        action_lines.push(Line::raw(""));
        action_lines.push(Line::styled(
            notice.to_string(),
            Style::default().fg(Color::Cyan),
        ));
    }
    action_lines.extend([
        Line::raw(""),
        Line::styled("Keys", Style::default().fg(Color::DarkGray)),
        Line::styled("[L] Light   [N] Normal", Style::default().fg(Color::Yellow)),
        Line::styled(
            "[F] Full    [S] Rest    [Q] Quit",
            Style::default().fg(Color::Yellow),
        ),
    ]);
    frame.render_widget(
        Paragraph::new(action_lines)
            .block(Block::default().borders(Borders::ALL))
            .wrap(ratatui::widgets::Wrap { trim: true }),
        areas.today,
    );

    let gauge = Gauge::default()
        .block(Block::default().title(" Voyage ").borders(Borders::ALL))
        .gauge_style(
            Style::default()
                .fg(Color::Yellow)
                .bg(Color::DarkGray)
                .add_modifier(Modifier::BOLD),
        )
        .ratio(progress)
        .label(format!("{:.0}%  {}", progress * 100.0, compact_route(dash)));
    frame.render_widget(gauge, areas.progress);

    let log = dash
        .latest_log
        .as_deref()
        .unwrap_or("The sea is quiet. Today's log will appear after the next check-in.");
    frame.render_widget(
        Paragraph::new(vec![
            Line::styled(
                "Captain's Log",
                Style::default()
                    .fg(Color::White)
                    .add_modifier(Modifier::BOLD),
            ),
            Line::raw(""),
            Line::raw(log),
        ])
        .block(Block::default().borders(Borders::ALL))
        .wrap(ratatui::widgets::Wrap { trim: true }),
        areas.log,
    );

    let footer = match ticks {
        Some(limit) => format!("frame {tick}/{limit}"),
        None => format!("frame {tick}   q quits"),
    };
    frame.render_widget(
        Paragraph::new(footer)
            .alignment(Alignment::Right)
            .style(Style::default().fg(Color::DarkGray)),
        areas.footer,
    );
}

#[derive(Debug, Clone, Copy)]
struct DashboardAreas {
    header: Rect,
    companion: Rect,
    today: Rect,
    progress: Rect,
    log: Rect,
    footer: Rect,
}

fn dashboard_areas(area: Rect) -> DashboardAreas {
    let root = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(4),
            Constraint::Min(14),
            Constraint::Length(3),
            Constraint::Length(7),
            Constraint::Length(1),
        ])
        .split(area);
    let main = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([Constraint::Percentage(58), Constraint::Percentage(42)])
        .split(root[1]);
    DashboardAreas {
        header: root[0],
        companion: main[0],
        today: main[1],
        progress: root[2],
        log: root[3],
        footer: root[4],
    }
}

fn companion_image_origin(area: Rect) -> (u16, u16) {
    let areas = dashboard_areas(area);
    (
        areas.companion.x.saturating_add(4),
        areas.companion.y.saturating_add(3),
    )
}

fn progress_ratio(dash: &Dashboard) -> f64 {
    let total = dash.total_days.max(1) as f64;
    (dash.position.min(dash.total_days) as f64 / total).clamp(0.0, 1.0)
}

fn state_text(animation: VesselAnimation) -> &'static str {
    match animation {
        VesselAnimation::Waiting => "Waiting for today's voyage",
        VesselAnimation::Sailing => "Sailing after check-in",
        VesselAnimation::Happy | VesselAnimation::Celebrating | VesselAnimation::Treasure => {
            "Bright and encouraged"
        }
        VesselAnimation::Resting => "Resting at anchor",
        VesselAnimation::LowEnergy => "Low energy",
        VesselAnimation::Idle => "At harbor",
    }
}

fn today_message(dash: &Dashboard, today_recorded: bool) -> &'static str {
    if today_recorded {
        return match dash.last_action_kind.as_deref() {
            Some("check_in") => "Today's training is recorded.",
            Some("rest") => "Today's planned rest is recorded.",
            Some("skip") => "Today's rest/skip is recorded.",
            _ => "Today is recorded.",
        };
    }
    match dash.animation {
        VesselAnimation::Waiting | VesselAnimation::Idle => "Ready for today's training.",
        VesselAnimation::Sailing => "Training logged. The sloop is moving.",
        VesselAnimation::Resting => "Rest day recorded. The sloop is anchored.",
        VesselAnimation::LowEnergy => "Keep it light today.",
        VesselAnimation::Happy | VesselAnimation::Celebrating | VesselAnimation::Treasure => {
            "A good day on the water."
        }
    }
}

fn animation_color(animation: VesselAnimation) -> Color {
    match animation {
        VesselAnimation::Waiting | VesselAnimation::Idle => Color::LightBlue,
        VesselAnimation::Sailing => Color::Green,
        VesselAnimation::Resting => Color::Blue,
        VesselAnimation::LowEnergy => Color::Red,
        VesselAnimation::Happy | VesselAnimation::Celebrating | VesselAnimation::Treasure => {
            Color::Yellow
        }
    }
}

fn vessel_name(id: &str) -> String {
    id.split('_')
        .filter(|part| !part.is_empty())
        .map(|part| {
            let mut chars = part.chars();
            match chars.next() {
                Some(first) => format!("{}{}", first.to_ascii_uppercase(), chars.as_str()),
                None => String::new(),
            }
        })
        .collect::<Vec<_>>()
        .join(" ")
}

fn ascii_ship_lines(animation: VesselAnimation) -> Vec<Line<'static>> {
    let water = if matches!(animation, VesselAnimation::Sailing) {
        "~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~"
    } else {
        "  ~ ~ ~ ~ ~ ~ ~ ~ ~ ~  "
    };
    vec![
        Line::raw(""),
        Line::raw("           |"),
        Line::raw("          /|\\"),
        Line::raw("         /_|_\\"),
        Line::raw("      ___\\___/___"),
        Line::raw("        \\_____/"),
        Line::styled(water, Style::default().fg(Color::Blue)),
    ]
}

fn compact_route(dash: &Dashboard) -> String {
    let slots = 18usize;
    let total = dash.total_days.max(1) as usize;
    let pos = dash.position.min(dash.total_days) as usize;
    let marker = ((pos * slots) / total).min(slots.saturating_sub(1));
    let mut out = String::with_capacity(slots);
    for idx in 0..slots {
        if idx == marker {
            out.push('S');
        } else if idx < marker {
            out.push('=');
        } else {
            out.push('~');
        }
    }
    out
}

fn refresh_image_frames(
    app: &BestmanApp,
    image_frames: &mut Vec<PathBuf>,
    last_key: &mut Option<String>,
) -> Result<()> {
    let dash = app.projection.dashboard()?;
    let animation = animation_name(dash.animation);
    let key = format!("{}:{animation}", dash.current_vessel);
    if last_key.as_deref() == Some(key.as_str()) && !image_frames.is_empty() {
        return Ok(());
    }

    let catalog = VesselCatalog::load_with_user_dir(&app.paths.home.join("vessels"))?;
    if let Some(vessel) = catalog.find(&dash.current_vessel) {
        let cache = FrameCache::new(app.paths.cache.join("vessel-frames"));
        *image_frames = cache.animation_frames(vessel, animation)?;
    } else {
        image_frames.clear();
    }
    *last_key = Some(key);
    Ok(())
}

fn write_kitty_frame<W: Write>(
    writer: &mut W,
    image_frames: &[PathBuf],
    tick: usize,
    image_id: u32,
) -> Result<()> {
    if image_frames.is_empty() {
        return Ok(());
    }
    let frame = &image_frames[tick % image_frames.len()];
    write!(writer, "{}", terminal_image::kitty_delete(image_id))?;
    write!(
        writer,
        "{}",
        terminal_image::kitty_inline_png(frame, image_id)?
    )?;
    writer.flush()?;
    Ok(())
}

fn apply_action(app: &mut BestmanApp, action: char, forced_dice: Option<u32>) -> UiAction {
    match action {
        'l' | 'L' => {
            return action_notice(
                append_check_in(app, CompletionLevel::Light, forced_dice),
                "Light check-in recorded.",
            );
        }
        'n' | 'N' => {
            return action_notice(
                append_check_in(app, CompletionLevel::Normal, forced_dice),
                "Normal check-in recorded.",
            );
        }
        'f' | 'F' => {
            return action_notice(
                append_check_in(app, CompletionLevel::Full, forced_dice),
                "Full check-in recorded.",
            );
        }
        's' | 'S' => return action_notice(append_skip(app), "Rest recorded."),
        'q' | 'Q' => return UiAction::Quit,
        _ => {}
    }
    UiAction::Continue
}

fn action_notice(result: Result<()>, success: &str) -> UiAction {
    match result {
        Ok(()) => UiAction::Notice(success.to_string()),
        Err(err) => UiAction::Notice(err.to_string()),
    }
}

fn append_check_in(
    app: &mut BestmanApp,
    level: CompletionLevel,
    forced_dice: Option<u32>,
) -> Result<()> {
    app.rebuild_projection()?;
    let dash = app.projection.dashboard()?;
    let event = rules::check_in_event(
        &app.config,
        &dash,
        Local::now().date_naive(),
        level,
        "tui action".to_string(),
        forced_dice,
    )?;
    app.store.append(event)?;
    app.rebuild_projection()?;
    Ok(())
}

fn append_skip(app: &mut BestmanApp) -> Result<()> {
    app.rebuild_projection()?;
    let dash = app.projection.dashboard()?;
    let event = rules::skip_or_rest_event(
        &app.config,
        &dash,
        Local::now().date_naive(),
        "tui rest".to_string(),
    )?;
    app.store.append(event)?;
    app.rebuild_projection()?;
    Ok(())
}
