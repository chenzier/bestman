use assert_cmd::Command;
use bestman_rs::app::{AppPaths, BestmanApp};
use bestman_rs::config::BestmanConfig;
use bestman_rs::events::CompletionLevel;
use bestman_rs::rules;
use chrono::NaiveDate;
use predicates::prelude::*;
use tempfile::tempdir;

#[test]
fn cli_init_done_status_and_log_work() {
    let dir = tempdir().unwrap();
    let home = dir.path().join("home");

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args([
            "--home",
            home.to_str().unwrap(),
            "init",
            "--daily-task",
            "俯卧撑 3x10",
            "--total-days",
            "30",
        ])
        .assert()
        .success()
        .stdout(predicate::str::contains("initialized"));

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args([
            "--home",
            home.to_str().unwrap(),
            "done",
            "--level",
            "full",
            "--dice",
            "3",
            "--mock-llm",
        ])
        .assert()
        .success()
        .stdout(predicate::str::contains("Check-in recorded"))
        .stdout(predicate::str::contains("task: 俯卧撑 3x10"))
        .stdout(predicate::str::contains("voyage: 0 -> 3 (+3 days)"))
        .stdout(predicate::str::contains("coins: +12"));

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "status", "--json"])
        .assert()
        .success()
        .stdout(predicate::str::contains("\"daily_task\": \"俯卧撑 3x10\""))
        .stdout(predicate::str::contains("\"position\": 3"))
        .stdout(predicate::str::contains("\"coins\": 12"))
        .stdout(predicate::str::contains(
            "\"owned_vessels\": [\n    \"starter_sloop\"\n  ]",
        ))
        .stdout(predicate::str::contains(
            "\"last_action_kind\": \"check_in\"",
        ));

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "log"])
        .assert()
        .success()
        .stdout(predicate::str::contains("LLM航海日志"));
}

#[test]
fn cli_done_generates_milestone_epic_when_crossing_milestone() {
    let dir = tempdir().unwrap();
    let home = dir.path().join("home");

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args([
            "--home",
            home.to_str().unwrap(),
            "init",
            "--daily-task",
            "俯卧撑 3x10",
            "--total-days",
            "4",
        ])
        .assert()
        .success();

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args([
            "--home",
            home.to_str().unwrap(),
            "done",
            "--level",
            "normal",
            "--dice",
            "1",
        ])
        .assert()
        .success()
        .stdout(predicate::str::contains("milestones: 第一片远海"))
        .stdout(predicate::str::contains("Milestone Epic: 第一片远海"));

    let events = std::fs::read_to_string(home.join("events.jsonl")).unwrap();
    assert!(events.contains("\"type\":\"milestone_epic_generated\""));

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "log"])
        .assert()
        .success()
        .stdout(predicate::str::contains("Milestone Epic: 第一片远海"));
}

#[test]
fn cli_talk_generates_captain_reply_without_state_changes() {
    let dir = tempdir().unwrap();
    let home = dir.path().join("home");

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "init"])
        .assert()
        .success();

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "status", "--json"])
        .assert()
        .success()
        .stdout(predicate::str::contains("\"position\": 0"))
        .stdout(predicate::str::contains("\"coins\": 0"));

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args([
            "--home",
            home.to_str().unwrap(),
            "talk",
            "今天有点累，还要练吗？",
        ])
        .assert()
        .success()
        .stdout(predicate::str::contains("Captain:"))
        .stdout(predicate::str::contains("轻量"));

    let events = std::fs::read_to_string(home.join("events.jsonl")).unwrap();
    assert!(events.contains("\"type\":\"captain_chat_generated\""));

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "status", "--json"])
        .assert()
        .success()
        .stdout(predicate::str::contains("\"position\": 0"))
        .stdout(predicate::str::contains("\"coins\": 0"))
        .stdout(predicate::str::contains(
            "\"latest_log\": \"可以把今天降到轻量版",
        ));
}

#[test]
fn cli_weigh_records_replayable_weight_progress() {
    let dir = tempdir().unwrap();
    let home = dir.path().join("home");

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "init"])
        .assert()
        .success();

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args([
            "--home",
            home.to_str().unwrap(),
            "weigh",
            "101.2",
            "--note",
            "morning",
        ])
        .assert()
        .success()
        .stdout(predicate::str::contains("weight recorded: 101.2kg"))
        .stdout(predicate::str::contains("Weight Progress"))
        .stdout(predicate::str::contains("latest: 101.2kg"))
        .stdout(predicate::str::contains("first record"));

    let events = std::fs::read_to_string(home.join("events.jsonl")).unwrap();
    assert!(events.contains("\"type\":\"weight_recorded\""));
    assert!(events.contains("\"weight_kg\":101.2"));

    std::fs::remove_file(home.join("bestman.db")).unwrap();
    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "rebuild"])
        .assert()
        .success();

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "progress"])
        .assert()
        .success()
        .stdout(predicate::str::contains("latest: 101.2kg"))
        .stdout(predicate::str::contains("- "))
        .stdout(predicate::str::contains("morning"));

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "status", "--json"])
        .assert()
        .success()
        .stdout(predicate::str::contains("\"latest_weight\""))
        .stdout(predicate::str::contains("\"weight_kg\": 101.2"))
        .stdout(predicate::str::contains("\"note\": \"morning\""));
}

#[test]
fn cli_advice_generates_health_advice_without_state_changes() {
    let dir = tempdir().unwrap();
    let home = dir.path().join("home");

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "init"])
        .assert()
        .success();

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "weigh", "101.2"])
        .assert()
        .success();

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args([
            "--home",
            home.to_str().unwrap(),
            "advice",
            "膝盖有点不舒服，今天怎么练？",
        ])
        .assert()
        .success()
        .stdout(predicate::str::contains("Health Advice:"))
        .stdout(predicate::str::contains("低冲击"))
        .stdout(predicate::str::contains("专业人士"));

    let events = std::fs::read_to_string(home.join("events.jsonl")).unwrap();
    assert!(events.contains("\"type\":\"health_advice_generated\""));

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "status", "--json"])
        .assert()
        .success()
        .stdout(predicate::str::contains("\"position\": 0"))
        .stdout(predicate::str::contains("\"coins\": 0"))
        .stdout(predicate::str::contains("\"weight_kg\": 101.2"))
        .stdout(predicate::str::contains("\"latest_log\": \"今天先避开"));
}

#[test]
fn installed_binary_name_works_for_v1_entrypoint() {
    let dir = tempdir().unwrap();
    let home = dir.path().join("home");

    Command::cargo_bin("bestman")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "init"])
        .assert()
        .success()
        .stdout(predicate::str::contains("initialized"));

    Command::cargo_bin("bestman")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "status", "--json"])
        .assert()
        .success()
        .stdout(predicate::str::contains("\"initialized\": true"));
}

#[test]
fn cli_rejects_second_check_in_on_same_day() {
    let dir = tempdir().unwrap();
    let home = dir.path().join("home");

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "init"])
        .assert()
        .success();

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "done", "--dice", "1"])
        .assert()
        .success();

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "done", "--dice", "1"])
        .assert()
        .failure()
        .stderr(predicate::str::contains("today is already recorded"));
}

#[test]
fn cli_skip_prints_companion_feedback() {
    let dir = tempdir().unwrap();
    let home = dir.path().join("home");

    Command::cargo_bin("bestman")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "init"])
        .assert()
        .success();
    std::fs::write(
        home.join("config.toml"),
        r#"[voyage]
total_days = 120
daily_task = "深蹲 3x15 + 平板支撑 3x30s"
rest_days = []

[companion]
current_vessel = "starter_sloop"

[llm]
enabled = false
provider = "openai_compatible"
base_url = "https://api.openai.com/v1"
api_key_env = "OPENAI_API_KEY"
model = "gpt-4o-mini"
prompt_version = "bestman-v2-narrative"
"#,
    )
    .unwrap();

    Command::cargo_bin("bestman")
        .unwrap()
        .args([
            "--home",
            home.to_str().unwrap(),
            "skip",
            "--reason",
            "tired",
        ])
        .assert()
        .success()
        .stdout(predicate::str::contains("Rest recorded"))
        .stdout(predicate::str::contains("type: rest/skip"))
        .stdout(predicate::str::contains("vessel state: resting"))
        .stdout(predicate::str::contains("mood: -2 (60 -> 58)"))
        .stdout(predicate::str::contains("streak: 0"))
        .stdout(predicate::str::contains("log:"));
}

#[test]
fn cli_reset_requires_confirmation_and_clears_home() {
    let dir = tempdir().unwrap();
    let home = dir.path().join("home");

    Command::cargo_bin("bestman")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "init"])
        .assert()
        .success();

    Command::cargo_bin("bestman")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "done", "--dice", "2"])
        .assert()
        .success();
    assert!(home.join("events.jsonl").exists());
    assert!(home.join("bestman.db").exists());

    Command::cargo_bin("bestman")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "reset"])
        .assert()
        .failure()
        .stderr(predicate::str::contains("Re-run with --yes"));
    assert!(home.join("events.jsonl").exists());

    Command::cargo_bin("bestman")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "reset", "--yes"])
        .assert()
        .success()
        .stdout(predicate::str::contains("bestman data reset"));
    assert!(!home.exists());

    Command::cargo_bin("bestman")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "status", "--json"])
        .assert()
        .success()
        .stdout(predicate::str::contains("\"initialized\": false"))
        .stdout(predicate::str::contains("\"position\": 0"));
}

#[test]
fn cli_config_show_and_rebuild_projection_work() {
    let dir = tempdir().unwrap();
    let home = dir.path().join("home");

    Command::cargo_bin("bestman")
        .unwrap()
        .args([
            "--home",
            home.to_str().unwrap(),
            "init",
            "--daily-task",
            "划船机 20 分钟",
            "--total-days",
            "30",
        ])
        .assert()
        .success();

    Command::cargo_bin("bestman")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "config", "show"])
        .assert()
        .success()
        .stdout(predicate::str::contains("total_days = 30"))
        .stdout(predicate::str::contains("daily_task = \"划船机 20 分钟\""))
        .stdout(predicate::str::contains("api_key_env = \"OPENAI_API_KEY\""));

    Command::cargo_bin("bestman")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "done", "--dice", "2"])
        .assert()
        .success();
    std::fs::remove_file(home.join("bestman.db")).unwrap();

    Command::cargo_bin("bestman")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "rebuild"])
        .assert()
        .success()
        .stdout(predicate::str::contains("projection rebuilt"))
        .stdout(predicate::str::contains("events: 2"))
        .stdout(predicate::str::contains("position: 2/30"));

    Command::cargo_bin("bestman")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "status", "--json"])
        .assert()
        .success()
        .stdout(predicate::str::contains("\"position\": 2"))
        .stdout(predicate::str::contains("\"coins\": 10"));
}

#[test]
fn cli_config_llm_updates_config_and_home_env_is_loaded() {
    let dir = tempdir().unwrap();
    let home = dir.path().join("home");

    Command::cargo_bin("bestman")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "init"])
        .assert()
        .success();

    Command::cargo_bin("bestman")
        .unwrap()
        .args([
            "--home",
            home.to_str().unwrap(),
            "config",
            "llm",
            "--enable",
            "--base-url",
            "http://127.0.0.1:9/v1",
            "--model",
            "test-model",
            "--api-key-env",
            "BESTMAN_TEST_API_KEY",
        ])
        .assert()
        .success()
        .stdout(predicate::str::contains("llm config updated"))
        .stdout(predicate::str::contains("enabled: true"))
        .stdout(predicate::str::contains("model: test-model"));

    Command::cargo_bin("bestman")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "config", "show"])
        .assert()
        .success()
        .stdout(predicate::str::contains("enabled = true"))
        .stdout(predicate::str::contains(
            "base_url = \"http://127.0.0.1:9/v1\"",
        ))
        .stdout(predicate::str::contains(
            "api_key_env = \"BESTMAN_TEST_API_KEY\"",
        ))
        .stdout(predicate::str::contains("model = \"test-model\""));

    Command::cargo_bin("bestman")
        .unwrap()
        .args([
            "--home",
            home.to_str().unwrap(),
            "done",
            "--dice",
            "1",
            "--llm",
        ])
        .assert()
        .success()
        .stderr(predicate::str::contains(
            "missing API key env BESTMAN_TEST_API_KEY",
        ));

    std::fs::write(home.join(".env"), "BESTMAN_TEST_API_KEY=test-key\n").unwrap();
    Command::cargo_bin("bestman")
        .unwrap()
        .args([
            "--home",
            home.to_str().unwrap(),
            "talk",
            "测试一下 LLM key",
            "--llm",
        ])
        .assert()
        .success()
        .stderr(predicate::str::contains("missing API key env").not());
}

#[test]
fn cli_coin_grant_adds_replayable_coins() {
    let dir = tempdir().unwrap();
    let home = dir.path().join("home");

    Command::cargo_bin("bestman")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "init"])
        .assert()
        .success();

    Command::cargo_bin("bestman")
        .unwrap()
        .args([
            "--home",
            home.to_str().unwrap(),
            "coins",
            "grant",
            "10000",
            "--reason",
            "shop testing",
        ])
        .assert()
        .success()
        .stdout(predicate::str::contains("coins granted: +10000"))
        .stdout(predicate::str::contains("coins: 10000"));

    std::fs::remove_file(home.join("bestman.db")).unwrap();
    Command::cargo_bin("bestman")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "rebuild"])
        .assert()
        .success();

    Command::cargo_bin("bestman")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "status", "--json"])
        .assert()
        .success()
        .stdout(predicate::str::contains("\"coins\": 10000"));
}

#[test]
fn cli_lists_builtin_catalog_and_blocks_unowned_vessel_equip() {
    let dir = tempdir().unwrap();
    let home = dir.path().join("home");

    Command::cargo_bin("bestman")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "init"])
        .assert()
        .success();

    Command::cargo_bin("bestman")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "shop", "list"])
        .assert()
        .success()
        .stdout(predicate::str::contains(
            "starter_sloop - kind=vessel rarity=common price=0 owned",
        ))
        .stdout(predicate::str::contains(
            "dragon_prow - kind=vessel rarity=uncommon price=80 available",
        ))
        .stdout(predicate::str::contains(
            "yinglong_ark - kind=vessel rarity=epic price=360 available",
        ));

    Command::cargo_bin("bestman")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "vessel", "list"])
        .assert()
        .success()
        .stdout(predicate::str::contains("starter_sloop"))
        .stdout(predicate::str::contains("[equipped]"))
        .stdout(predicate::str::contains("dragon_prow"))
        .stdout(predicate::str::contains("[locked]"));

    Command::cargo_bin("bestman")
        .unwrap()
        .args([
            "--home",
            home.to_str().unwrap(),
            "vessel",
            "set",
            "dragon_prow",
        ])
        .assert()
        .failure()
        .stderr(predicate::str::contains("is not owned"));
}

#[test]
fn cli_vessel_validate_checks_catalog_assets() {
    let dir = tempdir().unwrap();
    let home = dir.path().join("home");

    Command::cargo_bin("bestman")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "vessel", "validate"])
        .assert()
        .success()
        .stdout(predicate::str::contains("starter_sloop ok"))
        .stdout(predicate::str::contains("validated 5 vessel(s)"));

    Command::cargo_bin("bestman")
        .unwrap()
        .args([
            "--home",
            home.to_str().unwrap(),
            "vessel",
            "validate",
            "dragon_prow",
        ])
        .assert()
        .success()
        .stdout(predicate::str::contains("dragon_prow ok"))
        .stdout(predicate::str::contains("validated 1 vessel(s)"));

    assert!(
        home.join("cache/vessel-validation/dragon_prow-idle.png")
            .exists()
    );
}

#[test]
fn cli_plan_commands_update_today_task() {
    let dir = tempdir().unwrap();
    let home = dir.path().join("home");

    Command::cargo_bin("bestman")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "init"])
        .assert()
        .success();

    Command::cargo_bin("bestman")
        .unwrap()
        .args([
            "--home",
            home.to_str().unwrap(),
            "plan",
            "create",
            "--goal",
            "减脂保状态",
            "--tasks",
            "深蹲 3x12,快走 20 分钟",
        ])
        .assert()
        .success()
        .stdout(predicate::str::contains("plan created"))
        .stdout(predicate::str::contains("today: 深蹲 3x12"));

    Command::cargo_bin("bestman")
        .unwrap()
        .args([
            "--home",
            home.to_str().unwrap(),
            "plan",
            "set-today",
            "轻量拉伸 15 分钟",
            "--reason",
            "fatigue",
        ])
        .assert()
        .success()
        .stdout(predicate::str::contains("today: 轻量拉伸 15 分钟"));

    Command::cargo_bin("bestman")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "plan", "show"])
        .assert()
        .success()
        .stdout(predicate::str::contains("goal: 减脂保状态"))
        .stdout(predicate::str::contains("today: 轻量拉伸 15 分钟"))
        .stdout(predicate::str::contains("- 快走 20 分钟"));

    Command::cargo_bin("bestman")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "plan", "next"])
        .assert()
        .success()
        .stdout(predicate::str::contains("today: 深蹲 3x12"));

    Command::cargo_bin("bestman")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "plan", "next"])
        .assert()
        .success()
        .stdout(predicate::str::contains("today: 快走 20 分钟"));

    Command::cargo_bin("bestman")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "status", "--json"])
        .assert()
        .success()
        .stdout(predicate::str::contains("\"plan_goal\": \"减脂保状态\""))
        .stdout(predicate::str::contains("\"daily_task\": \"快走 20 分钟\""));

    Command::cargo_bin("bestman")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "done", "--dice", "1"])
        .assert()
        .success()
        .stdout(predicate::str::contains("task: 快走 20 分钟"));
}

#[test]
fn cli_done_llm_falls_back_when_llm_is_unavailable() {
    let dir = tempdir().unwrap();
    let home = dir.path().join("home");

    Command::cargo_bin("bestman")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "init"])
        .assert()
        .success();

    Command::cargo_bin("bestman")
        .unwrap()
        .args([
            "--home",
            home.to_str().unwrap(),
            "done",
            "--dice",
            "1",
            "--llm",
        ])
        .assert()
        .success()
        .stdout(predicate::str::contains("Check-in recorded"))
        .stderr(predicate::str::contains("LLM narrative unavailable"));
}

#[test]
fn cli_recap_generates_long_term_log_with_fallback() {
    let dir = tempdir().unwrap();
    let home = dir.path().join("home");

    Command::cargo_bin("bestman")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "init"])
        .assert()
        .success();

    Command::cargo_bin("bestman")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "done", "--dice", "1"])
        .assert()
        .success();

    Command::cargo_bin("bestman")
        .unwrap()
        .args([
            "--home",
            home.to_str().unwrap(),
            "recap",
            "--period",
            "week",
            "--llm",
        ])
        .assert()
        .success()
        .stdout(predicate::str::contains("Recap (week)"))
        .stderr(predicate::str::contains("LLM recap unavailable"));

    let events = std::fs::read_to_string(home.join("events.jsonl")).unwrap();
    assert!(events.contains("\"period\":\"week\""));

    Command::cargo_bin("bestman")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "log"])
        .assert()
        .success()
        .stdout(predicate::str::contains("Recap (week)"));
}

#[test]
fn cli_recap_auto_generates_due_weekly_recap_once() {
    let dir = tempdir().unwrap();
    let home = dir.path().join("home");
    let paths = AppPaths::from_home(home.clone());
    let config = BestmanConfig::default();
    config.save(&paths.config).unwrap();
    let mut app = BestmanApp::open(paths).unwrap();
    app.store
        .append(rules::init_event(
            &config,
            NaiveDate::from_ymd_opt(2026, 6, 1).unwrap(),
        ))
        .unwrap();
    app.rebuild_projection().unwrap();
    for day in 2..=8 {
        let dash = app.projection.dashboard().unwrap();
        app.store
            .append(
                rules::check_in_event(
                    &config,
                    &dash,
                    NaiveDate::from_ymd_opt(2026, 6, day).unwrap(),
                    CompletionLevel::Normal,
                    "".to_string(),
                    Some(1),
                )
                .unwrap(),
            )
            .unwrap();
        app.rebuild_projection().unwrap();
    }

    Command::cargo_bin("bestman")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "recap", "--auto"])
        .assert()
        .success()
        .stdout(predicate::str::contains("Recap (week)"));

    let events = std::fs::read_to_string(home.join("events.jsonl")).unwrap();
    assert!(events.contains("\"type\":\"recap_generated\""));
    assert!(events.contains("\"period\":\"week\""));

    Command::cargo_bin("bestman")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "recap", "--auto"])
        .assert()
        .success()
        .stdout(predicate::str::contains("no automatic recap due today"));
}

#[test]
fn cli_preview_writes_png() {
    let dir = tempdir().unwrap();
    let output = dir.path().join("ship.png");
    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args(["preview", "--output", output.to_str().unwrap()])
        .assert()
        .success()
        .stdout(predicate::str::contains("ship.png"));
    assert!(output.exists());
}

#[test]
fn cli_image_protocol_can_encode_kitty_inline_png() {
    let dir = tempdir().unwrap();
    let output = dir.path().join("ship.png");
    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args(["preview", "--output", output.to_str().unwrap()])
        .assert()
        .success();

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args(["image-protocol", "--kitty-inline", output.to_str().unwrap()])
        .assert()
        .success()
        .stdout(predicate::str::contains("kitty_inline_bytes="))
        .stdout(predicate::str::contains("kitty_delete_bytes="));
}

#[test]
fn cli_dashboard_image_writes_png() {
    let dir = tempdir().unwrap();
    let home = dir.path().join("home");
    let output = dir.path().join("dashboard.png");

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "init"])
        .assert()
        .success();

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args([
            "--home",
            home.to_str().unwrap(),
            "dashboard-image",
            "--output",
            output.to_str().unwrap(),
        ])
        .assert()
        .success()
        .stdout(predicate::str::contains("dashboard.png"));

    assert!(output.exists());
}

#[test]
fn cli_exports_animation_and_dashboard_frames() {
    let dir = tempdir().unwrap();
    let home = dir.path().join("home");
    let anim_dir = dir.path().join("anim");
    let dash_dir = dir.path().join("dash");

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args([
            "animation-frames",
            "--animation",
            "sailing",
            "--output-dir",
            anim_dir.to_str().unwrap(),
        ])
        .assert()
        .success()
        .stdout(predicate::str::contains("sailing-000.png"));
    assert_eq!(
        std::fs::read_dir(&anim_dir)
            .unwrap()
            .filter_map(Result::ok)
            .count(),
        4
    );

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "init"])
        .assert()
        .success();
    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "done", "--dice", "2"])
        .assert()
        .success();
    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args([
            "--home",
            home.to_str().unwrap(),
            "dashboard-frames",
            "--output-dir",
            dash_dir.to_str().unwrap(),
        ])
        .assert()
        .success()
        .stdout(predicate::str::contains("dashboard-000.png"));
    assert!(dash_dir.join("dashboard/dashboard-000.png").exists());
}

#[test]
fn cli_tui_generates_companion_preview() {
    let dir = tempdir().unwrap();
    let home = dir.path().join("home");

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "init"])
        .assert()
        .success();

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "tui"])
        .assert()
        .success()
        .stdout(predicate::str::contains("Today"))
        .stdout(predicate::str::contains("Plan"))
        .stdout(predicate::str::contains("Chat"))
        .stdout(predicate::str::contains("Shop"))
        .stdout(predicate::str::contains("Fleet"))
        .stdout(predicate::str::contains("Log"))
        .stdout(predicate::str::contains("Starter Sloop"))
        .stdout(predicate::str::contains("Task 深蹲 3x15"))
        .stdout(predicate::str::contains("Ready for today's training."))
        .stdout(predicate::str::contains("Milestone"))
        .stdout(predicate::str::contains("Route progress"))
        .stdout(predicate::str::contains("Hidden by multi-width symbols").not());

    assert!(home.join("cache/vessel-frames").exists());
}

#[test]
fn cli_live_tui_can_run_bounded_without_alt_screen() {
    let dir = tempdir().unwrap();
    let home = dir.path().join("home");

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "init"])
        .assert()
        .success();

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args([
            "--home",
            home.to_str().unwrap(),
            "tui",
            "--live",
            "--ticks",
            "2",
            "--tick-ms",
            "0",
            "--no-alt-screen",
            "--no-raw-mode",
        ])
        .assert()
        .success()
        .stdout(predicate::str::contains("live_tui_completed ticks=2"));
}

#[test]
fn cli_live_tui_can_quit_without_tick_limit() {
    let dir = tempdir().unwrap();
    let home = dir.path().join("home");

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "init"])
        .assert()
        .success();

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args([
            "--home",
            home.to_str().unwrap(),
            "tui",
            "--live",
            "--tick-ms",
            "0",
            "--no-alt-screen",
            "--no-raw-mode",
            "--script",
            "q",
        ])
        .assert()
        .success()
        .stdout(predicate::str::contains("live_tui_completed"))
        .stdout(predicate::str::contains("ticks=").not());
}

#[test]
fn cli_live_tui_script_can_switch_tabs() {
    let dir = tempdir().unwrap();
    let home = dir.path().join("home");

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "init"])
        .assert()
        .success();

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args([
            "--home",
            home.to_str().unwrap(),
            "tui",
            "--live",
            "--tick-ms",
            "0",
            "--no-alt-screen",
            "--no-raw-mode",
            "--script",
            "]]]]]q",
        ])
        .assert()
        .success()
        .stdout(predicate::str::contains("Training Plan"))
        .stdout(predicate::str::contains("Latest reply"))
        .stdout(predicate::str::contains("Ship Shop"))
        .stdout(predicate::str::contains("Fleet"))
        .stdout(predicate::str::contains("Captain's Log"))
        .stdout(predicate::str::contains("live_tui_completed"));
}

#[test]
fn cli_live_tui_chat_can_send_message() {
    let dir = tempdir().unwrap();
    let home = dir.path().join("home");

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "init"])
        .assert()
        .success();

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args([
            "--home",
            home.to_str().unwrap(),
            "tui",
            "--live",
            "--tick-ms",
            "0",
            "--no-alt-screen",
            "--no-raw-mode",
            "--script",
            "]]i累\nq",
        ])
        .assert()
        .success()
        .stdout(predicate::str::contains("Captain replied."))
        .stdout(predicate::str::contains("live_tui_completed"));

    let events = std::fs::read_to_string(home.join("events.jsonl")).unwrap();
    assert!(events.contains("\"type\":\"captain_chat_generated\""));

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "log"])
        .assert()
        .success()
        .stdout(predicate::str::contains("轻量版"));
}

#[test]
fn cli_live_tui_can_force_kitty_image_frames() {
    let dir = tempdir().unwrap();
    let home = dir.path().join("home");

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "init"])
        .assert()
        .success();

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args([
            "--home",
            home.to_str().unwrap(),
            "tui",
            "--live",
            "--ticks",
            "2",
            "--tick-ms",
            "0",
            "--no-alt-screen",
            "--no-raw-mode",
            "--force-kitty-images",
            "--image-id",
            "7007",
        ])
        .assert()
        .success()
        .stdout(predicate::str::contains("\u{1b}_Ga=d,d=i,i=7007"))
        .stdout(predicate::str::contains("\u{1b}_Ga=T,f=100,i=7007,c="))
        .stdout(predicate::str::contains(",r="))
        .stdout(predicate::str::contains("live_tui_completed ticks=2"));
}

#[test]
fn cli_live_tui_image_mode_can_quit_without_tick_limit() {
    let dir = tempdir().unwrap();
    let home = dir.path().join("home");

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "init"])
        .assert()
        .success();

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args([
            "--home",
            home.to_str().unwrap(),
            "tui",
            "--live",
            "--tick-ms",
            "0",
            "--no-alt-screen",
            "--no-raw-mode",
            "--script",
            "q",
            "--force-kitty-images",
            "--image-id",
            "7117",
        ])
        .assert()
        .success()
        .stdout(predicate::str::contains("\u{1b}_Ga=d,d=i,i=7117"))
        .stdout(predicate::str::contains("live_tui_completed"))
        .stdout(predicate::str::contains("ticks=").not());
}

#[test]
fn cli_live_tui_script_can_complete_check_in() {
    let dir = tempdir().unwrap();
    let home = dir.path().join("home");

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args([
            "--home",
            home.to_str().unwrap(),
            "init",
            "--total-days",
            "30",
        ])
        .assert()
        .success();

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args([
            "--home",
            home.to_str().unwrap(),
            "tui",
            "--live",
            "--ticks",
            "2",
            "--tick-ms",
            "0",
            "--no-alt-screen",
            "--no-raw-mode",
            "--script",
            "fq",
            "--dice",
            "3",
        ])
        .assert()
        .success()
        .stdout(predicate::str::contains("live_tui_completed ticks=2"));

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "status", "--json"])
        .assert()
        .success()
        .stdout(predicate::str::contains("\"position\": 3"))
        .stdout(predicate::str::contains("\"coins\": 12"));
}

#[test]
fn cli_live_tui_script_can_skip_or_rest() {
    let dir = tempdir().unwrap();
    let home = dir.path().join("home");

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "init"])
        .assert()
        .success();

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args([
            "--home",
            home.to_str().unwrap(),
            "tui",
            "--live",
            "--ticks",
            "2",
            "--tick-ms",
            "0",
            "--no-alt-screen",
            "--no-raw-mode",
            "--script",
            "sq",
        ])
        .assert()
        .success();

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "log"])
        .assert()
        .success()
        .stdout(predicate::str::contains("小帆船"));
}

#[test]
fn cli_live_tui_script_can_buy_and_equip_custom_vessel() {
    let dir = tempdir().unwrap();
    let home = dir.path().join("home");
    let custom_dir = home.join("vessels/custom_sloop");
    std::fs::create_dir_all(&custom_dir).unwrap();
    std::fs::write(
        home.join("catalog.json"),
        r#"{
            "items": [
                {
                    "id": "custom_sloop",
                    "kind": "vessel",
                    "rarity": "common",
                    "price": 0,
                    "unlock": { "type": "always" },
                    "assetPath": "vessels/custom_sloop/vessel.json",
                    "tags": ["test"]
                }
            ]
        }"#,
    )
    .unwrap();
    std::fs::write(
        custom_dir.join("vessel.json"),
        r#"{
            "id":"custom_sloop",
            "displayName":"Custom Sloop",
            "description":"custom test vessel",
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

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "init"])
        .assert()
        .success();

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args([
            "--home",
            home.to_str().unwrap(),
            "tui",
            "--live",
            "--ticks",
            "8",
            "--tick-ms",
            "0",
            "--no-alt-screen",
            "--no-raw-mode",
            "--script",
            "]]]jb]jeq",
        ])
        .assert()
        .success()
        .stdout(predicate::str::contains("Ship purchased."))
        .stdout(predicate::str::contains("Custom Sloop"))
        .stdout(predicate::str::contains("live_tui_completed ticks=8"));

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "status", "--json"])
        .assert()
        .success()
        .stdout(predicate::str::contains(
            "\"current_vessel\": \"custom_sloop\"",
        ))
        .stdout(predicate::str::contains("\"custom_sloop\""));
}

#[test]
fn cli_loads_and_sets_custom_vessel() {
    let dir = tempdir().unwrap();
    let home = dir.path().join("home");
    let custom_dir = home.join("vessels/custom_sloop");
    std::fs::create_dir_all(&custom_dir).unwrap();
    std::fs::write(
        home.join("catalog.json"),
        r#"{
            "items": [
                {
                    "id": "custom_sloop",
                    "kind": "vessel",
                    "rarity": "common",
                    "price": 0,
                    "unlock": { "type": "always" },
                    "assetPath": "vessels/custom_sloop/vessel.json",
                    "tags": ["test"]
                }
            ]
        }"#,
    )
    .unwrap();
    std::fs::write(
        custom_dir.join("vessel.json"),
        r#"{
            "id":"custom_sloop",
            "displayName":"Custom Sloop",
            "description":"custom test vessel",
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

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "init"])
        .assert()
        .success();

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "vessel", "list"])
        .assert()
        .success()
        .stdout(predicate::str::contains("custom_sloop - Custom Sloop"))
        .stdout(predicate::str::contains("[locked]"));

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args([
            "--home",
            home.to_str().unwrap(),
            "shop",
            "buy",
            "custom_sloop",
        ])
        .assert()
        .success()
        .stdout(predicate::str::contains("purchased custom_sloop"));

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args([
            "--home",
            home.to_str().unwrap(),
            "vessel",
            "set",
            "custom_sloop",
        ])
        .assert()
        .success()
        .stdout(predicate::str::contains("vessel equipped"));

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "status", "--json"])
        .assert()
        .success()
        .stdout(predicate::str::contains(
            "\"current_vessel\": \"custom_sloop\"",
        ));
}
