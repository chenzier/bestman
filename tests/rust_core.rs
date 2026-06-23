use chrono::NaiveDate;
use image::GenericImageView;
use tempfile::tempdir;

use bestman_rs::app::{AppPaths, BestmanApp};
use bestman_rs::config::BestmanConfig;
use bestman_rs::dashboard::{
    build_dashboard_render, export_dashboard_frames, export_dashboard_png,
};
use bestman_rs::events::{CompletionLevel, EventKind, VesselAnimation};
use bestman_rs::llm::{build_openai_chat_request, parse_openai_chat_response};
use bestman_rs::projection::Projection;
use bestman_rs::rules;
use bestman_rs::terminal_image::{
    ImageProtocol, detect_from_env, kitty_delete, kitty_inline_png, kitty_inline_png_sized,
};
use bestman_rs::vessels::catalog::VesselCatalog;
use bestman_rs::vessels::manifest::VesselManifest;
use bestman_rs::vessels::render::{FrameCache, export_animation_frames, render_preview};

#[test]
fn event_replay_rebuilds_projection() {
    let dir = tempdir().unwrap();
    let paths = AppPaths::from_home(dir.path().join("home"));
    let config = BestmanConfig::default();
    config.save(&paths.config).unwrap();
    let mut app = BestmanApp::open(paths).unwrap();
    app.store
        .append(rules::init_event(
            &config,
            NaiveDate::from_ymd_opt(2026, 6, 22).unwrap(),
        ))
        .unwrap();
    app.rebuild_projection().unwrap();
    let dash = app.projection.dashboard().unwrap();
    let event = rules::check_in_event(
        &config,
        &dash,
        NaiveDate::from_ymd_opt(2026, 6, 23).unwrap(),
        CompletionLevel::Full,
        "完成全套".to_string(),
        Some(3),
    )
    .unwrap();
    app.store.append(event).unwrap();
    app.rebuild_projection().unwrap();

    let before = app.projection.dashboard().unwrap();
    assert_eq!(before.daily_task, config.voyage.daily_task);
    assert_eq!(before.position, 3);
    assert_eq!(before.completed_days, 1);
    assert_eq!(before.coins, 12);
    assert_eq!(before.trust, 23);
    assert_eq!(before.animation, VesselAnimation::Sailing);
    assert_eq!(
        before.last_action_date,
        Some(NaiveDate::from_ymd_opt(2026, 6, 23).unwrap())
    );
    assert_eq!(before.last_action_kind.as_deref(), Some("check_in"));

    std::fs::remove_file(&app.paths.db).unwrap();
    let events = app.store.read_all().unwrap();
    let mut rebuilt = Projection::open(&app.paths.db).unwrap();
    rebuilt.rebuild(events).unwrap();
    assert_eq!(rebuilt.dashboard().unwrap(), before);
}

#[test]
fn same_day_check_in_is_rejected() {
    let dir = tempdir().unwrap();
    let paths = AppPaths::from_home(dir.path().join("home"));
    let config = BestmanConfig::default();
    config.save(&paths.config).unwrap();
    let mut app = BestmanApp::open(paths).unwrap();
    app.store
        .append(rules::init_event(
            &config,
            NaiveDate::from_ymd_opt(2026, 6, 22).unwrap(),
        ))
        .unwrap();
    app.rebuild_projection().unwrap();
    let date = NaiveDate::from_ymd_opt(2026, 6, 23).unwrap();
    let dash = app.projection.dashboard().unwrap();
    app.store
        .append(
            rules::check_in_event(
                &config,
                &dash,
                date,
                CompletionLevel::Normal,
                "".to_string(),
                Some(2),
            )
            .unwrap(),
        )
        .unwrap();
    app.rebuild_projection().unwrap();
    let dash = app.projection.dashboard().unwrap();

    let err = rules::check_in_event(
        &config,
        &dash,
        date,
        CompletionLevel::Full,
        "".to_string(),
        Some(3),
    )
    .unwrap_err()
    .to_string();
    assert!(err.contains("today is already recorded"));
}

#[test]
fn narrative_generated_replaces_template_log() {
    let dir = tempdir().unwrap();
    let paths = AppPaths::from_home(dir.path().join("home"));
    BestmanConfig::default().save(&paths.config).unwrap();
    let mut app = BestmanApp::open(paths).unwrap();
    let config = app.config.clone();
    app.store
        .append(rules::init_event(
            &config,
            NaiveDate::from_ymd_opt(2026, 6, 22).unwrap(),
        ))
        .unwrap();
    app.rebuild_projection().unwrap();
    let dash = app.projection.dashboard().unwrap();
    let check_in = rules::check_in_event(
        &config,
        &dash,
        NaiveDate::from_ymd_opt(2026, 6, 23).unwrap(),
        CompletionLevel::Light,
        "".to_string(),
        Some(1),
    )
    .unwrap();
    let target = app.store.append(check_in).unwrap().id;
    app.store
        .append(rules::narrative_generated_event(
            target,
            "LLM 替换日志".to_string(),
            "mock".to_string(),
            "test-v1".to_string(),
        ))
        .unwrap();
    app.rebuild_projection().unwrap();
    assert_eq!(
        app.projection.dashboard().unwrap().latest_log.as_deref(),
        Some("LLM 替换日志")
    );
}

#[test]
fn llm_request_and_response_contract_are_openai_compatible() {
    let request = build_openai_chat_request("test-model", "写一段日志", "prompt-v2");
    assert_eq!(request["model"], "test-model");
    assert_eq!(request["metadata"]["prompt_version"], "prompt-v2");
    assert_eq!(request["messages"][0]["role"], "system");
    assert_eq!(request["messages"][1]["content"], "写一段日志");
    assert!(
        request["messages"][0]["content"]
            .as_str()
            .unwrap()
            .contains("Do not change coins")
    );

    let response = serde_json::json!({
        "choices": [
            { "message": { "content": "小船在灯下轻轻靠岸。" } }
        ]
    });
    assert_eq!(
        parse_openai_chat_response(&response).unwrap(),
        "小船在灯下轻轻靠岸。"
    );
    assert!(parse_openai_chat_response(&serde_json::json!({})).is_err());
}

#[test]
fn plan_events_update_daily_task_and_replay() {
    let config = BestmanConfig::default();
    let dir = tempdir().unwrap();
    let paths = AppPaths::from_home(dir.path().join("home"));
    config.save(&paths.config).unwrap();
    let mut app = BestmanApp::open(paths).unwrap();
    app.store
        .append(rules::init_event(
            &config,
            NaiveDate::from_ymd_opt(2026, 6, 22).unwrap(),
        ))
        .unwrap();
    app.store
        .append(
            rules::plan_created_event(
                NaiveDate::from_ymd_opt(2026, 6, 23).unwrap(),
                "减脂保状态".to_string(),
                vec!["深蹲 3x12".to_string(), "快走 20 分钟".to_string()],
            )
            .unwrap(),
        )
        .unwrap();
    app.store
        .append(
            rules::plan_adjusted_event(
                NaiveDate::from_ymd_opt(2026, 6, 24).unwrap(),
                "轻量拉伸 15 分钟".to_string(),
                "fatigue".to_string(),
            )
            .unwrap(),
        )
        .unwrap();
    app.rebuild_projection().unwrap();
    let before = app.projection.dashboard().unwrap();
    assert_eq!(before.plan_goal.as_deref(), Some("减脂保状态"));
    assert_eq!(before.plan_tasks.len(), 2);
    assert_eq!(before.daily_task, "轻量拉伸 15 分钟");

    std::fs::remove_file(&app.paths.db).unwrap();
    let events = app.store.read_all().unwrap();
    let mut rebuilt = Projection::open(&app.paths.db).unwrap();
    rebuilt.rebuild(events).unwrap();
    assert_eq!(rebuilt.dashboard().unwrap(), before);
}

#[test]
fn recap_event_is_persisted_as_latest_log_and_replays() {
    let config = BestmanConfig::default();
    let dir = tempdir().unwrap();
    let paths = AppPaths::from_home(dir.path().join("home"));
    config.save(&paths.config).unwrap();
    let mut app = BestmanApp::open(paths).unwrap();
    app.store
        .append(rules::init_event(
            &config,
            NaiveDate::from_ymd_opt(2026, 6, 22).unwrap(),
        ))
        .unwrap();
    app.store
        .append(
            rules::recap_generated_event(
                NaiveDate::from_ymd_opt(2026, 6, 23).unwrap(),
                "Recap: 小船稳稳前进。".to_string(),
                "template".to_string(),
                "test-recap".to_string(),
            )
            .unwrap(),
        )
        .unwrap();
    app.rebuild_projection().unwrap();
    let before = app.projection.dashboard().unwrap();
    assert_eq!(before.latest_log.as_deref(), Some("Recap: 小船稳稳前进。"));

    std::fs::remove_file(&app.paths.db).unwrap();
    let events = app.store.read_all().unwrap();
    let mut rebuilt = Projection::open(&app.paths.db).unwrap();
    rebuilt.rebuild(events).unwrap();
    assert_eq!(rebuilt.dashboard().unwrap(), before);
}

#[test]
fn milestone_epic_event_is_persisted_as_latest_log_and_replays() {
    let config = BestmanConfig::default();
    let dir = tempdir().unwrap();
    let paths = AppPaths::from_home(dir.path().join("home"));
    config.save(&paths.config).unwrap();
    let mut app = BestmanApp::open(paths).unwrap();
    app.store
        .append(rules::init_event(
            &config,
            NaiveDate::from_ymd_opt(2026, 6, 22).unwrap(),
        ))
        .unwrap();
    app.store
        .append(
            rules::milestone_epic_generated_event(
                NaiveDate::from_ymd_opt(2026, 6, 23).unwrap(),
                "第一片远海".to_string(),
                "Milestone Epic: 第一片远海被写入航海志。".to_string(),
                "template".to_string(),
                "test-milestone".to_string(),
            )
            .unwrap(),
        )
        .unwrap();
    app.rebuild_projection().unwrap();
    let before = app.projection.dashboard().unwrap();
    assert_eq!(
        before.latest_log.as_deref(),
        Some("Milestone Epic: 第一片远海被写入航海志。")
    );

    std::fs::remove_file(&app.paths.db).unwrap();
    let events = app.store.read_all().unwrap();
    let mut rebuilt = Projection::open(&app.paths.db).unwrap();
    rebuilt.rebuild(events).unwrap();
    assert_eq!(rebuilt.dashboard().unwrap(), before);
}

#[test]
fn manifest_rejects_path_traversal() {
    let dir = tempdir().unwrap();
    let path = dir.path().join("vessel.json");
    std::fs::write(
        &path,
        r#"{
            "id":"bad",
            "displayName":"bad",
            "description":"bad",
            "spritesheetPath":"../escape.png",
            "frame":{"width":128,"height":128,"columns":1,"rows":4},
            "animations":{
                "idle":{"frames":[0],"fps":6.0,"looped":true,"fallback":"idle"},
                "sailing":{"frames":[0],"fps":6.0,"looped":true,"fallback":"idle"},
                "resting":{"frames":[0],"fps":6.0,"looped":true,"fallback":"idle"},
                "celebrating":{"frames":[0],"fps":6.0,"looped":true,"fallback":"idle"}
            }
        }"#,
    )
    .unwrap();
    assert!(VesselManifest::load(&path).is_err());
}

#[test]
fn preview_generation_produces_nonblank_png() {
    let catalog = VesselCatalog::load_default().unwrap();
    let manifest = catalog.find("starter_sloop").unwrap();
    let dir = tempdir().unwrap();
    let output = dir.path().join("preview.png");
    render_preview(manifest, "idle", &output).unwrap();
    assert!(output.exists());
    let img = image::open(&output).unwrap().to_rgba8();
    assert_eq!(img.dimensions(), (128, 128));
    let unique = img
        .pixels()
        .map(|p| p.0)
        .collect::<std::collections::HashSet<_>>();
    assert!(unique.len() > 4, "preview image should not be blank");
}

#[test]
fn custom_vessel_catalog_and_frame_cache_work() {
    let dir = tempdir().unwrap();
    let custom_dir = dir.path().join("vessels/mock_boat");
    std::fs::create_dir_all(&custom_dir).unwrap();
    std::fs::write(
        dir.path().join("catalog.json"),
        r#"{
            "items": [
                {
                    "id": "mock_boat",
                    "kind": "vessel",
                    "rarity": "common",
                    "price": 0,
                    "unlock": { "type": "always" },
                    "assetPath": "vessels/mock_boat/vessel.json",
                    "tags": ["test"]
                }
            ]
        }"#,
    )
    .unwrap();
    std::fs::write(
        custom_dir.join("vessel.json"),
        r#"{
            "id":"mock_boat",
            "displayName":"Mock Boat",
            "description":"custom test boat",
            "spritesheetPath":"spritesheet.png",
            "frame":{"width":32,"height":32,"columns":2,"rows":2},
            "animations":{
                "idle":{"frames":[0],"fps":6.0,"looped":true,"fallback":"idle"},
                "sailing":{"frames":[1],"fps":6.0,"looped":true,"fallback":"idle"},
                "resting":{"frames":[2],"fps":6.0,"looped":true,"fallback":"idle"},
                "celebrating":{"frames":[3],"fps":6.0,"looped":true,"fallback":"idle"}
            }
        }"#,
    )
    .unwrap();

    let catalog = VesselCatalog::load_with_user_dir(&dir.path().join("vessels")).unwrap();
    let manifest = catalog.find("mock_boat").unwrap();
    let cache = FrameCache::new(dir.path().join("cache"));
    let frame = cache.first_animation_frame(manifest, "sailing").unwrap();
    assert!(frame.exists());
    let img = image::open(frame).unwrap();
    assert_eq!(img.width(), 32);
    assert_eq!(img.height(), 32);
}

#[test]
fn catalog_purchase_and_equip_replay_as_owned_vessel() {
    let config = BestmanConfig::default();
    let dir = tempdir().unwrap();
    let paths = AppPaths::from_home(dir.path().join("home"));
    config.save(&paths.config).unwrap();
    let mut app = BestmanApp::open(paths).unwrap();
    let catalog = VesselCatalog::load_with_user_dir(&app.paths.home.join("vessels")).unwrap();
    let vessel_ids = catalog
        .vessel_items()
        .map(|item| item.id.as_str())
        .collect::<Vec<_>>();
    assert_eq!(
        vessel_ids,
        vec![
            "cloudblade_skiff",
            "dragon_prow",
            "ghost_lantern",
            "starter_sloop",
            "yinglong_ark"
        ]
    );

    app.store
        .append(rules::init_event(
            &config,
            NaiveDate::from_ymd_opt(2026, 6, 22).unwrap(),
        ))
        .unwrap();
    app.rebuild_projection().unwrap();
    assert_eq!(
        app.projection.dashboard().unwrap().owned_vessels,
        vec!["starter_sloop".to_string()]
    );

    for day in 23..=30 {
        let date = NaiveDate::from_ymd_opt(2026, 6, day).unwrap();
        let dash = app.projection.dashboard().unwrap();
        app.store
            .append(
                rules::check_in_event(
                    &config,
                    &dash,
                    date,
                    CompletionLevel::Full,
                    "".to_string(),
                    Some(1),
                )
                .unwrap(),
            )
            .unwrap();
        app.rebuild_projection().unwrap();
    }
    let dash = app.projection.dashboard().unwrap();
    assert_eq!(dash.coins, 96);

    let dragon = catalog.find_item("dragon_prow").unwrap();
    app.store
        .append(rules::purchase_event(&dash, dragon).unwrap())
        .unwrap();
    app.rebuild_projection().unwrap();
    let dash = app.projection.dashboard().unwrap();
    assert_eq!(dash.coins, 16);
    assert!(dash.owned_vessels.contains(&"dragon_prow".to_string()));

    app.store
        .append(rules::equip_vessel_event(&dash, "dragon_prow".to_string()).unwrap())
        .unwrap();
    app.rebuild_projection().unwrap();
    let before = app.projection.dashboard().unwrap();
    assert_eq!(before.current_vessel, "dragon_prow");
    assert_eq!(before.animation, VesselAnimation::Happy);

    std::fs::remove_file(&app.paths.db).unwrap();
    let events = app.store.read_all().unwrap();
    let mut rebuilt = Projection::open(&app.paths.db).unwrap();
    rebuilt.rebuild(events).unwrap();
    assert_eq!(rebuilt.dashboard().unwrap(), before);
}

#[test]
fn rest_day_uses_rest_event_without_skip_penalty() {
    let config = BestmanConfig::default();
    let dir = tempdir().unwrap();
    let paths = AppPaths::from_home(dir.path().join("home"));
    config.save(&paths.config).unwrap();
    let mut app = BestmanApp::open(paths).unwrap();
    app.store
        .append(rules::init_event(
            &config,
            NaiveDate::from_ymd_opt(2026, 6, 22).unwrap(),
        ))
        .unwrap();
    app.rebuild_projection().unwrap();
    let dash = app.projection.dashboard().unwrap();
    let sunday = NaiveDate::from_ymd_opt(2026, 6, 28).unwrap();
    let event = rules::skip_or_rest_event(&config, &dash, sunday, "rest".to_string()).unwrap();
    assert!(matches!(event.kind, EventKind::RestDayObserved { .. }));
}

#[test]
fn repeated_skip_switches_to_low_energy_without_extra_penalty() {
    let config = BestmanConfig::default();
    let dir = tempdir().unwrap();
    let paths = AppPaths::from_home(dir.path().join("home"));
    config.save(&paths.config).unwrap();
    let mut app = BestmanApp::open(paths).unwrap();
    app.store
        .append(rules::init_event(
            &config,
            NaiveDate::from_ymd_opt(2026, 6, 22).unwrap(),
        ))
        .unwrap();
    app.rebuild_projection().unwrap();

    let first_skip_date = NaiveDate::from_ymd_opt(2026, 6, 23).unwrap();
    let dash = app.projection.dashboard().unwrap();
    app.store
        .append(
            rules::skip_or_rest_event(&config, &dash, first_skip_date, "tired".to_string())
                .unwrap(),
        )
        .unwrap();
    app.rebuild_projection().unwrap();
    let after_first = app.projection.dashboard().unwrap();
    assert_eq!(after_first.animation, VesselAnimation::Resting);
    assert_eq!(after_first.mood, 58);

    let second_skip_date = NaiveDate::from_ymd_opt(2026, 6, 24).unwrap();
    app.store
        .append(
            rules::skip_or_rest_event(
                &config,
                &after_first,
                second_skip_date,
                "still tired".to_string(),
            )
            .unwrap(),
        )
        .unwrap();
    app.rebuild_projection().unwrap();
    let after_second = app.projection.dashboard().unwrap();
    assert_eq!(after_second.animation, VesselAnimation::LowEnergy);
    assert_eq!(after_second.mood, 56);
    assert_eq!(after_second.streak, 0);
    assert!(
        after_second
            .latest_log
            .as_deref()
            .unwrap()
            .contains("从轻量开始")
    );
}

#[test]
fn seven_day_streak_changes_companion_feedback_without_extra_coins() {
    let config = BestmanConfig::default();
    let dir = tempdir().unwrap();
    let paths = AppPaths::from_home(dir.path().join("home"));
    config.save(&paths.config).unwrap();
    let mut app = BestmanApp::open(paths).unwrap();
    app.store
        .append(rules::init_event(
            &config,
            NaiveDate::from_ymd_opt(2026, 6, 22).unwrap(),
        ))
        .unwrap();
    app.rebuild_projection().unwrap();

    for day in 23..=29 {
        let date = NaiveDate::from_ymd_opt(2026, 6, day).unwrap();
        let dash = app.projection.dashboard().unwrap();
        let event = rules::check_in_event(
            &config,
            &dash,
            date,
            CompletionLevel::Light,
            "".to_string(),
            Some(1),
        )
        .unwrap();
        app.store.append(event).unwrap();
        app.rebuild_projection().unwrap();
    }

    let dash = app.projection.dashboard().unwrap();
    assert_eq!(dash.streak, 7);
    assert_eq!(dash.coins, 49);
    assert_eq!(dash.animation, VesselAnimation::Happy);
    assert!(dash.latest_log.as_deref().unwrap().contains("连续 7 天"));
}

#[test]
fn terminal_image_protocol_detection_and_kitty_encoding_work() {
    assert_eq!(
        detect_from_env(Some("xterm-kitty"), None),
        ImageProtocol::Kitty
    );
    assert_eq!(
        detect_from_env(Some("xterm-256color"), Some("WezTerm")),
        ImageProtocol::Kitty
    );
    assert_eq!(
        detect_from_env(Some("xterm-sixel"), None),
        ImageProtocol::Sixel
    );
    assert_eq!(
        detect_from_env(Some("xterm-256color"), None),
        ImageProtocol::None
    );

    let catalog = VesselCatalog::load_default().unwrap();
    let manifest = catalog.find("starter_sloop").unwrap();
    let dir = tempdir().unwrap();
    let png = dir.path().join("preview.png");
    render_preview(manifest, "idle", &png).unwrap();
    let seq = kitty_inline_png(&png, 42).unwrap();
    assert!(seq.starts_with("\u{1b}_Ga=T,f=100,i=42,m=0;"));
    assert!(seq.ends_with("\u{1b}\\"));
    assert!(seq.len() > 100);
    let sized = kitty_inline_png_sized(&png, 43, Some(40), Some(16)).unwrap();
    assert!(sized.starts_with("\u{1b}_Ga=T,f=100,i=43,c=40,r=16,m=0;"));
    assert_eq!(kitty_delete(42), "\u{1b}_Ga=d,d=i,i=42\u{1b}\\");
}

#[test]
fn kitty_encoding_changes_across_animation_frames() {
    let catalog = VesselCatalog::load_default().unwrap();
    let manifest = catalog.find("starter_sloop").unwrap();
    let dir = tempdir().unwrap();
    let cache = FrameCache::new(dir.path().join("cache"));
    let frames = cache.animation_frames(manifest, "sailing").unwrap();
    assert_eq!(frames.len(), 4);

    let first = kitty_inline_png(&frames[0], 77).unwrap();
    let last = kitty_inline_png(&frames[3], 77).unwrap();
    assert!(first.contains("\u{1b}_Ga=T,f=100,i=77"));
    assert_ne!(
        first, last,
        "different animation frames should produce different terminal image payloads"
    );
}

#[test]
fn dashboard_snapshot_and_png_export_are_valid() {
    let dir = tempdir().unwrap();
    let paths = AppPaths::from_home(dir.path().join("home"));
    let config = BestmanConfig::default();
    config.save(&paths.config).unwrap();
    let mut app = BestmanApp::open(paths).unwrap();
    app.store
        .append(rules::init_event(
            &config,
            NaiveDate::from_ymd_opt(2026, 6, 22).unwrap(),
        ))
        .unwrap();
    app.rebuild_projection().unwrap();

    let render = build_dashboard_render(&app).unwrap();
    assert!(render.text.contains("Bestman Companion"));
    assert!(render.text.contains("Companion"));
    assert!(render.text.contains("Route progress"));
    assert!(!render.text.contains("proto"));
    assert!(!render.text.contains("image  /"));
    assert!(render.companion_frame.exists());

    let output = dir.path().join("dashboard.png");
    export_dashboard_png(&app, &output).unwrap();
    let img = image::open(&output).unwrap().to_rgba8();
    assert_eq!(img.dimensions(), (900, 560));
    let unique = img
        .pixels()
        .map(|p| p.0)
        .collect::<std::collections::HashSet<_>>();
    assert!(
        unique.len() > 8,
        "dashboard image should contain multiple visual regions"
    );
}

#[test]
fn animation_and_dashboard_frame_sequences_export() {
    let dir = tempdir().unwrap();
    let catalog = VesselCatalog::load_default().unwrap();
    let manifest = catalog.find("starter_sloop").unwrap();
    let raw_frames = export_animation_frames(manifest, "sailing", &dir.path().join("raw")).unwrap();
    assert_eq!(raw_frames.len(), 4);
    for frame in &raw_frames {
        let img = image::open(frame).unwrap();
        assert_eq!(img.dimensions(), (128, 128));
    }
    assert_ne!(
        std::fs::read(&raw_frames[0]).unwrap(),
        std::fs::read(&raw_frames[3]).unwrap(),
        "sailing animation frames should visibly change"
    );

    let paths = AppPaths::from_home(dir.path().join("home"));
    let config = BestmanConfig::default();
    config.save(&paths.config).unwrap();
    let mut app = BestmanApp::open(paths).unwrap();
    app.store
        .append(rules::init_event(
            &config,
            NaiveDate::from_ymd_opt(2026, 6, 22).unwrap(),
        ))
        .unwrap();
    app.rebuild_projection().unwrap();
    let dash = app.projection.dashboard().unwrap();
    let event = rules::check_in_event(
        &config,
        &dash,
        NaiveDate::from_ymd_opt(2026, 6, 23).unwrap(),
        CompletionLevel::Normal,
        "".to_string(),
        Some(2),
    )
    .unwrap();
    app.store.append(event).unwrap();
    app.rebuild_projection().unwrap();

    let dashboard_frames =
        export_dashboard_frames(&app, &dir.path().join("dashboard-frames")).unwrap();
    assert_eq!(dashboard_frames.len(), 4);
    let img = image::open(&dashboard_frames[0]).unwrap();
    assert_eq!(img.dimensions(), (900, 560));
    assert_ne!(
        std::fs::read(&dashboard_frames[0]).unwrap(),
        std::fs::read(&dashboard_frames[3]).unwrap(),
        "dashboard animation frames should include changing companion frames"
    );
}
