//! Compact native values crossing the owned plugin kwargs boundary.

/// Transport signed128 through two signed64 limbs, without decimal conversion.
pub(crate) mod signed_128 {
    use serde::{Deserialize, Serialize};
    pub(crate) fn serialize<S: serde::Serializer>(
        value: &i128,
        serializer: S,
    ) -> Result<S::Ok, S::Error> {
        ((*value >> 64) as i64, *value as i64).serialize(serializer)
    }
    pub(crate) fn deserialize<'de, D: serde::Deserializer<'de>>(
        deserializer: D,
    ) -> Result<i128, D::Error> {
        let (high, low) = <(i64, i64)>::deserialize(deserializer)?;
        Ok((i128::from(high) << 64) | i128::from(low as u64))
    }
}

/// Python plugin kwargs use one bytes object, not a list of per-byte integers.
pub(crate) fn byte_vector<'de, D: serde::Deserializer<'de>>(
    deserializer: D,
) -> Result<Vec<u8>, D::Error> {
    struct Bytes;
    impl<'de> serde::de::Visitor<'de> for Bytes {
        type Value = Vec<u8>;
        fn expecting(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
            f.write_str("native bytes or a byte sequence")
        }
        fn visit_bytes<E: serde::de::Error>(self, value: &[u8]) -> Result<Self::Value, E> {
            Ok(value.to_vec())
        }
        fn visit_byte_buf<E: serde::de::Error>(self, value: Vec<u8>) -> Result<Self::Value, E> {
            Ok(value)
        }
        fn visit_seq<A: serde::de::SeqAccess<'de>>(
            self,
            mut values: A,
        ) -> Result<Self::Value, A::Error> {
            let mut result = Vec::new();
            while let Some(value) = values.next_element()? {
                result.push(value);
            }
            Ok(result)
        }
    }
    deserializer.deserialize_byte_buf(Bytes)
}
