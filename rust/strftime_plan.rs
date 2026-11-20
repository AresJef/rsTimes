//! A small shared output plan: exact fraction nodes and preserved system syntax.
use serde::{Deserialize, Serialize};
use std::fmt::Write;
#[derive(Clone, Serialize, Deserialize)]
enum Node {
    Literal(String),
    Codepoints(Vec<u32>),
    Field(u8),
    Fraction { digits: u8, dot: bool },
    System(String),
}

/// Common formats keep their UTF8 buffer; Python-only literals upgrade once.
pub(crate) enum SystemFormat {
    Utf8(String),
    Codepoints(Vec<u32>),
}
impl SystemFormat {
    fn push(&mut self, value: char) {
        match self {
            Self::Utf8(out) => out.push(value),
            Self::Codepoints(out) => out.push(u32::from(value)),
        }
    }
    fn push_str(&mut self, value: &str) {
        match self {
            Self::Utf8(out) => out.push_str(value),
            Self::Codepoints(out) => out.extend(value.chars().map(u32::from)),
        }
    }
    fn push_points(&mut self, value: &[u32]) {
        match self {
            Self::Utf8(out) => {
                let mut points: Vec<_> = out.chars().map(u32::from).collect();
                points.extend_from_slice(value);
                *self = Self::Codepoints(points);
            }
            Self::Codepoints(out) => out.extend_from_slice(value),
        }
    }
}
impl std::fmt::Write for SystemFormat {
    fn write_str(&mut self, value: &str) -> std::fmt::Result {
        self.push_str(value);
        Ok(())
    }
    fn write_char(&mut self, value: char) -> std::fmt::Result {
        self.push(value);
        Ok(())
    }
}
#[derive(Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct Plan {
    version: u8,
    nodes: Vec<Node>,
    modified: bool,
}
impl Plan {
    pub(crate) fn parse_points(format: impl Iterator<Item = u32>) -> Result<Self, String> {
        let mut nodes = Vec::new();
        let mut modified = false;
        let mut chars = format.peekable();
        let mut text = String::new();
        while let Some(c) = chars.next() {
            if c != 37 {
                if let Some(c) = char::from_u32(c) {
                    text.push(c);
                } else {
                    if !text.is_empty() {
                        nodes.push(Node::Literal(std::mem::take(&mut text)));
                    }
                    nodes.push(Node::Codepoints(vec![c]));
                }
                continue;
            }
            if !text.is_empty() {
                nodes.push(Node::Literal(std::mem::take(&mut text)));
            }
            let Some(c) = chars.next() else {
                nodes.push(Node::System("%".into()));
                break;
            };
            if c == 102 {
                modified = true;
                nodes.push(Node::Fraction {
                    digits: 0,
                    dot: false,
                });
            } else if c == 46 {
                modified = true;
                let digit = chars
                    .next()
                    .and_then(char::from_u32)
                    .and_then(|v| v.to_digit(10))
                    .filter(|_| chars.peek() == Some(&102))
                    .ok_or("fraction precision must use exactly %.0f through %.9f")?;
                chars.next();
                if digit != 0 {
                    nodes.push(Node::Fraction {
                        digits: digit as u8,
                        dot: true,
                    });
                }
            } else if c <= 127 && b"YymdHIMSjwuUWGVzZ%".contains(&(c as u8)) {
                nodes.push(Node::Field(c as u8));
            } else if let Some(c) = char::from_u32(c) {
                nodes.push(Node::System(format!("%{c}")));
            } else {
                nodes.push(Node::Codepoints(vec![37, c]));
            }
        }
        if !text.is_empty() {
            nodes.push(Node::Literal(text));
        }
        Ok(Self {
            version: 1,
            nodes,
            modified,
        })
    }
    #[cfg(test)]
    fn parse(format: &str) -> Result<Self, String> {
        Self::parse_points(format.chars().map(u32::from))
    }
    pub(crate) fn validate(&self) -> Result<(), String> {
        if self.version != 1 {
            return Err("unsupported strftime preparation version".into());
        }
        for node in &self.nodes {
            match node {
                Node::Codepoints(points) if points.iter().any(|&point| point > 0x10ffff) => {
                    return Err("invalid prepared Unicode code point".into());
                }
                Node::Fraction { digits, dot } if *digits > 9 || (*digits == 0 && *dot) => {
                    return Err("invalid fraction preparation".into());
                }
                Node::Field(code) if !b"YymdHIMSjwuUWGVzZ%".contains(code) => {
                    return Err("invalid prepared numeric format".into());
                }
                _ => {}
            }
        }
        Ok(())
    }
    pub(crate) fn native(&self) -> bool {
        !self
            .nodes
            .iter()
            .any(|v| matches!(v, Node::System(_) | Node::Codepoints(_)))
    }
    /// Universally supported system numeric forms, without locale or platform
    /// extensions. Small/wide years and unusual zone names are host concerns.
    pub(crate) fn system_numeric(&self) -> bool {
        self.nodes.iter().all(|node| match node {
            Node::Literal(text) => text.is_ascii() && !text.contains('\0'),
            Node::Field(code) => b"YymdHIMSjwUWzZ%".contains(code),
            Node::Fraction { .. } => true,
            Node::System(_) | Node::Codepoints(_) => false,
        })
    }
    pub(crate) fn modified(&self) -> bool {
        self.modified
    }
    pub(crate) fn has_fraction(&self) -> bool {
        self.nodes
            .iter()
            .any(|v| matches!(v, Node::Fraction { .. }))
    }
    pub(crate) fn needs_wall(&self) -> bool {
        self.nodes
            .iter()
            .any(|v| matches!(v,Node::Field(c)if !b"zZ%".contains(c)))
    }
    pub(crate) fn needs_offset(&self) -> bool {
        self.nodes.iter().any(|v| matches!(v, Node::Field(b'z')))
    }
    pub(crate) fn needs_name(&self) -> bool {
        self.nodes.iter().any(|v| matches!(v, Node::Field(b'Z')))
    }
    fn fraction(out: &mut impl Write, nanos: u32, digits: u8, dot: bool, default: u8) {
        let digits = if digits == 0 { default } else { digits };
        if dot {
            let _ = out.write_char('.');
        }
        let _ = write!(
            out,
            "{:0width$}",
            nanos / 10_u32.pow(9 - u32::from(digits)),
            width = usize::from(digits)
        );
    }
    pub(crate) fn system_format(&self, nanos: u32, default: u8) -> SystemFormat {
        let mut out = SystemFormat::Utf8(String::new());
        for node in &self.nodes {
            match node {
                Node::Literal(text) => {
                    for c in text.chars() {
                        out.push(c);
                        if c == '%' {
                            out.push('%');
                        }
                    }
                }
                Node::Field(code) => {
                    out.push('%');
                    out.push(char::from(*code));
                }
                Node::Fraction { digits, dot } => {
                    Self::fraction(&mut out, nanos, *digits, *dot, default)
                }
                Node::System(text) => out.push_str(text),
                Node::Codepoints(points) => out.push_points(points),
            }
        }
        out
    }
    pub(crate) fn render_into(
        &self,
        wall: i128,
        default: u8,
        offset: Option<i32>,
        name: Option<&str>,
        out: &mut String,
    ) -> Result<(), crate::calendar_query::Error> {
        use crate::calendar_query::{Error, fact};
        out.clear();
        let mut cache = None;
        macro_rules! number {
            ($value:expr,$width:expr) => {{
                let _ = write!(out, "{:0width$}", $value, width = $width);
            }};
        }
        for node in &self.nodes {
            match node {
                Node::Literal(text) => out.push_str(text),
                Node::Fraction { digits, dot } => Self::fraction(
                    out,
                    wall.rem_euclid(1_000_000_000) as u32,
                    *digits,
                    *dot,
                    default,
                ),
                Node::System(_) | Node::Codepoints(_) => {
                    return Err(Error::Internal("system formats require the eager adapter"));
                }
                Node::Field(code) => match code {
                    b'Y' | b'G' => {
                        let value = if *code == b'Y' {
                            fact::<20>(wall, None, &mut cache)?
                        } else {
                            fact::<0>(wall, None, &mut cache)?
                        };
                        if value < 0 {
                            out.push('-');
                        }
                        number!(value.unsigned_abs(), 4);
                    }
                    b'y' => number!(fact::<20>(wall, None, &mut cache)?.rem_euclid(100), 2),
                    b'm' => number!(fact::<21>(wall, None, &mut cache)?, 2),
                    b'd' => number!(fact::<22>(wall, None, &mut cache)?, 2),
                    b'H' => number!(fact::<23>(wall, None, &mut cache)?, 2),
                    b'I' => {
                        let hour = fact::<23>(wall, None, &mut cache)? % 12;
                        number!(if hour == 0 { 12 } else { hour }, 2);
                    }
                    b'M' => number!(fact::<24>(wall, None, &mut cache)?, 2),
                    b'S' => number!(fact::<25>(wall, None, &mut cache)?, 2),
                    b'j' => number!(fact::<29>(wall, None, &mut cache)?, 3),
                    b'w' => number!((fact::<28>(wall, None, &mut cache)? + 1) % 7, 1),
                    b'u' => number!(fact::<28>(wall, None, &mut cache)? + 1, 1),
                    b'V' => number!(fact::<1>(wall, None, &mut cache)?, 2),
                    b'U' | b'W' => {
                        let yday = fact::<29>(wall, None, &mut cache)?;
                        let wd = fact::<28>(wall, None, &mut cache)?;
                        let wd = if *code == b'U' { (wd + 1) % 7 } else { wd };
                        number!((yday + 6 - wd) / 7, 2);
                    }
                    b'z' => {
                        if let Some(offset) = offset {
                            out.push(if offset < 0 { '-' } else { '+' });
                            let seconds = offset.unsigned_abs();
                            number!(seconds / 3600, 2);
                            number!(seconds / 60 % 60, 2);
                            if seconds % 60 != 0 {
                                number!(seconds % 60, 2);
                            }
                        }
                    }
                    b'Z' => {
                        if let Some(name) = name {
                            out.push_str(name);
                        }
                    }
                    b'%' => out.push('%'),
                    _ => return Err(Error::Internal("invalid numeric format directive")),
                },
            }
        }
        Ok(())
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn python_only_literal_keeps_codepoints_and_fraction_in_host_plan() {
        let input = "%Y|"
            .chars()
            .map(u32::from)
            .chain([0xd800])
            .chain("|%.3f|%%f".chars().map(u32::from));
        let plan = Plan::parse_points(input).unwrap();
        assert!(!plan.native());
        assert!(plan.validate().is_ok());
        let SystemFormat::Codepoints(actual) = plan.system_format(123_456_789, 9) else {
            panic!("Python literal must retain its code point");
        };
        let expected: Vec<_> = "%Y|"
            .chars()
            .map(u32::from)
            .chain([0xd800])
            .chain("|.123|%%f".chars().map(u32::from))
            .collect();
        assert_eq!(actual, expected);
        let mut invalid = plan.clone();
        invalid.nodes.push(Node::Codepoints(vec![0x110000]));
        assert!(invalid.validate().is_err());
    }
    #[test]
    fn rendering_into_scratch_overwrites_previous_value_and_keeps_exact_fraction() {
        let plan = Plan::parse("%Y %.9f %Z").unwrap();
        let mut out = "not output".to_owned();
        plan.render_into(-1, 9, Some(0), Some("first"), &mut out)
            .unwrap();
        let previous = out.clone();
        plan.render_into(0, 6, None, Some("second name"), &mut out)
            .unwrap();
        assert_eq!(previous, "1969 .999999999 first");
        assert_eq!(out, "1970 .000000000 second name");
    }
    #[test]
    fn numeric_plan_runs_on_an_unattached_native_thread() {
        std::thread::spawn(|| {
            let plan = Plan::parse("%Y-%m-%d %H:%M:%S%.9f %G %V %u %z %Z").unwrap();
            let mut out = String::new();
            plan.render_into(-1, 9, Some(0), Some("UTC"), &mut out)
                .unwrap();
            assert_eq!(out, "1969-12-31 23:59:59.999999999 1970 01 3 +0000 UTC");
        })
        .join()
        .unwrap();
    }
    #[test]
    fn fractional_plan_is_exact_and_system_escapes_remain_literal() {
        let plan = Plan::parse("%%f %%.3f %f %.0f %.1f %.9f").unwrap();
        let mut out = String::new();
        plan.render_into(123456789, 9, None, None, &mut out)
            .unwrap();
        assert_eq!(out, "%f %.3f 123456789  .1 .123456789");
        assert_eq!(Plan::parse("%.0f").unwrap().nodes.len(), 0);
        assert!(!Plan::parse("%A %.9f").unwrap().native());
        for bad in ["%.10f", "%.-1f", "%.f", "%.3g"] {
            assert!(Plan::parse(bad).is_err());
        }
    }

    #[test]
    fn system_numeric_subset_does_not_capture_platform_locale_or_literal_nul() {
        for format in [
            "%Y-%m-%d %H:%M:%S.%f",
            "%j %w %U %W %I %z %Z%.0f",
            "%%f|%.9f",
        ] {
            assert!(Plan::parse(format).unwrap().system_numeric(), "{format}");
        }
        for format in ["%G %V %u %.3f", "%A %.9f", "%_d %f", "日期%f", "a\0%f"] {
            assert!(!Plan::parse(format).unwrap().system_numeric(), "{format}");
        }
    }
}
