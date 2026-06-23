# Python legacy prototype

This directory contains the original Python prototype for bestman.

The active product direction is now the Rust implementation at the repository root:

```bash
cargo run -- --home /tmp/bestman-demo init
cargo run -- --home /tmp/bestman-demo tui --live --images
```

Use this Python package as historical reference only. New product work should go into the Rust core unless there is an explicit decision to revive a specific Python component.

Legacy Python entry point, if needed:

```bash
uv run bestman --help
```
