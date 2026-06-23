use assert_cmd::Command;
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
        .stdout(predicate::str::contains("Starter Sloop"))
        .stdout(predicate::str::contains("Task 深蹲 3x15"))
        .stdout(predicate::str::contains("Ready for today's training."))
        .stdout(predicate::str::contains("Captain's Log"))
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
        .stdout(predicate::str::contains("\u{1b}_Ga=T,f=100,i=7007"))
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
fn cli_loads_and_sets_custom_vessel() {
    let dir = tempdir().unwrap();
    let home = dir.path().join("home");
    let custom_dir = home.join("vessels/custom_sloop");
    std::fs::create_dir_all(&custom_dir).unwrap();
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
        .stdout(predicate::str::contains("custom_sloop - Custom Sloop"));

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
        .success();

    Command::cargo_bin("bestman-rs")
        .unwrap()
        .args(["--home", home.to_str().unwrap(), "status", "--json"])
        .assert()
        .success()
        .stdout(predicate::str::contains(
            "\"current_vessel\": \"custom_sloop\"",
        ));
}
