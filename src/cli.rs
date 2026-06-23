use std::path::{Path, PathBuf};

use anyhow::{Result, bail};
use chrono::{Local, NaiveDate};
use clap::{Parser, Subcommand, ValueEnum};
use directories::ProjectDirs;

use crate::app::{AppPaths, BestmanApp};
use crate::config::BestmanConfig;
use crate::events::{CoinAward, CompletionLevel, RecapPeriod};
use crate::llm::{generate_narrative, mock_narrative};
use crate::map::Route;
use crate::rules;
use crate::tui;
use crate::vessels::catalog::{CatalogItemKind, VesselCatalog};

#[derive(Debug, Parser)]
#[command(name = "bestman")]
#[command(about = "Bestman pet-vessel fitness companion")]
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
    Reset {
        #[arg(long)]
        yes: bool,
    },
    Config {
        #[command(subcommand)]
        command: ConfigCommand,
    },
    Rebuild,
    Coins {
        #[command(subcommand)]
        command: CoinsCommand,
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
        #[arg(long)]
        llm: bool,
    },
    Skip {
        #[arg(long, default_value = "需要休整")]
        reason: String,
    },
    Log,
    Talk {
        message: String,
        #[arg(long)]
        llm: bool,
    },
    Weigh {
        weight_kg: f64,
        #[arg(long)]
        note: Option<String>,
    },
    Progress,
    Advice {
        message: String,
        #[arg(long)]
        llm: bool,
    },
    Recap {
        #[arg(long)]
        llm: bool,
        #[arg(long, value_enum, default_value_t = RecapPeriodArg::All)]
        period: RecapPeriodArg,
    },
    Plan {
        #[command(subcommand)]
        command: PlanCommand,
    },
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
    Validate { id: Option<String> },
}

#[derive(Debug, Subcommand)]
enum ShopCommand {
    List,
    Buy { item_id: String },
}

#[derive(Debug, Subcommand)]
enum ConfigCommand {
    Show,
}

#[derive(Debug, Subcommand)]
enum CoinsCommand {
    Grant {
        amount: i32,
        #[arg(long, default_value = "manual grant")]
        reason: String,
    },
}

#[derive(Debug, Subcommand)]
enum PlanCommand {
    Create {
        #[arg(long)]
        goal: String,
        #[arg(long, value_delimiter = ',')]
        tasks: Vec<String>,
    },
    Show,
    SetToday {
        task: String,
        #[arg(long, default_value = "manual adjustment")]
        reason: String,
    },
    Next {
        #[arg(long, default_value = "next planned task")]
        reason: String,
    },
}

#[derive(Debug, Clone, Copy, ValueEnum)]
enum LevelArg {
    Light,
    Normal,
    Full,
}

#[derive(Debug, Clone, Copy, ValueEnum)]
enum RecapPeriodArg {
    Week,
    Month,
    All,
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
            println!("bestman initialized");
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
        Command::Reset { yes } => {
            reset_home(&paths.home, yes)?;
        }
        Command::Config { command } => match command {
            ConfigCommand::Show => {
                let app = BestmanApp::open(paths)?;
                println!("{}", toml::to_string_pretty(&app.config)?.trim_end());
            }
        },
        Command::Rebuild => {
            let mut app = BestmanApp::open(paths)?;
            let events = app.store.read_all()?;
            let count = events.len();
            app.projection.rebuild(events)?;
            let dash = app.projection.dashboard()?;
            println!("projection rebuilt");
            println!("events: {count}");
            println!("position: {}/{}", dash.position, dash.total_days);
            println!("current_vessel: {}", dash.current_vessel);
        }
        Command::Coins { command } => match command {
            CoinsCommand::Grant { amount, reason } => {
                let mut app = BestmanApp::open(paths)?;
                app.store
                    .append(rules::coins_granted_event(today(), amount, reason)?)?;
                app.rebuild_projection()?;
                let dash = app.projection.dashboard()?;
                println!("coins granted: +{amount}");
                println!("coins: {}", dash.coins);
            }
        },
        Command::Done {
            level,
            message,
            dice,
            mock_llm,
            llm,
        } => {
            let mut app = BestmanApp::open(paths)?;
            app.rebuild_projection()?;
            let dash = app.projection.dashboard()?;
            let current_daily_task = dash.daily_task.clone();
            let event =
                rules::check_in_event(&app.config, &dash, today(), level.into(), message, dice)?;
            let feedback = done_feedback(&event.kind);
            let stored = app.store.append(event)?;
            if mock_llm {
                let text = mock_narrative("今天完成训练，请写一段温柔航海日志")?;
                app.store.append(rules::narrative_generated_event(
                    stored.id,
                    text,
                    "mock-llm".to_string(),
                    "mock-v1".to_string(),
                ))?;
            } else if llm || app.config.llm.enabled {
                let prompt = narrative_prompt(&current_daily_task, feedback.level);
                match generate_narrative(&app.config.llm, &prompt) {
                    Ok(generated) => {
                        app.store.append(rules::narrative_generated_event(
                            stored.id,
                            generated.text,
                            generated.model,
                            generated.prompt_version,
                        ))?;
                    }
                    Err(err) => {
                        eprintln!("LLM narrative unavailable; kept template log: {err}");
                    }
                }
            }
            if !feedback.milestones.is_empty() {
                let (text, model, prompt_version) = milestone_epic_text(
                    &app.config.llm,
                    &dash,
                    &feedback,
                    &feedback.milestones,
                    llm || app.config.llm.enabled,
                );
                for milestone in &feedback.milestones {
                    app.store.append(rules::milestone_epic_generated_event(
                        today(),
                        milestone.clone(),
                        text.clone(),
                        model.clone(),
                        prompt_version.clone(),
                    )?)?;
                }
            }
            app.rebuild_projection()?;
            let dash = app.projection.dashboard()?;
            print_done_feedback(&current_daily_task, feedback, &dash);
        }
        Command::Skip { reason } => {
            let mut app = BestmanApp::open(paths)?;
            app.rebuild_projection()?;
            let dash = app.projection.dashboard()?;
            let event = rules::skip_or_rest_event(&app.config, &dash, today(), reason)?;
            let feedback = skip_feedback(&event.kind, dash.mood);
            app.store.append(event)?;
            app.rebuild_projection()?;
            let dash = app.projection.dashboard()?;
            print_skip_feedback(feedback, &dash);
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
        Command::Talk { message, llm } => {
            let mut app = BestmanApp::open(paths)?;
            app.rebuild_projection()?;
            let dash = app.projection.dashboard()?;
            let (text, model, prompt_version) = captain_chat_text(
                &app.config.llm,
                &dash,
                &message,
                llm || app.config.llm.enabled,
            );
            app.store.append(rules::captain_chat_generated_event(
                today(),
                message,
                text.clone(),
                model,
                prompt_version,
            )?)?;
            app.rebuild_projection()?;
            println!("Captain:");
            println!("{text}");
        }
        Command::Weigh { weight_kg, note } => {
            let mut app = BestmanApp::open(paths)?;
            app.store
                .append(rules::weight_recorded_event(today(), weight_kg, note)?)?;
            app.rebuild_projection()?;
            let dash = app.projection.dashboard()?;
            println!("weight recorded: {:.1}kg", weight_kg);
            print_weight_progress(&dash);
        }
        Command::Progress => {
            let mut app = BestmanApp::open(paths)?;
            app.rebuild_projection()?;
            let dash = app.projection.dashboard()?;
            print_weight_progress(&dash);
        }
        Command::Advice { message, llm } => {
            let mut app = BestmanApp::open(paths)?;
            app.rebuild_projection()?;
            let dash = app.projection.dashboard()?;
            let (text, model, prompt_version) = health_advice_text(
                &app.config.llm,
                &dash,
                &message,
                llm || app.config.llm.enabled,
            );
            app.store.append(rules::health_advice_generated_event(
                today(),
                message,
                text.clone(),
                model,
                prompt_version,
            )?)?;
            app.rebuild_projection()?;
            println!("Health Advice:");
            println!("{text}");
        }
        Command::Recap { llm, period } => {
            let mut app = BestmanApp::open(paths)?;
            app.rebuild_projection()?;
            let dash = app.projection.dashboard()?;
            let period: RecapPeriod = period.into();
            let prompt = recap_prompt(&dash, period);
            let (text, model, prompt_version) = if llm || app.config.llm.enabled {
                match generate_narrative(&app.config.llm, &prompt) {
                    Ok(generated) => (generated.text, generated.model, generated.prompt_version),
                    Err(err) => {
                        eprintln!("LLM recap unavailable; generated local recap: {err}");
                        (
                            local_recap(&dash, period),
                            "template".to_string(),
                            recap_prompt_version(period).to_string(),
                        )
                    }
                }
            } else {
                (
                    local_recap(&dash, period),
                    "template".to_string(),
                    recap_prompt_version(period).to_string(),
                )
            };
            app.store.append(rules::recap_generated_event(
                today(),
                period,
                text.clone(),
                model,
                prompt_version,
            )?)?;
            app.rebuild_projection()?;
            println!("{text}");
        }
        Command::Plan { command } => {
            let mut app = BestmanApp::open(paths)?;
            app.rebuild_projection()?;
            match command {
                PlanCommand::Create { goal, tasks } => {
                    app.store
                        .append(rules::plan_created_event(today(), goal, tasks)?)?;
                    app.rebuild_projection()?;
                    let dash = app.projection.dashboard()?;
                    println!("plan created");
                    println!("goal: {}", dash.plan_goal.unwrap_or_default());
                    println!("today: {}", dash.daily_task);
                }
                PlanCommand::Show => {
                    let dash = app.projection.dashboard()?;
                    println!(
                        "goal: {}",
                        dash.plan_goal
                            .clone()
                            .unwrap_or_else(|| "no plan".to_string())
                    );
                    println!("today: {}", dash.daily_task);
                    if !dash.plan_tasks.is_empty() {
                        println!("tasks:");
                        for task in dash.plan_tasks {
                            println!("- {task}");
                        }
                    }
                }
                PlanCommand::SetToday { task, reason } => {
                    app.store
                        .append(rules::plan_adjusted_event(today(), task, reason)?)?;
                    app.rebuild_projection()?;
                    let dash = app.projection.dashboard()?;
                    println!("today: {}", dash.daily_task);
                }
                PlanCommand::Next { reason } => {
                    let dash = app.projection.dashboard()?;
                    let task = next_plan_task(&dash)?;
                    app.store
                        .append(rules::plan_adjusted_event(today(), task, reason)?)?;
                    app.rebuild_projection()?;
                    let dash = app.projection.dashboard()?;
                    println!("today: {}", dash.daily_task);
                }
            }
        }
        Command::Vessel { command } => {
            let mut app = BestmanApp::open(paths)?;
            match command {
                VesselCommand::List => {
                    let catalog =
                        VesselCatalog::load_with_user_dir(&app.paths.home.join("vessels"))?;
                    app.rebuild_projection()?;
                    let dash = app.projection.dashboard()?;
                    for item in catalog.vessel_items() {
                        let owned = dash.owned_vessels.iter().any(|id| id == &item.id);
                        let equipped = dash.current_vessel == item.id;
                        let name = catalog
                            .find(&item.id)
                            .map(|vessel| vessel.display_name.as_str())
                            .unwrap_or(item.id.as_str());
                        println!(
                            "{} {} - {} [{}] price={} rarity={}",
                            if equipped {
                                "*"
                            } else if owned {
                                "+"
                            } else {
                                "-"
                            },
                            item.id,
                            name,
                            if equipped {
                                "equipped"
                            } else if owned {
                                "owned"
                            } else {
                                "locked"
                            },
                            item.price,
                            item.rarity
                        );
                    }
                }
                VesselCommand::Set { id } => {
                    let catalog =
                        VesselCatalog::load_with_user_dir(&app.paths.home.join("vessels"))?;
                    if catalog.find(&id).is_none() {
                        bail!("unknown vessel {id}");
                    }
                    app.rebuild_projection()?;
                    let dash = app.projection.dashboard()?;
                    app.store.append(rules::equip_vessel_event(&dash, id)?)?;
                    app.rebuild_projection()?;
                    println!("vessel equipped");
                }
                VesselCommand::Validate { id } => {
                    let catalog =
                        VesselCatalog::load_with_user_dir(&app.paths.home.join("vessels"))?;
                    let count = validate_vessels(&app, &catalog, id.as_deref())?;
                    println!("validated {count} vessel(s)");
                }
            }
        }
        Command::Shop { command } => {
            let mut app = BestmanApp::open(paths)?;
            app.rebuild_projection()?;
            let dash = app.projection.dashboard()?;
            match command {
                ShopCommand::List => {
                    let catalog =
                        VesselCatalog::load_with_user_dir(&app.paths.home.join("vessels"))?;
                    for item in catalog.vessel_items() {
                        let owned = dash.owned_items.iter().any(|id| id == &item.id);
                        println!(
                            "{} - kind={} rarity={} price={} {}",
                            item.id,
                            catalog_kind_label(item.kind.clone()),
                            item.rarity,
                            item.price,
                            if owned { "owned" } else { "available" }
                        );
                    }
                }
                ShopCommand::Buy { item_id } => {
                    let catalog =
                        VesselCatalog::load_with_user_dir(&app.paths.home.join("vessels"))?;
                    let item = catalog
                        .find_item(&item_id)
                        .ok_or_else(|| anyhow::anyhow!("unknown shop item {item_id}"))?;
                    if item.kind != CatalogItemKind::Vessel {
                        bail!("only vessel items can be bought in v1.2");
                    }
                    app.store.append(rules::purchase_event(&dash, item)?)?;
                    app.rebuild_projection()?;
                    println!("purchased {item_id}");
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

fn reset_home(home: &Path, yes: bool) -> Result<()> {
    if !yes {
        bail!(
            "reset deletes all bestman data under {}. Re-run with --yes to confirm.",
            home.display()
        );
    }
    if home.parent().is_none() {
        bail!("refusing to reset filesystem root");
    }
    if home.exists() {
        std::fs::remove_dir_all(home)?;
    }
    println!("bestman data reset: {}", home.display());
    Ok(())
}

fn next_plan_task(dash: &crate::projection::Dashboard) -> Result<String> {
    if dash.plan_tasks.is_empty() {
        bail!("no plan tasks available; run plan create first");
    }
    let next = dash
        .plan_tasks
        .iter()
        .position(|task| task == &dash.daily_task)
        .map(|idx| (idx + 1) % dash.plan_tasks.len())
        .unwrap_or(0);
    Ok(dash.plan_tasks[next].clone())
}

fn validate_vessels(app: &BestmanApp, catalog: &VesselCatalog, id: Option<&str>) -> Result<usize> {
    let manifests = match id {
        Some(id) => vec![
            catalog
                .find(id)
                .ok_or_else(|| anyhow::anyhow!("unknown vessel {id}"))?,
        ],
        None => catalog.vessels.iter().collect::<Vec<_>>(),
    };
    let output_dir = app.paths.cache.join("vessel-validation");
    for manifest in &manifests {
        let output = output_dir.join(format!("{}-idle.png", manifest.id));
        crate::vessels::render::render_preview(manifest, "idle", &output)?;
        println!("{} ok {}", manifest.id, output.display());
    }
    Ok(manifests.len())
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
    if let Some(weight) = &dash.latest_weight {
        println!("weight: {:.1}kg ({})", weight.weight_kg, weight.date);
    }
}

fn status_json(dash: &crate::projection::Dashboard) -> serde_json::Value {
    let latest_weight = dash.latest_weight.as_ref().map(|weight| {
        serde_json::json!({
            "date": weight.date.to_string(),
            "weight_kg": weight.weight_kg,
            "note": weight.note.as_ref(),
        })
    });
    let recent_weights = dash
        .recent_weights
        .iter()
        .map(|weight| {
            serde_json::json!({
                "date": weight.date.to_string(),
                "weight_kg": weight.weight_kg,
                "note": weight.note.as_ref(),
            })
        })
        .collect::<Vec<_>>();
    serde_json::json!({
        "initialized": dash.initialized,
        "daily_task": dash.daily_task,
        "plan_goal": dash.plan_goal,
        "plan_tasks": dash.plan_tasks,
        "position": dash.position,
        "total_days": dash.total_days,
        "coins": dash.coins,
        "trust": dash.trust,
        "mood": dash.mood,
        "streak": dash.streak,
        "current_vessel": dash.current_vessel,
        "owned_items": dash.owned_items,
        "owned_vessels": dash.owned_vessels,
        "animation": format!("{:?}", dash.animation),
        "last_action_date": dash.last_action_date.map(|date| date.to_string()),
        "last_action_kind": dash.last_action_kind,
        "latest_log": dash.latest_log,
        "latest_weight": latest_weight,
        "recent_weights": recent_weights,
    })
}

fn print_weight_progress(dash: &crate::projection::Dashboard) {
    if dash.recent_weights.is_empty() {
        println!("no weight records yet");
        println!("Use `bestman weigh <kg>` to add one.");
        return;
    }
    println!("Weight Progress");
    if let Some(latest) = &dash.latest_weight {
        println!("latest: {:.1}kg ({})", latest.weight_kg, latest.date);
    }
    if let Some(summary) = weight_trend_summary(&dash.recent_weights) {
        println!("trend: {summary}");
    }
    println!("recent:");
    for record in &dash.recent_weights {
        if let Some(note) = &record.note {
            println!("- {} {:.1}kg - {}", record.date, record.weight_kg, note);
        } else {
            println!("- {} {:.1}kg", record.date, record.weight_kg);
        }
    }
}

fn weight_trend_summary(weights: &[crate::projection::WeightRecord]) -> Option<String> {
    let latest = weights.first()?;
    let oldest = weights.last()?;
    if weights.len() < 2 {
        return Some("first record; keep the trend gentle and long-term".to_string());
    }
    let delta = latest.weight_kg - oldest.weight_kg;
    if delta.abs() < 0.05 {
        Some("stable across recent records".to_string())
    } else if delta < 0.0 {
        Some(format!("{:.1}kg lower across recent records", delta.abs()))
    } else {
        Some(format!("{:.1}kg higher across recent records", delta))
    }
}

#[derive(Debug)]
struct DoneFeedback {
    level: CompletionLevel,
    old_position: u32,
    new_position: u32,
    dice_distance: u32,
    coins_breakdown: Vec<CoinAward>,
    trust_delta: i32,
    mood_delta: i32,
    milestones: Vec<String>,
    treasures: Vec<String>,
}

#[derive(Debug)]
struct SkipFeedback {
    kind: &'static str,
    mood_delta: i32,
    mood_before: i32,
    animation: crate::events::VesselAnimation,
}

fn done_feedback(kind: &crate::events::EventKind) -> DoneFeedback {
    let crate::events::EventKind::DailyCheckInCompleted {
        level,
        old_position,
        new_position,
        dice_distance,
        coins_breakdown,
        trust_delta,
        mood_delta,
        milestones,
        treasures,
        ..
    } = kind
    else {
        unreachable!("done feedback is only built from check-in events");
    };
    DoneFeedback {
        level: *level,
        old_position: *old_position,
        new_position: *new_position,
        dice_distance: *dice_distance,
        coins_breakdown: coins_breakdown.clone(),
        trust_delta: *trust_delta,
        mood_delta: *mood_delta,
        milestones: milestones.clone(),
        treasures: treasures.clone(),
    }
}

fn skip_feedback(kind: &crate::events::EventKind, mood_before: i32) -> SkipFeedback {
    match kind {
        crate::events::EventKind::DaySkipped {
            mood_delta,
            animation,
            ..
        } => SkipFeedback {
            kind: "rest/skip",
            mood_delta: *mood_delta,
            mood_before,
            animation: *animation,
        },
        crate::events::EventKind::RestDayObserved { animation, .. } => SkipFeedback {
            kind: "planned rest",
            mood_delta: 0,
            mood_before,
            animation: *animation,
        },
        _ => unreachable!("skip feedback is only built from rest/skip events"),
    }
}

fn print_done_feedback(
    daily_task: &str,
    feedback: DoneFeedback,
    dash: &crate::projection::Dashboard,
) {
    let coins: i32 = feedback
        .coins_breakdown
        .iter()
        .map(|award| award.amount)
        .sum();
    println!("Check-in recorded");
    println!("task: {daily_task}");
    println!("level: {}", level_label(feedback.level));
    println!(
        "voyage: {} -> {} (+{} days)",
        feedback.old_position, feedback.new_position, feedback.dice_distance
    );
    println!("coins: +{coins} (total {})", dash.coins);
    println!(
        "mood: {:+} -> {}    trust: {:+} -> {}",
        feedback.mood_delta, dash.mood, feedback.trust_delta, dash.trust
    );
    if !feedback.milestones.is_empty() {
        println!("milestones: {}", feedback.milestones.join(", "));
    }
    if !feedback.treasures.is_empty() {
        println!("treasures: {}", feedback.treasures.join(", "));
    }
    if let Some(log) = &dash.latest_log {
        println!("log: {log}");
    }
}

fn print_skip_feedback(feedback: SkipFeedback, dash: &crate::projection::Dashboard) {
    println!("Rest recorded");
    println!("type: {}", feedback.kind);
    println!("vessel state: {}", animation_label(feedback.animation));
    println!(
        "mood: {:+} ({} -> {})",
        feedback.mood_delta, feedback.mood_before, dash.mood
    );
    println!("streak: {}", dash.streak);
    if let Some(log) = &dash.latest_log {
        println!("log: {log}");
    }
}

fn level_label(level: CompletionLevel) -> &'static str {
    match level {
        CompletionLevel::Light => "light",
        CompletionLevel::Normal => "normal",
        CompletionLevel::Full => "full",
    }
}

fn animation_label(animation: crate::events::VesselAnimation) -> &'static str {
    match animation {
        crate::events::VesselAnimation::Idle => "idle",
        crate::events::VesselAnimation::Waiting => "waiting",
        crate::events::VesselAnimation::Sailing => "sailing",
        crate::events::VesselAnimation::Happy => "happy",
        crate::events::VesselAnimation::Resting => "resting",
        crate::events::VesselAnimation::Celebrating => "celebrating",
        crate::events::VesselAnimation::Treasure => "treasure",
        crate::events::VesselAnimation::LowEnergy => "low_energy",
    }
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

impl From<RecapPeriodArg> for RecapPeriod {
    fn from(value: RecapPeriodArg) -> Self {
        match value {
            RecapPeriodArg::Week => RecapPeriod::Week,
            RecapPeriodArg::Month => RecapPeriod::Month,
            RecapPeriodArg::All => RecapPeriod::All,
        }
    }
}

fn narrative_prompt(daily_task: &str, level: CompletionLevel) -> String {
    format!(
        "今日任务：{daily_task}\n完成级别：{}\n请写一段 1-2 句温柔的宠物船航海日志。不要提及或修改金币、位置、心情、信任等规则状态。",
        level_label(level)
    )
}

fn recap_prompt(dash: &crate::projection::Dashboard, period: RecapPeriod) -> String {
    format!(
        "请写一段 3-4 句 bestman 宠物船{}回顾。事实：已完成 {} 天，当前位置 {}/{}，当前船 {}，拥有船只 {} 艘，金币 {}，心情 {}，信任 {}，当前计划目标 {}。只写叙事，不修改任何状态。",
        recap_period_label(period),
        dash.completed_days,
        dash.position,
        dash.total_days,
        dash.current_vessel,
        dash.owned_vessels.len(),
        dash.coins,
        dash.mood,
        dash.trust,
        dash.plan_goal.as_deref().unwrap_or("未设置")
    )
}

fn local_recap(dash: &crate::projection::Dashboard, period: RecapPeriod) -> String {
    format!(
        "Recap ({})：小船已经陪你完成 {} 天，航线推进到 {}/{}。当前船只是 {}，船坞里已有 {} 艘船。今天不需要夸张的史诗，只要把下一次训练稳稳接上。",
        recap_period_label(period),
        dash.completed_days,
        dash.position,
        dash.total_days,
        dash.current_vessel,
        dash.owned_vessels.len()
    )
}

fn recap_period_label(period: RecapPeriod) -> &'static str {
    match period {
        RecapPeriod::Week => "week",
        RecapPeriod::Month => "month",
        RecapPeriod::All => "all-time",
    }
}

fn recap_prompt_version(period: RecapPeriod) -> &'static str {
    match period {
        RecapPeriod::Week => "bestman-v3-weekly-recap-template",
        RecapPeriod::Month => "bestman-v3-monthly-recap-template",
        RecapPeriod::All => "bestman-v3-recap-template",
    }
}

fn milestone_epic_text(
    llm_config: &crate::config::LlmConfig,
    dash: &crate::projection::Dashboard,
    feedback: &DoneFeedback,
    milestones: &[String],
    use_llm: bool,
) -> (String, String, String) {
    let prompt = milestone_epic_prompt(dash, feedback, milestones);
    if use_llm {
        match generate_narrative(llm_config, &prompt) {
            Ok(generated) => {
                return (generated.text, generated.model, generated.prompt_version);
            }
            Err(err) => {
                eprintln!("LLM milestone epic unavailable; generated local epic: {err}");
            }
        }
    }
    (
        local_milestone_epic(dash, feedback, milestones),
        "template".to_string(),
        "bestman-v3-milestone-template".to_string(),
    )
}

fn milestone_epic_prompt(
    dash: &crate::projection::Dashboard,
    feedback: &DoneFeedback,
    milestones: &[String],
) -> String {
    let coins_total = dash.coins
        + feedback
            .coins_breakdown
            .iter()
            .map(|award| award.amount)
            .sum::<i32>();
    format!(
        "请写一段 3 句以内的 bestman 宠物船里程碑史诗。事实：抵达里程碑 {}，当前位置 {}/{}，累计完成 {} 天，最长/当前连续 {} 天，当前船 {}，拥有船只 {} 艘，金币 {}。只写叙事，不修改任何状态。",
        milestones.join("、"),
        feedback.new_position,
        dash.total_days,
        dash.completed_days.saturating_add(1),
        dash.streak.saturating_add(1),
        dash.current_vessel,
        dash.owned_vessels.len(),
        coins_total
    )
}

fn local_milestone_epic(
    dash: &crate::projection::Dashboard,
    feedback: &DoneFeedback,
    milestones: &[String],
) -> String {
    format!(
        "Milestone Epic: {} 被写入航海志。{} 已航行到 {}/{}，完成 {} 天训练；这不是新的负担，只是一枚证明你已经走到这里的航标。",
        milestones.join("、"),
        dash.current_vessel,
        feedback.new_position,
        dash.total_days,
        dash.completed_days.saturating_add(1)
    )
}

fn captain_chat_text(
    llm_config: &crate::config::LlmConfig,
    dash: &crate::projection::Dashboard,
    message: &str,
    use_llm: bool,
) -> (String, String, String) {
    let prompt = captain_chat_prompt(dash, message);
    if use_llm {
        match generate_narrative(llm_config, &prompt) {
            Ok(generated) => {
                return (generated.text, generated.model, generated.prompt_version);
            }
            Err(err) => {
                eprintln!("LLM captain chat unavailable; generated local reply: {err}");
            }
        }
    }
    (
        local_captain_chat(dash, message),
        "template".to_string(),
        "bestman-v3-captain-chat-template".to_string(),
    )
}

fn captain_chat_prompt(dash: &crate::projection::Dashboard, message: &str) -> String {
    format!(
        "你是 bestman 宠物船的船长。用户说：{message}\n当前事实：今日任务 {}，位置 {}/{}，连续 {} 天，金币 {}，心情 {}，信任 {}，当前船 {}，计划目标 {}。\n请用 1-3 句中文回答，温和、具体、不过度鸡血。只能聊天和建议，不要修改或承诺修改金币、位置、心情、信任、船只、计划或任务。",
        dash.daily_task,
        dash.position,
        dash.total_days,
        dash.streak,
        dash.coins,
        dash.mood,
        dash.trust,
        dash.current_vessel,
        dash.plan_goal.as_deref().unwrap_or("未设置")
    )
}

fn local_captain_chat(dash: &crate::projection::Dashboard, message: &str) -> String {
    let lowered = message.to_lowercase();
    if dash.last_action_date == Some(today()) {
        return format!(
            "今天已经记录过了。船长建议你把训练停在这里，最多做 5 分钟拉伸；{} 会在港口把灯留着。",
            dash.current_vessel
        );
    }
    if lowered.contains("累") || lowered.contains("tired") || lowered.contains("疲") {
        return format!(
            "可以把今天降到轻量版：{}。船长不会催你加量，先把节奏接住。",
            dash.daily_task
        );
    }
    format!(
        "船长看了今天的任务：{}。先做最小可完成的一组，完成后再决定要不要继续。",
        dash.daily_task
    )
}

fn health_advice_text(
    llm_config: &crate::config::LlmConfig,
    dash: &crate::projection::Dashboard,
    message: &str,
    use_llm: bool,
) -> (String, String, String) {
    let prompt = health_advice_prompt(dash, message);
    if use_llm {
        match generate_narrative(llm_config, &prompt) {
            Ok(generated) => {
                return (generated.text, generated.model, generated.prompt_version);
            }
            Err(err) => {
                eprintln!("LLM health advice unavailable; generated local advice: {err}");
            }
        }
    }
    (
        local_health_advice(dash, message),
        "template".to_string(),
        "bestman-v3-health-advice-template".to_string(),
    )
}

fn health_advice_prompt(dash: &crate::projection::Dashboard, message: &str) -> String {
    let weight = dash
        .latest_weight
        .as_ref()
        .map(|record| format!("{:.1}kg on {}", record.weight_kg, record.date))
        .unwrap_or_else(|| "未记录".to_string());
    let trend = weight_trend_summary(&dash.recent_weights).unwrap_or_else(|| "未记录".to_string());
    format!(
        "你是 bestman 的低风险健康建议助手。用户说：{message}\n事实：今日任务 {}，连续 {} 天，心情 {}，最新体重 {}，近期趋势 {}。\n请用 2-4 句中文给温和、具体、低风险建议。不要诊断，不要承诺治疗，不要给极端节食或高风险医疗建议；如果提到严重疼痛、胸痛、晕厥、麻木或受伤加重，明确建议停止训练并寻求专业帮助。只能建议，不修改计划、金币、位置、心情、信任或体重。",
        dash.daily_task, dash.streak, dash.mood, weight, trend
    )
}

fn local_health_advice(dash: &crate::projection::Dashboard, message: &str) -> String {
    let lowered = message.to_lowercase();
    let needs_professional_help = [
        "严重疼",
        "胸痛",
        "晕",
        "麻",
        "受伤",
        "sharp pain",
        "chest pain",
        "dizzy",
        "numb",
        "injury",
    ]
    .iter()
    .any(|needle| lowered.contains(needle));
    if needs_professional_help {
        return "先停止今天的训练，不要硬撑。若有严重疼痛、胸痛、头晕、麻木或伤势加重，请尽快寻求专业医疗帮助；今天最多只保留轻柔活动或休息。".to_string();
    }

    if lowered.contains("膝") || lowered.contains("knee") {
        return "今天先避开跳跃、冲刺和深蹲到底，改成低冲击版本：快走、髋桥或轻量拉伸。若膝盖疼痛持续或加重，停止训练并找专业人士评估。".to_string();
    }

    if lowered.contains("累")
        || lowered.contains("疲")
        || lowered.contains("tired")
        || lowered.contains("fatigue")
    {
        return format!(
            "把今天降到轻量版就够了：{}。目标是保住节奏，不是证明强度；睡眠和恢复比额外加量更重要。",
            dash.daily_task
        );
    }

    if let Some(trend) = weight_trend_summary(&dash.recent_weights) {
        return format!(
            "按当前记录看，{}。继续看 2-4 周趋势，不要被单日波动牵着走；今天先完成可持续的一小组。",
            trend
        );
    }

    "先从最小可完成版本开始：热身 5 分钟，再做一组今天任务。任何不适都可以降强度或休息，严重疼痛请找专业人士。".to_string()
}

fn catalog_kind_label(kind: CatalogItemKind) -> &'static str {
    match kind {
        CatalogItemKind::Vessel => "vessel",
        CatalogItemKind::Skin => "skin",
        CatalogItemKind::Decoration => "decoration",
        CatalogItemKind::Animation => "animation",
    }
}
