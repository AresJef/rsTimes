//! A small shared output plan: exact fraction nodes and preserved system syntax.
use serde::{Deserialize, Serialize};
use std::fmt::Write;
#[derive(Clone, Serialize, Deserialize)]
enum Node {
    Literal(String),
    Field(u8),
    Fraction { digits: u8, dot: bool },
    System(String),
}
#[derive(Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct Plan {
    version: u8,
    nodes: Vec<Node>,
    modified: bool,
}
impl Plan {
    pub(crate) fn parse(format: &str) -> Result<Self, String> {
        let mut nodes = Vec::new();
        let mut modified = false;
        let mut chars = format.chars().peekable();
        let mut text = String::new();
        while let Some(c) = chars.next() {
            if c != '%' {
                text.push(c);
                continue;
            }
            if !text.is_empty() {
                nodes.push(Node::Literal(std::mem::take(&mut text)));
            }
            let Some(c) = chars.next() else {
                nodes.push(Node::System("%".into()));
                break;
            };
            if c == 'f' {
                modified = true;
                nodes.push(Node::Fraction {
                    digits: 0,
                    dot: false,
                });
            } else if c == '.' {
                modified = true;
                let digit = chars
                    .next()
                    .and_then(|v| v.to_digit(10))
                    .filter(|_| chars.peek() == Some(&'f'))
                    .ok_or("fraction precision must use exactly %.0f through %.9f")?;
                chars.next();
                if digit != 0 {
                    nodes.push(Node::Fraction {
                        digits: digit as u8,
                        dot: true,
                    });
                }
            } else if c.is_ascii() && b"YymdHIMSjwuUWGVzZ%".contains(&(c as u8)) {
                nodes.push(Node::Field(c as u8));
            } else {
                nodes.push(Node::System(format!("%{c}")));
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
    pub(crate) fn validate(&self) -> Result<(), String> {
        if self.version != 1 {
            return Err("unsupported strftime preparation version".into());
        }
        for node in &self.nodes {
            match node {
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
        !self.nodes.iter().any(|v| matches!(v, Node::System(_)))
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
    fn fraction(out: &mut String, nanos: u32, digits: u8, dot: bool, default: u8) {
        let digits = if digits == 0 { default } else { digits };
        if dot {
            out.push('.');
        }
        let _ = write!(
            out,
            "{:0width$}",
            nanos / 10_u32.pow(9 - u32::from(digits)),
            width = usize::from(digits)
        );
    }
    pub(crate) fn system_format(&self, nanos: u32, default: u8) -> String {
        let mut out = String::new();
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
            }
        }
        out
    }
    pub(crate) fn render(
        &self,
        wall: i128,
        default: u8,
        offset: Option<i32>,
        name: Option<&str>,
    ) -> Result<String, crate::calendar_query::Error> {
        use crate::calendar_query::{Error, fact};
        let mut out = String::new();
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
                    &mut out,
                    wall.rem_euclid(1_000_000_000) as u32,
                    *digits,
                    *dot,
                    default,
                ),
                Node::System(_) => {
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
        Ok(out)
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn numeric_plan_runs_on_an_unattached_native_thread() {
        std::thread::spawn(|| {
            let plan = Plan::parse("%Y-%m-%d %H:%M:%S%.9f %G %V %u %z %Z").unwrap();
            assert_eq!(
                plan.render(-1, 9, Some(0), Some("UTC")).unwrap(),
                "1969-12-31 23:59:59.999999999 1970 01 3 +0000 UTC"
            );
        })
        .join()
        .unwrap();
    }
    #[test]
    fn fractional_plan_is_exact_and_system_escapes_remain_literal() {
        let plan = Plan::parse("%%f %%.3f %f %.0f %.1f %.9f").unwrap();
        assert_eq!(
            plan.render(123456789, 9, None, None).unwrap(),
            "%f %.3f 123456789  .1 .123456789"
        );
        assert_eq!(Plan::parse("%.0f").unwrap().nodes.len(), 0);
        assert!(!Plan::parse("%A %.9f").unwrap().native());
        for bad in ["%.10f", "%.-1f", "%.f", "%.3g"] {
            assert!(Plan::parse(bad).is_err());
        }
    }
}
