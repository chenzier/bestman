use std::path::Path;

use anyhow::Result;

use crate::vessels::manifest::VesselManifest;

pub struct VesselCatalog {
    pub vessels: Vec<VesselManifest>,
}

impl VesselCatalog {
    pub fn load_default() -> Result<Self> {
        let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR"));
        let manifest = root.join("assets/vessels/starter_sloop/vessel.json");
        Ok(Self {
            vessels: vec![VesselManifest::load(&manifest)?],
        })
    }

    pub fn load_with_user_dir(user_dir: &Path) -> Result<Self> {
        let mut catalog = Self::load_default()?;
        if user_dir.is_dir() {
            for entry in std::fs::read_dir(user_dir)? {
                let entry = entry?;
                if !entry.file_type()?.is_dir() {
                    continue;
                }
                let manifest_path = entry.path().join("vessel.json");
                if manifest_path.exists() {
                    let manifest = VesselManifest::load(&manifest_path)?;
                    if let Some(pos) = catalog.vessels.iter().position(|v| v.id == manifest.id) {
                        catalog.vessels[pos] = manifest;
                    } else {
                        catalog.vessels.push(manifest);
                    }
                }
            }
        }
        catalog.vessels.sort_by(|a, b| a.id.cmp(&b.id));
        Ok(catalog)
    }

    pub fn find(&self, id: &str) -> Option<&VesselManifest> {
        self.vessels.iter().find(|v| v.id == id)
    }
}
