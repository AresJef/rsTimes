//! Select public Python C APIs with PyO3's interpreter-version configuration.

/// Keep interpreter-specific layout and Unicode data tied to the target Python.
fn main() -> Result<(), Box<dyn std::error::Error>> {
    pyo3_build_config::use_pyo3_cfgs();
    {
        // Capture the target interpreter's exact public str.isalpha rule once
        // at build time. Both Python and native UTF8 readers then use the same
        // immutable Rust data; Polars workers never call a CPython classifier.
        let interpreter = pyo3_build_config::get();
        let python = interpreter.executable().unwrap_or("python");
        let script = r#"
import unicodedata
blocks = []
indices = []
lookup = {}
for start in range(0, 0x110000, 256):
    words = [0, 0, 0, 0]
    for offset in range(256):
        if chr(start + offset).isalpha():
            words[offset // 64] |= 1 << (offset % 64)
    words = tuple(words)
    if words not in lookup:
        lookup[words] = len(blocks)
        blocks.append(words)
    indices.append(lookup[words])
assert len(blocks) < 65536
print('pub(super) const LETTER_BLOCKS: &[u16; 4352] = &[')
for offset in range(0, len(indices), 32):
    print(','.join(map(str, indices[offset:offset+32])) + ',')
print('];')
print('pub(super) const LETTER_BITS: &[[u64; 4]] = &[')
for words in blocks:
    print('[' + ','.join(map(str, words)) + '],')
print('];')
starts = [code for code in range(0x110000) if chr(code).isdecimal() and unicodedata.decimal(chr(code)) == 0]
assert all(unicodedata.decimal(chr(start + digit)) == digit for start in starts for digit in range(10))
print('pub(super) const DECIMAL_STARTS: &[u32] = &[' + ','.join(map(str, starts)) + '];')
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
