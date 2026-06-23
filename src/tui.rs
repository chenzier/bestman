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

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum DashboardTab {
    Today,
    Plan,
    Shop,
    Fleet,
    Log,
}

impl DashboardTab {
    const ALL: [DashboardTab; 5] = [
        DashboardTab::Today,
        DashboardTab::Plan,
        DashboardTab::Shop,
        DashboardTab::Fleet,
        DashboardTab::Log,
    ];

    fn label(self) -> &'static str {
        match self {
            DashboardTab::Today => "Today",
            DashboardTab::Plan => "Plan",
            DashboardTab::Shop => "Shop",
            DashboardTab::Fleet => "Fleet",
            DashboardTab::Log => "Log",
        }
    }

    fn next(self) -> Self {
        let idx = Self::ALL
            .iter()
            .position(|tab| *tab == self)
            .unwrap_or_default();
        Self::ALL[(idx + 1) % Self::ALL.len()]
    }

    fn previous(self) -> Self {
        let idx = Self::ALL
            .iter()
            .position(|tab| *tab == self)
            .unwrap_or_default();
        Self::ALL[(idx + Self::ALL.len() - 1) % Self::ALL.len()]
    }
}

#[derive(Debug, Clone)]
struct TuiState {
    tab: DashboardTab,
    shop_selected: usize,
    fleet_selected: usize,
}

impl Default for TuiState {
    fn default() -> Self {
        Self {
            tab: DashboardTab::Today,
            shop_selected: 0,
            fleet_selected: 0,
        }
    }
}

impl TuiState {
    fn next_tab(&mut self) {
        self.tab = self.tab.next();
    }

    fn previous_tab(&mut self) {
        self.tab = self.tab.previous();
    }

    fn move_selection(&mut self, catalog: &VesselCatalog, delta: isize) {
        let len = catalog.vessel_items().count();
        if len == 0 {
            self.shop_selected = 0;
            self.fleet_selected = 0;
            return;
        }
        let selected = match self.tab {
            DashboardTab::Shop => &mut self.shop_selected,
            DashboardTab::Fleet => &mut self.fleet_selected,
            _ => return,
        };
        let next = (*selected as isize + delta).clamp(0, len.saturating_sub(1) as isize);
        *selected = next as usize;
    }
}

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
    let catalog = VesselCatalog::load_with_user_dir(&app.paths.home.join("vessels"))?;
    println!(
        "{}",
        render_pet_snapshot(
            &dash,
            &catalog,
            &TuiState::default(),
            false,
            0,
            Some(1),
            96,
            32
        )?
    );
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
    let catalog = VesselCatalog::load_with_user_dir(&app.paths.home.join("vessels"))?;
    let mut ui_state = TuiState::default();
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
            match apply_action(app, &catalog, &mut ui_state, action, options.forced_dice) {
                UiAction::Continue => {}
                UiAction::Quit => break,
                UiAction::Notice(message) => notice = Some(message),
            }
        } else if options.raw_mode {
            match handle_pending_input(app, &catalog, &mut ui_state, options.forced_dice)? {
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
                &catalog,
                &ui_state,
                image_protocol == ImageProtocol::Kitty,
                tick + 1,
                tick_limit,
                notice.as_deref(),
            );
        })?;
        if image_protocol == ImageProtocol::Kitty && ui_state.tab == DashboardTab::Today {
            let image_result = (|| -> Result<()> {
                refresh_image_frames(app, &mut image_frames, &mut last_image_frame_key)?;
                let size = terminal.size()?;
                let placement = companion_image_placement(Rect::new(0, 0, size.width, size.height));
                if tick % image_frame_stride(options.tick_ms) == 0 {
                    queue!(terminal.backend_mut(), MoveTo(placement.x, placement.y))?;
                    write_kitty_frame(
                        terminal.backend_mut(),
                        &image_frames,
                        tick,
                        options.image_id,
                        placement.columns,
                        placement.rows,
                    )?;
                }
                Ok(())
            })();
            if let Err(err) = image_result {
                image_protocol = ImageProtocol::None;
                notice = Some(format!("Image mode disabled: {err}"));
            }
        } else if image_protocol == ImageProtocol::Kitty {
            write!(
                terminal.backend_mut(),
                "{}",
                terminal_image::kitty_delete(options.image_id)
            )?;
            terminal.backend_mut().flush()?;
        }
        tick = tick.saturating_add(1);
        if scripted_actions.is_empty() && options.raw_mode {
            match wait_for_next_frame(
                app,
                &catalog,
                &mut ui_state,
                options.forced_dice,
                options.tick_ms,
            )? {
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

fn handle_pending_input(
    app: &mut BestmanApp,
    catalog: &VesselCatalog,
    ui_state: &mut TuiState,
    forced_dice: Option<u32>,
) -> Result<UiAction> {
    while poll(Duration::from_millis(0))? {
        if let Event::Key(key) = read()? {
            let action = handle_key(app, catalog, ui_state, key, forced_dice);
            if !matches!(action, UiAction::Continue) {
                return Ok(action);
            }
        }
    }
    Ok(UiAction::Continue)
}

fn wait_for_next_frame(
    app: &mut BestmanApp,
    catalog: &VesselCatalog,
    ui_state: &mut TuiState,
    forced_dice: Option<u32>,
    tick_ms: u64,
) -> Result<UiAction> {
    let wait = Duration::from_millis(tick_ms);
    if poll(wait)? {
        if let Event::Key(key) = read()? {
            let action = handle_key(app, catalog, ui_state, key, forced_dice);
            if !matches!(action, UiAction::Continue) {
                return Ok(action);
            }
        }
        return handle_pending_input(app, catalog, ui_state, forced_dice);
    }
    Ok(UiAction::Continue)
}

fn handle_key(
    app: &mut BestmanApp,
    catalog: &VesselCatalog,
    ui_state: &mut TuiState,
    key: KeyEvent,
    forced_dice: Option<u32>,
) -> UiAction {
    if key.modifiers.contains(KeyModifiers::CONTROL) && matches!(key.code, KeyCode::Char('c')) {
        return UiAction::Quit;
    }
    match key.code {
        KeyCode::Tab => {
            ui_state.next_tab();
            UiAction::Continue
        }
        KeyCode::BackTab => {
            ui_state.previous_tab();
            UiAction::Continue
        }
        KeyCode::Up => {
            ui_state.move_selection(catalog, -1);
            UiAction::Continue
        }
        KeyCode::Down => {
            ui_state.move_selection(catalog, 1);
            UiAction::Continue
        }
        KeyCode::Char(ch) => apply_action(app, catalog, ui_state, ch, forced_dice),
        KeyCode::Esc => UiAction::Quit,
        _ => UiAction::Continue,
    }
}

fn image_frame_stride(tick_ms: u64) -> usize {
    let frame_ms = tick_ms.max(1);
    ((240 / frame_ms).max(1)) as usize
}

fn render_pet_snapshot(
    dash: &Dashboard,
    catalog: &VesselCatalog,
    ui_state: &TuiState,
    images_enabled: bool,
    tick: usize,
    ticks: Option<u16>,
    width: u16,
    height: u16,
) -> Result<String> {
    let backend = ratatui::backend::TestBackend::new(width, height);
    let mut terminal = Terminal::new(backend)?;
    terminal.draw(|frame| {
        draw_pet_dashboard(
            frame,
            dash,
            catalog,
            ui_state,
            images_enabled,
            tick,
            ticks,
            None,
        )
    })?;
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
    catalog: &VesselCatalog,
    ui_state: &TuiState,
    images_enabled: bool,
    tick: usize,
    ticks: Option<u16>,
    notice: Option<&str>,
) {
    let area = frame.area();
    let areas = dashboard_areas(area);

    let title = Line::from(vec![
        Span::styled(
            "Bestman Companion",
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
        Span::styled("Today ", Style::default().fg(Color::DarkGray)),
        Span::styled(
            dash.daily_task.clone(),
            Style::default()
                .fg(Color::White)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw("    "),
        Span::raw(format!("Day {} / {}", dash.position, dash.total_days)),
    ]);
    frame.render_widget(
        Paragraph::new(vec![title, summary])
            .alignment(Alignment::Center)
            .block(Block::default().borders(Borders::BOTTOM)),
        areas.header,
    );

    frame.render_widget(
        Paragraph::new(tab_bar_lines(ui_state.tab))
            .alignment(Alignment::Center)
            .block(Block::default().borders(Borders::BOTTOM)),
        areas.tabs,
    );

    match ui_state.tab {
        DashboardTab::Today => draw_today_tab(frame, dash, images_enabled, notice, &areas),
        DashboardTab::Plan => draw_plan_tab(frame, dash, notice, areas.body),
        DashboardTab::Shop => draw_shop_tab(frame, dash, catalog, ui_state, notice, areas.body),
        DashboardTab::Fleet => draw_fleet_tab(frame, dash, catalog, ui_state, notice, areas.body),
        DashboardTab::Log => draw_log_tab(frame, dash, notice, areas.body),
    }

    let footer = match ticks {
        Some(limit) => format!("frame {tick}/{limit}   Tab switch   q quit"),
        None => format!("frame {tick}   Tab switch   q quit"),
    };
    frame.render_widget(
        Paragraph::new(footer)
            .alignment(Alignment::Right)
            .style(Style::default().fg(Color::DarkGray)),
        areas.footer,
    );
}

fn draw_today_tab(
    frame: &mut ratatui::Frame<'_>,
    dash: &Dashboard,
    images_enabled: bool,
    notice: Option<&str>,
    areas: &DashboardAreas,
) {
    let progress = progress_ratio(dash);
    let today_recorded = dash.last_action_date == Some(Local::now().date_naive());

    let stage_lines = if images_enabled {
        vec![
            Line::raw(""),
            Line::raw(""),
            Line::raw(""),
            Line::raw(""),
            Line::raw(""),
            Line::styled("~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~", Style::default().fg(Color::Blue)),
        ]
    } else {
        companion_stage_lines(dash)
    };
    frame.render_widget(
        Paragraph::new(stage_lines)
            .alignment(Alignment::Center)
            .block(
                Block::default()
                    .title(format!(
                        " Companion · {} ",
                        vessel_name(&dash.current_vessel)
                    ))
                    .borders(Borders::ALL)
                    .border_style(Style::default().fg(Color::Cyan)),
            ),
        areas.companion,
    );

    frame.render_widget(
        Paragraph::new(today_action_lines(dash, today_recorded, notice))
            .block(
                Block::default()
                    .title(" Today ")
                    .borders(Borders::ALL)
                    .border_style(Style::default().fg(if today_recorded {
                        Color::Green
                    } else {
                        Color::Yellow
                    })),
            )
            .wrap(ratatui::widgets::Wrap { trim: true }),
        areas.today,
    );

    let gauge = Gauge::default()
        .block(
            Block::default()
                .title(" Route progress ")
                .borders(Borders::ALL),
        )
        .gauge_style(
            Style::default()
                .fg(Color::Yellow)
                .bg(Color::DarkGray)
                .add_modifier(Modifier::BOLD),
        )
        .ratio(progress)
        .label(format!("{:.0}%  {}", progress * 100.0, compact_route(dash)));
    frame.render_widget(gauge, areas.progress);
}

fn draw_plan_tab(
    frame: &mut ratatui::Frame<'_>,
    dash: &Dashboard,
    notice: Option<&str>,
    area: Rect,
) {
    let mut lines = vec![
        Line::styled(
            "Training Plan",
            Style::default()
                .fg(Color::White)
                .add_modifier(Modifier::BOLD),
        ),
        Line::raw(""),
        Line::from(vec![
            Span::styled("Goal  ", Style::default().fg(Color::DarkGray)),
            Span::raw(
                dash.plan_goal
                    .clone()
                    .unwrap_or_else(|| "No plan yet. Use `bestman plan create`.".to_string()),
            ),
        ]),
        Line::from(vec![
            Span::styled("Today ", Style::default().fg(Color::DarkGray)),
            Span::styled(
                dash.daily_task.clone(),
                Style::default()
                    .fg(Color::White)
                    .add_modifier(Modifier::BOLD),
            ),
        ]),
        Line::raw(""),
        Line::styled("Tasks", Style::default().fg(Color::DarkGray)),
    ];
    if dash.plan_tasks.is_empty() {
        lines.push(Line::raw("No plan tasks yet."));
    } else {
        for (idx, task) in dash.plan_tasks.iter().enumerate() {
            lines.push(Line::raw(format!("{:>2}. {task}", idx + 1)));
        }
    }
    push_notice(&mut lines, notice);
    lines.push(Line::raw(""));
    lines.push(Line::styled(
        "Tab switch pages   q quit",
        Style::default().fg(Color::DarkGray),
    ));
    frame.render_widget(
        Paragraph::new(lines)
            .block(
                Block::default()
                    .title(" Plan ")
                    .borders(Borders::ALL)
                    .border_style(Style::default().fg(Color::LightBlue)),
            )
            .wrap(ratatui::widgets::Wrap { trim: true }),
        area,
    );
}

fn draw_shop_tab(
    frame: &mut ratatui::Frame<'_>,
    dash: &Dashboard,
    catalog: &VesselCatalog,
    ui_state: &TuiState,
    notice: Option<&str>,
    area: Rect,
) {
    let mut lines = vec![
        Line::styled(
            "Ship Shop",
            Style::default()
                .fg(Color::White)
                .add_modifier(Modifier::BOLD),
        ),
        Line::from(vec![
            Span::styled("Coins ", Style::default().fg(Color::DarkGray)),
            Span::styled(dash.coins.to_string(), Style::default().fg(Color::Yellow)),
            Span::raw("   "),
            Span::styled("Buy ", Style::default().fg(Color::DarkGray)),
            Span::styled("B", Style::default().fg(Color::Yellow)),
            Span::raw("   "),
            Span::styled("Move ", Style::default().fg(Color::DarkGray)),
            Span::raw("↑/↓"),
        ]),
        Line::raw(""),
    ];
    let selected = bounded_selection(ui_state.shop_selected, catalog.vessel_items().count());
    for (idx, item) in catalog.vessel_items().enumerate() {
        let owned = dash.owned_items.iter().any(|id| id == &item.id);
        let affordable = dash.coins >= item.price;
        let name = catalog_vessel_name(catalog, &item.id);
        let status = if owned {
            "owned"
        } else if affordable {
            "available"
        } else {
            "need coins"
        };
        let style = if idx == selected {
            Style::default()
                .fg(Color::Black)
                .bg(Color::Yellow)
                .add_modifier(Modifier::BOLD)
        } else if owned {
            Style::default().fg(Color::Green)
        } else if affordable {
            Style::default().fg(Color::White)
        } else {
            Style::default().fg(Color::DarkGray)
        };
        lines.push(Line::styled(
            format!(
                "{} {:<18} {:<22} price {:>3}  {:<8}  {}",
                if idx == selected { ">" } else { " " },
                item.id,
                name,
                item.price,
                item.rarity,
                status
            ),
            style,
        ));
    }
    push_notice(&mut lines, notice);
    frame.render_widget(
        Paragraph::new(lines)
            .block(
                Block::default()
                    .title(" Shop ")
                    .borders(Borders::ALL)
                    .border_style(Style::default().fg(Color::Yellow)),
            )
            .wrap(ratatui::widgets::Wrap { trim: true }),
        area,
    );
}

fn draw_fleet_tab(
    frame: &mut ratatui::Frame<'_>,
    dash: &Dashboard,
    catalog: &VesselCatalog,
    ui_state: &TuiState,
    notice: Option<&str>,
    area: Rect,
) {
    let mut lines = vec![
        Line::styled(
            "Fleet",
            Style::default()
                .fg(Color::White)
                .add_modifier(Modifier::BOLD),
        ),
        Line::from(vec![
            Span::styled("Current ", Style::default().fg(Color::DarkGray)),
            Span::styled(
                catalog_vessel_name(catalog, &dash.current_vessel),
                Style::default().fg(Color::Cyan),
            ),
            Span::raw("   "),
            Span::styled("Equip ", Style::default().fg(Color::DarkGray)),
            Span::styled("E", Style::default().fg(Color::Yellow)),
            Span::raw("   "),
            Span::styled("Move ", Style::default().fg(Color::DarkGray)),
            Span::raw("↑/↓"),
        ]),
        Line::raw(""),
    ];
    let selected = bounded_selection(ui_state.fleet_selected, catalog.vessel_items().count());
    for (idx, item) in catalog.vessel_items().enumerate() {
        let owned = dash.owned_vessels.iter().any(|id| id == &item.id);
        let equipped = dash.current_vessel == item.id;
        let status = if equipped {
            "equipped"
        } else if owned {
            "owned"
        } else {
            "locked"
        };
        let style = if idx == selected {
            Style::default()
                .fg(Color::Black)
                .bg(Color::LightBlue)
                .add_modifier(Modifier::BOLD)
        } else if equipped {
            Style::default().fg(Color::Cyan)
        } else if owned {
            Style::default().fg(Color::Green)
        } else {
            Style::default().fg(Color::DarkGray)
        };
        lines.push(Line::styled(
            format!(
                "{} {:<18} {:<22} {:<8}  {}",
                if idx == selected { ">" } else { " " },
                item.id,
                catalog_vessel_name(catalog, &item.id),
                item.rarity,
                status
            ),
            style,
        ));
    }
    push_notice(&mut lines, notice);
    frame.render_widget(
        Paragraph::new(lines)
            .block(
                Block::default()
                    .title(" Fleet ")
                    .borders(Borders::ALL)
                    .border_style(Style::default().fg(Color::LightBlue)),
            )
            .wrap(ratatui::widgets::Wrap { trim: true }),
        area,
    );
}

fn draw_log_tab(
    frame: &mut ratatui::Frame<'_>,
    dash: &Dashboard,
    notice: Option<&str>,
    area: Rect,
) {
    let log = dash
        .latest_log
        .as_deref()
        .unwrap_or("The sea is quiet. Today's log will appear after the next check-in.");
    let mut lines = vec![
        Line::styled(
            "Captain's Log",
            Style::default()
                .fg(Color::White)
                .add_modifier(Modifier::BOLD),
        ),
        Line::raw(""),
        Line::raw(log.to_string()),
    ];
    push_notice(&mut lines, notice);
    frame.render_widget(
        Paragraph::new(lines)
            .block(
                Block::default()
                    .title(" Log ")
                    .borders(Borders::ALL)
                    .border_style(Style::default().fg(Color::Green)),
            )
            .wrap(ratatui::widgets::Wrap { trim: true }),
        area,
    );
}

#[derive(Debug, Clone, Copy)]
struct DashboardAreas {
    header: Rect,
    tabs: Rect,
    body: Rect,
    companion: Rect,
    today: Rect,
    progress: Rect,
    footer: Rect,
}

fn dashboard_areas(area: Rect) -> DashboardAreas {
    let root = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(3),
            Constraint::Length(2),
            Constraint::Min(12),
            Constraint::Length(3),
            Constraint::Length(1),
        ])
        .split(area);
    let main = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([Constraint::Percentage(64), Constraint::Percentage(36)])
        .split(root[2]);
    DashboardAreas {
        header: root[0],
        tabs: root[1],
        body: root[2],
        companion: main[0],
        today: main[1],
        progress: root[3],
        footer: root[4],
    }
}

#[derive(Debug, Clone, Copy)]
struct ImagePlacement {
    x: u16,
    y: u16,
    columns: u16,
    rows: u16,
}

fn companion_image_placement(area: Rect) -> ImagePlacement {
    let areas = dashboard_areas(area);
    let columns = (areas.companion.width.saturating_sub(8)).clamp(24, 56);
    let rows = (areas.companion.height.saturating_sub(8)).clamp(10, 24);
    ImagePlacement {
        x: areas
            .companion
            .x
            .saturating_add(areas.companion.width.saturating_sub(columns) / 2),
        y: areas
            .companion
            .y
            .saturating_add(areas.companion.height.saturating_sub(rows) / 2)
            .saturating_sub(1),
        columns,
        rows,
    }
}

fn tab_bar_lines(current: DashboardTab) -> Vec<Line<'static>> {
    let mut spans = Vec::new();
    for tab in DashboardTab::ALL {
        if !spans.is_empty() {
            spans.push(Span::raw("  "));
        }
        let label = format!(" {} ", tab.label());
        if tab == current {
            spans.push(Span::styled(
                label,
                Style::default()
                    .fg(Color::Black)
                    .bg(Color::Cyan)
                    .add_modifier(Modifier::BOLD),
            ));
        } else {
            spans.push(Span::styled(label, Style::default().fg(Color::DarkGray)));
        }
    }
    vec![Line::from(spans)]
}

fn today_action_lines(
    dash: &Dashboard,
    today_recorded: bool,
    notice: Option<&str>,
) -> Vec<Line<'static>> {
    let mut lines = vec![
        Line::styled(
            if today_recorded {
                "Today is done"
            } else {
                "Today's action"
            },
            Style::default()
                .fg(Color::White)
                .add_modifier(Modifier::BOLD),
        ),
        Line::raw(""),
        Line::styled(
            today_message(dash, today_recorded),
            Style::default().fg(Color::LightGreen),
        ),
        Line::raw(""),
        Line::from(vec![
            Span::styled("Task ", Style::default().fg(Color::DarkGray)),
            Span::styled(
                dash.daily_task.clone(),
                Style::default()
                    .fg(Color::White)
                    .add_modifier(Modifier::BOLD),
            ),
        ]),
        Line::raw(""),
        Line::from(vec![
            Span::styled("Coins ", Style::default().fg(Color::DarkGray)),
            Span::styled(dash.coins.to_string(), Style::default().fg(Color::Yellow)),
            Span::raw("   "),
            Span::styled("Streak ", Style::default().fg(Color::DarkGray)),
            Span::styled(
                dash.streak.to_string(),
                Style::default().fg(Color::LightGreen),
            ),
        ]),
        Line::from(vec![
            Span::styled("Mood ", Style::default().fg(Color::DarkGray)),
            Span::styled(dash.mood.to_string(), Style::default().fg(Color::Green)),
            Span::raw("   "),
            Span::styled("Trust ", Style::default().fg(Color::DarkGray)),
            Span::styled(
                dash.trust.to_string(),
                Style::default().fg(Color::LightBlue),
            ),
        ]),
    ];
    push_notice(&mut lines, notice);
    lines.extend([
        Line::raw(""),
        Line::styled("Check in", Style::default().fg(Color::DarkGray)),
        Line::styled("[F] Full training", Style::default().fg(Color::Yellow)),
        Line::styled("[N] Normal   [L] Light", Style::default().fg(Color::Yellow)),
        Line::styled(
            "[S] Rest     [Tab] Plan/Shop/Fleet/Log     [Q] Quit",
            Style::default().fg(Color::DarkGray),
        ),
    ]);
    lines
}

fn push_notice(lines: &mut Vec<Line<'static>>, notice: Option<&str>) {
    if let Some(notice) = notice {
        lines.push(Line::raw(""));
        lines.push(Line::styled(
            notice.to_string(),
            Style::default().fg(Color::Cyan),
        ));
    }
}

fn bounded_selection(selected: usize, len: usize) -> usize {
    if len == 0 {
        0
    } else {
        selected.min(len.saturating_sub(1))
    }
}

fn catalog_vessel_name(catalog: &VesselCatalog, id: &str) -> String {
    catalog
        .find(id)
        .map(|vessel| vessel.display_name.clone())
        .unwrap_or_else(|| vessel_name(id))
}

fn selected_shop_item<'a>(
    catalog: &'a VesselCatalog,
    ui_state: &TuiState,
) -> Option<&'a crate::vessels::catalog::CatalogItem> {
    let selected = bounded_selection(ui_state.shop_selected, catalog.vessel_items().count());
    catalog.vessel_items().nth(selected)
}

fn selected_fleet_item<'a>(
    catalog: &'a VesselCatalog,
    ui_state: &TuiState,
) -> Option<&'a crate::vessels::catalog::CatalogItem> {
    let selected = bounded_selection(ui_state.fleet_selected, catalog.vessel_items().count());
    catalog.vessel_items().nth(selected)
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

fn companion_stage_lines(dash: &Dashboard) -> Vec<Line<'static>> {
    let mut lines = Vec::new();
    lines.push(Line::raw(""));
    lines.extend(ascii_ship_lines(dash.animation));
    lines.push(Line::raw(""));
    lines.push(Line::styled(
        state_text(dash.animation),
        Style::default()
            .fg(animation_color(dash.animation))
            .add_modifier(Modifier::BOLD),
    ));
    lines.push(Line::from(vec![
        Span::styled("Route ", Style::default().fg(Color::DarkGray)),
        Span::raw(format!("{} / {}", dash.position, dash.total_days)),
        Span::raw("   "),
        Span::styled("Vessel ", Style::default().fg(Color::DarkGray)),
        Span::raw(vessel_name(&dash.current_vessel)),
    ]));
    lines
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
    columns: u16,
    rows: u16,
) -> Result<()> {
    if image_frames.is_empty() {
        return Ok(());
    }
    let frame = &image_frames[tick % image_frames.len()];
    write!(writer, "{}", terminal_image::kitty_delete(image_id))?;
    write!(
        writer,
        "{}",
        terminal_image::kitty_inline_png_sized(frame, image_id, Some(columns), Some(rows))?
    )?;
    writer.flush()?;
    Ok(())
}

fn apply_action(
    app: &mut BestmanApp,
    catalog: &VesselCatalog,
    ui_state: &mut TuiState,
    action: char,
    forced_dice: Option<u32>,
) -> UiAction {
    match action {
        '[' => {
            ui_state.previous_tab();
        }
        ']' | '\t' => {
            ui_state.next_tab();
        }
        'j' | 'J' => {
            ui_state.move_selection(catalog, 1);
        }
        'k' | 'K' => {
            ui_state.move_selection(catalog, -1);
        }
        'l' | 'L' if ui_state.tab == DashboardTab::Today => {
            return action_notice(
                append_check_in(app, CompletionLevel::Light, forced_dice),
                "Light check-in recorded.",
            );
        }
        'n' | 'N' if ui_state.tab == DashboardTab::Today => {
            return action_notice(
                append_check_in(app, CompletionLevel::Normal, forced_dice),
                "Normal check-in recorded.",
            );
        }
        'f' | 'F' if ui_state.tab == DashboardTab::Today => {
            return action_notice(
                append_check_in(app, CompletionLevel::Full, forced_dice),
                "Full check-in recorded.",
            );
        }
        's' | 'S' if ui_state.tab == DashboardTab::Today => {
            return action_notice(append_skip(app), "Rest recorded.");
        }
        'b' | 'B' if ui_state.tab == DashboardTab::Shop => {
            return action_notice(
                purchase_selected_vessel(app, catalog, ui_state),
                "Ship purchased.",
            );
        }
        'e' | 'E' if ui_state.tab == DashboardTab::Fleet => {
            return action_notice(
                equip_selected_vessel(app, catalog, ui_state),
                "Ship equipped.",
            );
        }
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

fn purchase_selected_vessel(
    app: &mut BestmanApp,
    catalog: &VesselCatalog,
    ui_state: &TuiState,
) -> Result<()> {
    app.rebuild_projection()?;
    let dash = app.projection.dashboard()?;
    let item = selected_shop_item(catalog, ui_state)
        .ok_or_else(|| anyhow::anyhow!("no shop item selected"))?;
    app.store.append(rules::purchase_event(&dash, item)?)?;
    app.rebuild_projection()?;
    Ok(())
}

fn equip_selected_vessel(
    app: &mut BestmanApp,
    catalog: &VesselCatalog,
    ui_state: &TuiState,
) -> Result<()> {
    app.rebuild_projection()?;
    let dash = app.projection.dashboard()?;
    let item = selected_fleet_item(catalog, ui_state)
        .ok_or_else(|| anyhow::anyhow!("no fleet item selected"))?;
    app.store
        .append(rules::equip_vessel_event(&dash, item.id.clone())?)?;
    app.rebuild_projection()?;
    Ok(())
}
