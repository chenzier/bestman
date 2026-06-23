#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Route {
    pub width: u32,
    pub height: u32,
    pub points: Vec<(u32, u32)>,
}

impl Route {
    pub fn generate(total_days: u32) -> Self {
        let width = 50;
        let height = 14;
        let total = total_days.max(1);
        let mut points = Vec::with_capacity(total as usize);
        for i in 0..total {
            let t = if total <= 1 {
                0.0
            } else {
                i as f32 / (total - 1) as f32
            };
            let x = 2.0 + t * 46.0;
            let wave = (t * std::f32::consts::PI * 5.5).sin();
            let drift = (t * std::f32::consts::PI * 2.0).cos();
            let y = 7.0 + wave * 3.0 + drift * 1.5;
            points.push((x.round() as u32, y.round().clamp(1.0, 12.0) as u32));
        }
        Self {
            width,
            height,
            points,
        }
    }

    pub fn render_ascii(&self, position: u32) -> String {
        let mut grid = vec![vec!['~'; self.width as usize]; self.height as usize];
        for (idx, &(x, y)) in self.points.iter().enumerate() {
            if idx as u32 <= position && y < self.height && x < self.width {
                grid[y as usize][x as usize] = '.';
            }
        }
        if let Some(&(x, y)) = self.points.get(position.saturating_sub(1) as usize) {
            if y < self.height && x < self.width {
                grid[y as usize][x as usize] = 'S';
            }
        }
        grid.into_iter()
            .map(|row| row.into_iter().collect::<String>())
            .collect::<Vec<_>>()
            .join("\n")
    }
}

pub fn milestone_names(old_position: u32, new_position: u32, total_days: u32) -> Vec<String> {
    let marks = [
        (total_days / 4, "第一片远海"),
        (total_days / 2, "中途港湾"),
        (total_days * 3 / 4, "信风尽头"),
        (total_days, "新大陆"),
    ];
    marks
        .into_iter()
        .filter(|(day, _)| *day > 0 && old_position < *day && new_position >= *day)
        .map(|(_, name)| name.to_string())
        .collect()
}
