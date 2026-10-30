//! Exact, bounded binary accumulation for the accepted fixed-duration floats.
//!
//! f64 has no bit below 2^-1074. Inputs are individually signed64-bounded and
//! the largest coefficient is a week in ns (<2^50). Even all eight fixed fields
//! together require fewer than 1190 binary positions at this common scale.
//! Nineteen 64-bit limbs provide 1216 positions; no big-integer dependency or
//! Python operation is used. Integer-only constructors do not create this scratch.

use super::value::ValueError;

const LIMBS: usize = 19;
const FRACTION_BITS: usize = 1074;
const SIGNED64_BOUND: f64 = 9_223_372_036_854_775_808.0;

/// Round one exact binary contribution with an integer base, without scratch.
/// This is the same ns contract as the accumulator, specialized for one float.
pub(crate) fn round_scaled(
    value: f64,
    coefficient: u64,
    integer_ns: i128,
) -> Result<i128, ValueError> {
    let (product, power, negative) = scaled_parts(value, coefficient)?;
    let (whole, above_half, exactly_half) = if power >= 0 {
        let shift = power as u32;
        if shift >= 127 || product > ((i128::MAX as u128) >> shift) {
            return Err(ValueError::Overflow);
        }
        ((product << shift) as i128, false, false)
    } else {
        let shift = (-power) as u32;
        if shift >= 128 {
            // The bounded product has at most103 bits, strictly below half.
            (0, false, false)
        } else {
            let remainder = product & ((1_u128 << shift) - 1);
            let half = 1_u128 << (shift - 1);
            (
                (product >> shift) as i128,
                remainder > half,
                remainder == half,
            )
        }
    };
    let whole = if negative { -whole } else { whole };
    let result = integer_ns.checked_add(whole).ok_or(ValueError::Overflow)?;
    if above_half || (exactly_half && result % 2 != 0) {
        result
            .checked_add(if negative { -1 } else { 1 })
            .ok_or(ValueError::Overflow)
    } else {
        Ok(result)
    }
}

fn scaled_parts(value: f64, coefficient: u64) -> Result<(u128, i32, bool), ValueError> {
    if value.is_nan() {
        return Err(ValueError::NotANumber);
    }
    if !value.is_finite()
        || !(-SIGNED64_BOUND..SIGNED64_BOUND).contains(&value)
        || coefficient > 604_800_000_000_000
    {
        return Err(ValueError::Overflow);
    }
    let bits = value.to_bits();
    let exponent = ((bits >> 52) & 0x7ff) as i32;
    let fraction = bits & ((1_u64 << 52) - 1);
    let (significand, power) = if exponent == 0 {
        (fraction, -1074)
    } else {
        (fraction | (1_u64 << 52), exponent - 1023 - 52)
    };
    Ok((
        u128::from(significand) * u128::from(coefficient),
        power,
        bits >> 63 != 0,
    ))
}

/// Exact signed binary sum of fixed-duration floating contributions.
pub(crate) struct FixedNsAccumulator {
    magnitude: [u64; LIMBS],
    negative: bool,
}

impl FixedNsAccumulator {
    /// Empty scratch, created only after encountering a nonintegral float path.
    pub(crate) const fn new() -> Self {
        Self {
            magnitude: [0; LIMBS],
            negative: false,
        }
    }

    /// Accumulate the actual binary value times its exact integer ns coefficient.
    pub(crate) fn add(&mut self, value: f64, coefficient: u64) -> Result<(), ValueError> {
        let (product, power, negative) = scaled_parts(value, coefficient)?;
        if product == 0 {
            return Ok(());
        }
        let shift = (power + FRACTION_BITS as i32) as usize;
        let word = shift / 64;
        let offset = shift % 64;
        let mut term = [0_u64; LIMBS];
        for lane in 0..2 {
            let value = (product >> (lane * 64)) as u64;
            if value == 0 {
                continue;
            }
            if word + lane >= LIMBS {
                return Err(ValueError::Overflow);
            }
            term[word + lane] |= value << offset;
            if offset != 0 {
                let high = value >> (64 - offset);
                if high != 0 {
                    if word + lane + 1 >= LIMBS {
                        return Err(ValueError::Overflow);
                    }
                    term[word + lane + 1] |= high;
                }
            }
        }
        self.add_magnitude(term, negative)
    }

    fn add_magnitude(&mut self, term: [u64; LIMBS], negative: bool) -> Result<(), ValueError> {
        if negative == self.negative {
            let mut carry = false;
            for (left, right) in self.magnitude.iter_mut().zip(term) {
                let (sum, first) = left.overflowing_add(right);
                let (sum, second) = sum.overflowing_add(u64::from(carry));
                *left = sum;
                carry = first || second;
            }
            return if carry {
                Err(ValueError::Overflow)
            } else {
                Ok(())
            };
        }
        let ordering = self.magnitude.iter().rev().cmp(term.iter().rev());
        if ordering == std::cmp::Ordering::Equal {
            self.magnitude.fill(0);
            self.negative = false;
            return Ok(());
        }
        let (mut larger, smaller) = if ordering.is_gt() {
            (self.magnitude, term)
        } else {
            self.negative = negative;
            (term, self.magnitude)
        };
        let mut borrow = false;
        for (left, right) in larger.iter_mut().zip(smaller) {
            let (difference, first) = left.overflowing_sub(right);
            let (difference, second) = difference.overflowing_sub(u64::from(borrow));
            *left = difference;
            borrow = first || second;
        }
        debug_assert!(!borrow);
        self.magnitude = larger;
        Ok(())
    }

    /// Round once to ns after combining the exact integer contribution.
    /// Ties use the parity of the complete result, including the integer base.
    pub(crate) fn rounded(&self, integer_ns: i128) -> Result<i128, ValueError> {
        let mut whole = 0_u128;
        for index in FRACTION_BITS / 64..LIMBS {
            let word = u128::from(self.magnitude[index]);
            let bit = index * 64;
            if bit < FRACTION_BITS {
                whole |= word >> (FRACTION_BITS - bit);
            } else {
                let shift = bit - FRACTION_BITS;
                if shift >= 128 || word > (u128::MAX >> shift) {
                    return Err(ValueError::Overflow);
                }
                whole |= word << shift;
            }
        }
        let whole = i128::try_from(whole).map_err(|_| ValueError::Overflow)?;
        let whole = if self.negative { -whole } else { whole };
        let value = integer_ns.checked_add(whole).ok_or(ValueError::Overflow)?;
        let halfway = FRACTION_BITS - 1;
        let half_word = halfway / 64;
        let half_bit = halfway % 64;
        let half = self.magnitude[half_word] & (1_u64 << half_bit) != 0;
        let below = self.magnitude[..half_word].iter().any(|&word| word != 0)
            || self.magnitude[half_word] & ((1_u64 << half_bit) - 1) != 0;
        if half && (below || value % 2 != 0) {
            value
                .checked_add(if self.negative { -1 } else { 1 })
                .ok_or(ValueError::Overflow)
        } else {
            Ok(value)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn half_ties_include_complete_integer_parity() {
        let mut value = FixedNsAccumulator::new();
        value.add(0.5, 1).unwrap();
        assert_eq!(value.rounded(0).unwrap(), 0);
        assert_eq!(value.rounded(1).unwrap(), 2);
        assert_eq!(value.rounded(-1).unwrap(), 0);
        let mut negative = FixedNsAccumulator::new();
        negative.add(-0.5, 1).unwrap();
        assert_eq!(negative.rounded(0).unwrap(), 0);
        assert_eq!(negative.rounded(1).unwrap(), 0);
        assert_eq!(negative.rounded(-1).unwrap(), -2);
    }

    #[test]
    fn fractions_are_combined_before_rounding() {
        let mut value = FixedNsAccumulator::new();
        value.add(0.5, 1).unwrap();
        value.add(0.5, 1).unwrap();
        assert_eq!(value.rounded(0).unwrap(), 1);
        value.add(-1.0, 1).unwrap();
        assert_eq!(value.rounded(0).unwrap(), 0);
        value.add(-0.75, 1).unwrap();
        assert_eq!(value.rounded(0).unwrap(), -1);
    }

    #[test]
    fn tiny_values_and_negative_zero_do_not_disappear_by_underflow() {
        let mut value = FixedNsAccumulator::new();
        value.add(f64::from_bits(1), 604_800_000_000_000).unwrap();
        value.add(-0.0, 1).unwrap();
        assert_eq!(value.rounded(0).unwrap(), 0);
        value.add(0.5, 1).unwrap();
        assert_eq!(value.rounded(0).unwrap(), 1); // strictly above half
    }

    #[test]
    fn common_float_seconds_keep_nanoseconds() {
        let mut value = FixedNsAccumulator::new();
        value.add(1e-9, 1_000_000_000).unwrap();
        assert_eq!(value.rounded(0).unwrap(), 1);
        value.add(0.001, 1000).unwrap();
        assert_eq!(value.rounded(0).unwrap(), 2);
    }

    #[test]
    fn large_exact_cancellation_preserves_small_fraction() {
        let mut value = FixedNsAccumulator::new();
        value
            .add(9_007_199_254_740_992.0, 604_800_000_000_000)
            .unwrap();
        value.add(0.75, 1).unwrap();
        value
            .add(-9_007_199_254_740_992.0, 604_800_000_000_000)
            .unwrap();
        assert_eq!(value.rounded(0).unwrap(), 1);
    }

    #[test]
    fn input_bounds_and_nonfinite_are_distinct() {
        let mut value = FixedNsAccumulator::new();
        assert_eq!(value.add(f64::NAN, 1), Err(ValueError::NotANumber));
        assert_eq!(value.add(f64::INFINITY, 1), Err(ValueError::Overflow));
        assert_eq!(value.add(SIGNED64_BOUND, 1), Err(ValueError::Overflow));
        value.add(-SIGNED64_BOUND, 1).unwrap();
        assert_eq!(value.rounded(0).unwrap(), i128::from(i64::MIN));
    }

    #[test]
    fn single_float_specialization_has_the_same_exact_answers() {
        let numbers = [
            0.0,
            -0.0,
            0.5,
            -0.5,
            0.1,
            -0.1,
            1e-9,
            f64::from_bits(1),
            -SIGNED64_BOUND,
            f64::from_bits(SIGNED64_BOUND.to_bits() - 1),
        ];
        for number in numbers {
            for coefficient in [1, 1000, 1_000_000_000, 604_800_000_000_000] {
                for base in [-1, 0, 1, i128::from(i64::MAX)] {
                    let mut sum = FixedNsAccumulator::new();
                    sum.add(number, coefficient).unwrap();
                    assert_eq!(round_scaled(number, coefficient, base), sum.rounded(base));
                }
            }
        }
    }
}
