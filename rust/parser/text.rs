//! Borrowed CPython Unicode storage, including lone surrogate code points.
use pyo3::{ffi, prelude::*, types::PyString};
use std::{ffi::c_void, marker::PhantomData};

/// Decode four little-endian ASCII digits with one checked native word.
/// The two masks reject bytes outside 0..9 before combining decimal pairs.
#[inline(always)]
fn ascii_four(word: u32) -> Option<i32> {
    let digits = word.wrapping_sub(0x3030_3030);
    if (word.wrapping_add(0x4646_4646) | digits) & 0x8080_8080 != 0 {
        return None;
    }
    let pairs = (digits & 0x00ff_00ff) * 10 + ((digits >> 8) & 0x00ff_00ff);
    Some(((pairs & 0xffff) * 100 + (pairs >> 16)) as i32)
}

pub(super) struct TextView<'a> {
    data: *const c_void,
    kind: u32,
    length: usize,
    owner: PhantomData<&'a Bound<'a, PyString>>,
}

impl<'a> TextView<'a> {
    pub(super) fn new(input: &'a Bound<'_, PyString>) -> PyResult<Self> {
        // SAFETY: PyString is ready immutable Unicode; the borrowed Bound keeps
        // its storage alive even while configuration callbacks execute.
        unsafe {
            Ok(Self {
                data: ffi::PyUnicode_DATA(input.as_ptr()),
                kind: ffi::PyUnicode_KIND(input.as_ptr()),
                length: ffi::PyUnicode_GET_LENGTH(input.as_ptr()) as usize,
                owner: PhantomData,
            })
        }
    }
    #[inline]
    pub(super) fn len(&self) -> usize {
        self.length
    }
    /// Limit the view while retaining its borrowed Python owner.
    pub(super) fn truncate(&mut self, end: usize) {
        self.length = end.min(self.length);
    }
    #[inline]
    pub(super) fn get(&self, index: usize) -> u32 {
        if index >= self.length {
            return 0;
        }
        // SAFETY: index is checked; CPython's kind selects the actual storage.
        unsafe {
            match self.kind {
                1 => *self.data.cast::<u8>().add(index) as u32,
                2 => *self.data.cast::<u16>().add(index) as u32,
                4 => *self.data.cast::<u32>().add(index),
                _ => 0,
            }
        }
    }
    /// Read one ASCII-digit run, retaining at most the requested precision.
    /// The returned position consumes all digits, including discarded tails.
    #[inline(always)]
    pub(super) fn fractional_digits(&self, start: usize, digits: u32) -> (i32, u32, usize) {
        let (mut value, mut count, mut pos) = (0, 0, start);
        if start >= self.length {
            return (value, count, pos);
        }
        if self.kind == 1 {
            // SAFETY: start is in bounds, kind 1 establishes one-byte Unicode
            // storage, and the immutable Python owner remains borrowed under
            // the GIL for the complete lifetime of this local slice.
            let bytes = unsafe { std::slice::from_raw_parts(self.data.cast::<u8>(), self.length) };
            for &ch in &bytes[start..] {
                if !ch.is_ascii_digit() {
                    break;
                }
                if count < digits {
                    value = value * 10 + i32::from(ch - b'0');
                    count += 1;
                }
                pos += 1;
            }
        } else {
            while pos < self.length {
                let ch = self.get(pos);
                if !digit(ch) {
                    break;
                }
                if count < digits {
                    value = value * 10 + (ch - 48) as i32;
                    count += 1;
                }
                pos += 1;
            }
        }
        (value, count, pos)
    }
    pub(super) fn range(&self, start: usize, end: usize) -> Vec<u32> {
        (start..end.min(self.length)).map(|i| self.get(i)).collect()
    }
    #[inline(always)]
    pub(super) fn number(&self, start: usize, count: usize, min: i32, max: i32) -> i32 {
        if start.checked_add(count).is_none_or(|end| end > self.length) {
            return -1;
        }
        let mut value = 0;
        if self.kind == 1 {
            if count == 4 {
                // SAFETY: the full four-byte span was checked above; kind 1
                // proves the storage width and the borrowed owner stays live.
                let word = unsafe {
                    self.data
                        .cast::<u8>()
                        .add(start)
                        .cast::<u32>()
                        .read_unaligned()
                };
                let Some(number) = ascii_four(u32::from_le(word)) else {
                    return -1;
                };
                return if (min..=max).contains(&number) {
                    number
                } else {
                    -1
                };
            }
            // SAFETY: ready CPython Unicode of kind 1 has one-byte storage.
            // The complete range is checked above and the TextView borrow
            // keeps the immutable owner alive throughout these reads.
            for index in start..start + count {
                let ch = unsafe { *self.data.cast::<u8>().add(index) };
                if !ch.is_ascii_digit() {
                    return -1;
                }
                value = value * 10 + i32::from(ch - b'0');
            }
        } else {
            for i in start..start + count {
                let ch = self.get(i);
                if !digit(ch) {
                    return -1;
                }
                value = value * 10 + (ch - 48) as i32;
            }
        }
        if value >= min && value <= max {
            value
        } else {
            -1
        }
    }
}

#[cfg(test)]
mod ascii_tests {
    use super::ascii_four;

    #[test]
    fn four_digit_reader_preserves_decimal_values_and_rejects_other_bytes() {
        for number in 0..10_000 {
            let text = format!("{number:04}");
            let bytes: [u8; 4] = text.as_bytes().try_into().unwrap();
            assert_eq!(ascii_four(u32::from_le_bytes(bytes)), Some(number));
        }
        for template in [*b"0000", *b"9999", *b"1234", *b"8080"] {
            for position in 0..4 {
                for byte in 0..=u8::MAX {
                    let mut bytes = template;
                    bytes[position] = byte;
                    let expected = bytes.iter().all(u8::is_ascii_digit).then(|| {
                        bytes
                            .iter()
                            .fold(0, |value, byte| value * 10 + i32::from(byte - b'0'))
                    });
                    assert_eq!(ascii_four(u32::from_le_bytes(bytes)), expected);
                }
            }
        }
    }
}

#[inline]
pub(super) fn digit(ch: u32) -> bool {
    (48..=57).contains(&ch)
}
#[inline]
pub(super) fn space(ch: u32) -> bool {
    ch <= 32 || ch == 127
}
#[inline]
pub(super) fn ascii_letter(ch: u32) -> bool {
    (65..=90).contains(&ch) || (97..=122).contains(&ch)
}
unsafe extern "C" {
    fn _PyUnicode_IsAlpha(ch: u32) -> std::ffi::c_int;
}
#[inline]
pub(super) fn alpha(ch: u32) -> bool {
    ascii_letter(ch) || (ch > 127 && unsafe { _PyUnicode_IsAlpha(ch) != 0 })
}

/// Native normalized code points and token boundaries. A scan allocates the
/// arena once instead of allocating and growing a separate Vec for each token.
pub(super) struct Tokens {
    arena: Vec<u32>,
    ranges: Vec<std::ops::Range<usize>>,
    pub(super) region_candidate: bool,
}

impl Tokens {
    #[inline]
    pub(super) fn len(&self) -> usize {
        self.ranges.len()
    }
    #[inline]
    pub(super) fn get(&self, index: usize) -> Option<&[u32]> {
        self.ranges
            .get(index)
            .map(|range| &self.arena[range.clone()])
    }
    #[inline]
    fn push_single(&mut self, ch: u32) {
        let start = self.arena.len();
        self.arena.push(ch);
        self.ranges.push(start..start + 1);
    }
}

/// Frozen timelex state transitions, with native normalized token storage.
pub(super) fn tokenize(input: &TextView<'_>, mut pos: usize) -> Tokens {
    let remaining = input.len().saturating_sub(pos);
    // Normalization can only shorten the input. Each source code point is
    // written once; splitting records ranges within this immutable arena.
    let mut tokens = Tokens {
        arena: Vec::with_capacity(remaining),
        ranges: Vec::with_capacity(remaining.min(32)),
        region_candidate: false,
    };
    while pos < input.len() && space(input.get(pos)) {
        pos += 1;
    }
    while pos < input.len() {
        let first = input.get(pos);
        if space(first) {
            while pos < input.len() && space(input.get(pos)) {
                pos += 1;
            }
            tokens.push_single(32);
            continue;
        }
        let mut state = if digit(first) {
            1
        } else if alpha(first) {
            3
        } else {
            0
        };
        if state == 0 {
            if first == 93 || (first == 47 && ascii_letter(input.get(pos + 1))) {
                tokens.region_candidate = true;
            }
            tokens.push_single(first);
            pos += 1;
            continue;
        }
        let start = tokens.arena.len();
        tokens.arena.push(first);
        pos += 1;
        let (mut dots, mut commas, mut dot_end, mut comma_end) = (0, 0, false, false);
        while pos < input.len() {
            let ch = input.get(pos);
            let accepted = match state {
                1 => {
                    if digit(ch) {
                        true
                    } else if ch == 46 || (ch == 44 && dots == 0 && commas == 0) {
                        state = 2;
                        true
                    } else {
                        false
                    }
                }
                2 => {
                    if digit(ch) {
                        true
                    } else if dot_end && alpha(ch) {
                        state = 4;
                        true
                    } else {
                        ch == 46
                    }
                }
                3 => {
                    if alpha(ch) {
                        true
                    } else if ch == 46 {
                        state = 4;
                        true
                    } else {
                        false
                    }
                }
                _ => {
                    if alpha(ch) {
                        true
                    } else if dot_end && digit(ch) {
                        state = 2;
                        true
                    } else {
                        ch == 46
                    }
                }
            };
            if !accepted {
                break;
            }
            if ch == 46 {
                dots += 1;
            } else if ch == 44 {
                commas += 1;
            }
            dot_end = ch == 46;
            comma_end = ch == 44;
            tokens.arena.push(ch);
            pos += 1;
        }
        let end = tokens.arena.len();
        if state == 4 || dot_end || comma_end || dots > 1 || commas > 1 {
            let mut sub_start = start;
            for index in start..end {
                let ch = tokens.arena[index];
                if ch == 46 || ch == 44 {
                    if sub_start < index {
                        tokens.ranges.push(sub_start..index);
                    }
                    tokens.ranges.push(index..index + 1);
                    sub_start = index + 1;
                }
            }
            if sub_start < end {
                tokens.ranges.push(sub_start..end);
            }
        } else {
            if state == 2 && commas == 1 && dots == 0 {
                for ch in &mut tokens.arena[start..end] {
                    if *ch == 44 {
                        *ch = 46;
                    }
                }
            }
            tokens.ranges.push(start..end);
        }
    }
    tokens
}
