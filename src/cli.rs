use std::path::PathBuf;

use anyhow::{Result, bail};
use chrono::{Local, NaiveDate};
use clap::{Parser, Subcommand, ValueEnum};
use directories::ProjectDirs;

use crate::app::{AppPaths, BestmanApp};
use crate::config::BestmanConfig;
use crate::events::CompletionLevel;
use crate::llm::mock_narrative;
use crate::map::Route;
use crate::rules;
use crate::tui;
use crate::vessels::catalog::VesselCatalog;

#[derive(Debug, Parser)]
#[command(name = "bestman-rs")]
#[command(about = "bestman Rust pet-vessel prototype")]
pub struct Cli {
    #[arg(long, env = "BESTMAN_HOME")]
    home: Option<PathBuf>,
    #[command(subcommand)]
    command: Option<Command>,
}

#[derive(Debug, Subcommand)]
enum Command {
    Init {
        #[arg(long, default_value = "深蹲 3x15 + 平板支撑 3x30s")]
        daily_task: String,
        #[arg(long, default_value_t = 120)]
        total_days: u32,
    },
    Status {
        #[arg(long)]
        json: bool,
    },
    Done {
        #[arg(long, value_enum, default_value_t = LevelArg::Normal)]
        level: LevelArg,
        #[arg(short, long, default_value = "")]
        message: String,
        #[arg(long)]
        dice: Option<u32>,
        #[arg(long)]
        mock_llm: bool,
    },
    Skip {
        #[arg(long, default_value = "需要休整")]
        reason: String,
    },
    Log,
    Vessel {
        #[command(subcommand)]
        command: VesselCommand,
    },
    Shop {
        #[command(subcommand)]
        command: ShopCommand,
    },
    Tui {
        #[arg(long)]
        live: bool,
        #[arg(long)]
        ticks: Option<u16>,
        #[arg(long, default_value_t = 120)]
        tick_ms: u64,
        #[arg(long)]
        no_alt_screen: bool,
        #[arg(long)]
        no_raw_mode: bool,
        #[arg(long)]
        script: Option<String>,
        #[arg(long)]
        dice: Option<u32>,
        #[arg(long)]
        images: bool,
        #[arg(long)]
        force_kitty_images: bool,
        #[arg(long, default_value_t = 9001)]
        image_id: u32,
    },
    DashboardImage {
        #[arg(long)]
        output: PathBuf,
    },
    DashboardFrames {
        #[arg(long)]
        output_dir: PathBuf,
    },
    ImageProtocol {
        #[arg(long)]
        kitty_inline: Option<PathBuf>,
    },
    Preview {
        #[arg(long, default_value = "starter_sloop")]
        vessel: String,
        #[arg(long, default_value = "idle")]
        animation: String,
        #[arg(long)]
        output: PathBuf,
    },
    AnimationFrames {
        #[arg(long, default_value = "starter_sloop")]
        vessel: String,
        #[arg(long, default_value = "idle")]
        animation: String,
        #[arg(long)]
        output_dir: PathBuf,
    },
}

#[derive(Debug, Subcommand)]
enum VesselCommand {
    List,
    Set { id: String },
}

#[derive(Debug, Subcommand)]
enum ShopCommand {
    Buy { item_id: String },
}

#[derive(Debug, Clone, Copy, ValueEnum)]
enum LevelArg {
    Light,
    Normal,
    Full,
}

pub fn run() -> Result<()> {
    let cli = Cli::parse();
    let paths = AppPaths::from_home(resolve_home(cli.home)?);
    let command = cli.command.unwrap_or(Command::Status { json: false });
    match command {
        Command::Init {
            daily_task,
            total_days,
        } => {
            let mut config = BestmanConfig::default();
            config.voyage.daily_task = daily_task;
            config.voyage.total_days = total_days;
            config.save(&paths.config)?;
            let mut app = BestmanApp::open(paths)?;
            let event = rules::init_event(&app.config, today());
            app.store.append(event)?;
            app.rebuild_projection()?;
            println!("bestman-rs initialized");
        }
        Command::Status { json } => {
            let mut app = BestmanApp::open(paths)?;
            app.rebuild_projection()?;
            let dash = app.projection.dashboard()?;
            if json {
                println!("{}", serde_json::to_string_pretty(&status_json(&dash))?);
            } else {
                print_dashboard(&app, &dash);
            }
        }
        Command::Done {
            level,
            message,
            dice,
            mock_llm,
        } => {
            let mut app = BestmanApp::open(paths)?;
            app.rebuild_projection()?;
            let dash = app.projection.dashboard()?;
            let event =
                rules::check_in_event(&app.config, &dash, today(), level.into(), message, dice)?;
            let stored = app.store.append(event)?;
            if mock_llm {
                let text = mock_narrative("今天完成训练，请写一段温柔航海日志")?;
                app.store.append(rules::narrative_generated_event(
                    stored.id,
                    text,
                    "mock-llm".to_string(),
                ))?;
            }
            app.rebuild_projection()?;
            let dash = app.projection.dashboard()?;
            println!("done: position {} coins {}", dash.position, dash.coins);
        }
        Command::Skip { reason } => {
            let mut app = BestmanApp::open(paths)?;
            app.rebuild_projection()?;
            let dash = app.projection.dashboard()?;
            let event = rules::skip_or_rest_event(&app.config, &dash, today(), reason)?;
            app.store.append(event)?;
            app.rebuild_projection()?;
            println!("resting");
        }
        Command::Log => {
            let mut app = BestmanApp::open(paths)?;
            app.rebuild_projection()?;
            let dash = app.projection.dashboard()?;
            println!(
                "{}",
                dash.latest_log.unwrap_or_else(|| "no logs".to_string())
            );
        }
        Command::Vessel { command } => {
            let mut app = BestmanApp::open(paths)?;
            match command {
                VesselCommand::List => {
                    let catalog =
                        VesselCatalog::load_with_user_dir(&app.paths.home.join("vessels"))?;
                    for vessel in catalog.vessels {
                        println!("{} - {}", vessel.id, vessel.display_name);
                    }
                }
                VesselCommand::Set { id } => {
                    let catalog =
                        VesselCatalog::load_with_user_dir(&app.paths.home.join("vessels"))?;
                    if catalog.find(&id).is_none() {
                        bail!("unknown vessel {id}");
                    }
                    app.store.append(rules::change_vessel_event(id))?;
                    app.rebuild_projection()?;
                    println!("vessel changed");
                }
            }
        }
        Command::Shop { command } => {
            let mut app = BestmanApp::open(paths)?;
            app.rebuild_projection()?;
            let dash = app.projection.dashboard()?;
            match command {
                ShopCommand::Buy { item_id } => {
                    let cost = shop_cost(&item_id)?;
                    app.store
                        .append(rules::purchase_event(&dash, item_id, cost)?)?;
                    app.rebuild_projection()?;
                    println!("purchased");
                }
            }
        }
        Command::Tui {
            live,
            ticks,
            tick_ms,
            no_alt_screen,
            no_raw_mode,
            script,
            dice,
            images,
            force_kitty_images,
            image_id,
        } => {
            let mut app = BestmanApp::open(paths)?;
            app.rebuild_projection()?;
            if live {
                tui::run_live_dashboard(
                    &mut app,
                    tui::LiveTuiOptions {
                        ticks,
                        tick_ms,
                        alt_screen: !no_alt_screen,
                        raw_mode: !no_raw_mode,
                        script,
                        forced_dice: dice,
                        images,
                        force_kitty_images,
                        image_id,
                    },
                )?;
                if let Some(ticks) = ticks {
                    println!("live_tui_completed ticks={ticks}");
                } else {
                    println!("live_tui_completed");
                }
            } else {
                tui::render_static_dashboard(&app)?;
            }
        }
        Command::DashboardImage { output } => {
            let mut app = BestmanApp::open(paths)?;
            app.rebuild_projection()?;
            crate::dashboard::export_dashboard_png(&app, &output)?;
            println!("{}", output.display());
        }
        Command::DashboardFrames { output_dir } => {
            let mut app = BestmanApp::open(paths)?;
            app.rebuild_projection()?;
            let frames = crate::dashboard::export_dashboard_frames(&app, &output_dir)?;
            for frame in frames {
                println!("{}", frame.display());
            }
        }
        Command::ImageProtocol { kitty_inline } => {
            println!("{:?}", crate::terminal_image::detect_current());
            if let Some(path) = kitty_inline {
                let seq = crate::terminal_image::kitty_inline_png(&path, 9001)?;
                let delete = crate::terminal_image::kitty_delete(9001);
                println!("kitty_inline_bytes={}", seq.len());
                println!("kitty_delete_bytes={}", delete.len());
            }
        }
        Command::Preview {
            vessel,
            animation,
            output,
        } => {
            let app = BestmanApp::open(paths)?;
            let catalog = VesselCatalog::load_with_user_dir(&app.paths.home.join("vessels"))?;
            let manifest = catalog
                .find(&vessel)
                .ok_or_else(|| anyhow::anyhow!("unknown vessel {vessel}"))?;
            crate::vessels::render::render_preview(manifest, &animation, &output)?;
            println!("{}", output.display());
        }
        Command::AnimationFrames {
            vessel,
            animation,
            output_dir,
        } => {
            let app = BestmanApp::open(paths)?;
            let catalog = VesselCatalog::load_with_user_dir(&app.paths.home.join("vessels"))?;
            let manifest = catalog
                .find(&vessel)
                .ok_or_else(|| anyhow::anyhow!("unknown vessel {vessel}"))?;
            let frames =
                crate::vessels::render::export_animation_frames(manifest, &animation, &output_dir)?;
            for frame in frames {
                println!("{}", frame.display());
            }
        }
    }
    Ok(())
}

fn resolve_home(home: Option<PathBuf>) -> Result<PathBuf> {
    if let Some(home) = home {
        return Ok(home);
    }
    if let Some(project) = ProjectDirs::from("dev", "bestman", "bestman-rs") {
        return Ok(project.data_dir().to_path_buf());
    }
    bail!("could not resolve data dir")
}

fn today() -> NaiveDate {
    Local::now().date_naive()
}

fn print_dashboard(app: &BestmanApp, dash: &crate::projection::Dashboard) {
    println!("bestman-rs");
    println!("position: {}/{}", dash.position, dash.total_days);
    println!(
        "coins: {} trust: {} mood: {} streak: {}",
        dash.coins, dash.trust, dash.mood, dash.streak
    );
    println!(
        "vessel: {} animation: {:?}",
        dash.current_vessel, dash.animation
    );
    println!("data: {}", app.paths.home.display());
    println!(
        "{}",
        Route::generate(dash.total_days).render_ascii(dash.position)
    );
    if let Some(log) = &dash.latest_log {
        println!("log: {log}");
    }
}

fn status_json(dash: &crate::projection::Dashboard) -> serde_json::Value {
    serde_json::json!({
        "initialized": dash.initialized,
        "position": dash.position,
        "total_days": dash.total_days,
        "coins": dash.coins,
        "trust": dash.trust,
        "mood": dash.mood,
        "streak": dash.streak,
        "current_vessel": dash.current_vessel,
        "animation": format!("{:?}", dash.animation),
        "latest_log": dash.latest_log,
    })
}

fn shop_cost(item_id: &str) -> Result<i32> {
    Ok(match item_id {
        "blue_sail" => 20,
        "warm_lantern" => 30,
        "idle_bobble" => 40,
        other => bail!("unknown shop item {other}"),
    })
}

impl From<LevelArg> for CompletionLevel {
    fn from(value: LevelArg) -> Self {
        match value {
            LevelArg::Light => CompletionLevel::Light,
            LevelArg::Normal => CompletionLevel::Normal,
            LevelArg::Full => CompletionLevel::Full,
        }
    }
}
