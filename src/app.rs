use std::path::PathBuf;

use anyhow::Result;

use crate::config::BestmanConfig;
use crate::events::EventStore;
use crate::projection::Projection;

pub struct AppPaths {
    pub home: PathBuf,
    pub config: PathBuf,
    pub events: PathBuf,
    pub db: PathBuf,
    pub cache: PathBuf,
}

impl AppPaths {
    pub fn from_home(home: PathBuf) -> Self {
        Self {
            config: home.join("config.toml"),
            events: home.join("events.jsonl"),
            db: home.join("bestman.db"),
            cache: home.join("cache"),
            home,
        }
    }
}

pub struct BestmanApp {
    pub paths: AppPaths,
    pub config: BestmanConfig,
    pub store: EventStore,
    pub projection: Projection,
}

impl BestmanApp {
    pub fn open(paths: AppPaths) -> Result<Self> {
        std::fs::create_dir_all(&paths.home)?;
        std::fs::create_dir_all(&paths.cache)?;
        let config = BestmanConfig::load_or_default(&paths.config)?;
        let store = EventStore::open(paths.events.clone())?;
        let projection = Projection::open(&paths.db)?;
        Ok(Self {
            paths,
            config,
            store,
            projection,
        })
    }

    pub fn rebuild_projection(&mut self) -> Result<()> {
        self.projection.rebuild(self.store.read_all()?)
    }
}
