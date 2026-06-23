use std::path::Path;

use anyhow::{Result, bail};
use serde::{Deserialize, Serialize};

use crate::vessels::manifest::VesselManifest;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum CatalogItemKind {
    Vessel,
    Skin,
    Decoration,
    Animation,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct CatalogItem {
    pub id: String,
    pub kind: CatalogItemKind,
    pub rarity: String,
    pub price: i32,
    pub unlock: Option<serde_json::Value>,
    pub asset_path: String,
    #[serde(default)]
    pub tags: Vec<String>,
    #[serde(default)]
    pub traits: serde_json::Value,
    #[serde(default)]
    pub effects: serde_json::Value,
}

#[derive(Debug, Clone, Deserialize)]
struct CatalogFile {
    items: Vec<CatalogItem>,
}

pub struct VesselCatalog {
    pub items: Vec<CatalogItem>,
    pub vessels: Vec<VesselManifest>,
}

impl VesselCatalog {
    pub fn load_default() -> Result<Self> {
        let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR"));
        Self::load_from_catalog(&root.join("assets/catalog.json"), root)
    }

    pub fn load_with_user_dir(user_dir: &Path) -> Result<Self> {
        let mut catalog = Self::load_default()?;
        if let Some(home) = user_dir.parent() {
            let user_catalog_path = home.join("catalog.json");
            if user_catalog_path.exists() {
                let user_catalog = Self::load_from_catalog(&user_catalog_path, home)?;
                for item in user_catalog.items {
                    if catalog.items.iter().any(|existing| existing.id == item.id) {
                        bail!(
                            "custom catalog item id conflicts with built-in item {}",
                            item.id
                        );
                    }
                    catalog.items.push(item);
                }
                for vessel in user_catalog.vessels {
                    if catalog
                        .vessels
                        .iter()
                        .any(|existing| existing.id == vessel.id)
                    {
                        bail!(
                            "custom vessel id conflicts with built-in vessel {}",
                            vessel.id
                        );
                    }
                    catalog.vessels.push(vessel);
                }
            }
        }
        catalog.items.sort_by(|a, b| a.id.cmp(&b.id));
        catalog.vessels.sort_by(|a, b| a.id.cmp(&b.id));
        Ok(catalog)
    }

    fn load_from_catalog(path: &Path, root: &Path) -> Result<Self> {
        let text = std::fs::read_to_string(path)?;
        let file: CatalogFile = serde_json::from_str(&text)?;
        let mut vessels = Vec::new();
        for item in &file.items {
            validate_item(item)?;
            if item.kind == CatalogItemKind::Vessel {
                let manifest_path = safe_join(root, &item.asset_path)?;
                let manifest = VesselManifest::load(&manifest_path)?;
                if manifest.id != item.id {
                    bail!(
                        "catalog item {} points to vessel manifest {}",
                        item.id,
                        manifest.id
                    );
                }
                vessels.push(manifest);
            }
        }
        Ok(Self {
            items: file.items,
            vessels,
        })
    }

    pub fn find(&self, id: &str) -> Option<&VesselManifest> {
        self.vessels.iter().find(|v| v.id == id)
    }

    pub fn find_item(&self, id: &str) -> Option<&CatalogItem> {
        self.items.iter().find(|item| item.id == id)
    }

    pub fn vessel_items(&self) -> impl Iterator<Item = &CatalogItem> {
        self.items
            .iter()
            .filter(|item| item.kind == CatalogItemKind::Vessel)
    }
}

fn validate_item(item: &CatalogItem) -> Result<()> {
    if item.id.trim().is_empty() {
        bail!("catalog item id cannot be empty");
    }
    if item.price < 0 {
        bail!("catalog item {} has negative price", item.id);
    }
    if item.rarity.trim().is_empty() {
        bail!("catalog item {} has empty rarity", item.id);
    }
    if let Some(unlock) = &item.unlock {
        let ty = unlock
            .get("type")
            .and_then(|value| value.as_str())
            .unwrap_or("always");
        if ty != "always" {
            bail!("catalog item {} uses unsupported unlock type {ty}", item.id);
        }
    }
    Ok(())
}

fn safe_join(root: &Path, relative: &str) -> Result<std::path::PathBuf> {
    let path = Path::new(relative);
    if path.is_absolute()
        || path
            .components()
            .any(|component| matches!(component, std::path::Component::ParentDir))
    {
        bail!("catalog assetPath must stay inside catalog root");
    }
    Ok(root.join(path))
}
