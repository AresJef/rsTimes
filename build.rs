//! Select public Python C APIs with PyO3's interpreter-version configuration.

/// Keep interpreter-specific layout and Unicode data tied to the target Python.
fn main() -> Result<(), Box<dyn std::error::Error>> {
    pyo3_build_config::use_pyo3_cfgs();
    if std::env::var("CARGO_CFG_TARGET_OS")? == "windows" {
        // Windows does not export CPython's private Unicode classification
        // function. Generate its exact public str.isalpha rule at build time;
        // parsing still uses only native integer lookups at runtime.
        let interpreter = pyo3_build_config::get();
        let python = interpreter.executable.as_deref().unwrap_or("python");
        let script = r#"
ranges = []
start = None
for point in range(128, 0x110000):
    if chr(point).isalpha():
        if start is None:
            start = point
    elif start is not None:
        ranges.append((start, point - 1))
        start = None
if start is not None:
    ranges.append((start, 0x10ffff))
print('pub(super) const LETTERS: &[(u32, u32)] = &[')
for first, last in ranges:
    print(f'({first}, {last}),')
print('];')
"#;
        let output = std::process::Command::new(python)
            .args(["-I", "-c", script])
            .output()?;
        if !output.status.success() {
            return Err(format!(
                "Target Python Unicode data failed: {}",
                String::from_utf8_lossy(&output.stderr)
            )
            .into());
        }
        let path = std::path::PathBuf::from(std::env::var_os("OUT_DIR").ok_or("Missing OUT_DIR")?)
            .join("python_unicode_letters.rs");
        std::fs::write(path, output.stdout)?;
    }
    Ok(())
}
