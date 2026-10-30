//! Scalar roles and strict positional column lengths, independent of containers.
pub(crate) enum Column<T> {
    Scalar(T),
    Values(Vec<T>),
}
impl<T: Copy> Column<T> {
    pub(crate) fn get(&self, row: usize) -> T {
        match self {
            Self::Scalar(value) => *value,
            Self::Values(values) => values[row],
        }
    }
    pub(crate) fn len(&self) -> Option<usize> {
        match self {
            Self::Scalar(_) => None,
            Self::Values(values) => Some(values.len()),
        }
    }
}

pub(crate) fn length(
    lengths: impl IntoIterator<Item = Option<usize>>,
    size: Option<usize>,
) -> Result<usize, &'static str> {
    let mut common = None;
    for length in lengths.into_iter().flatten() {
        if size.is_some() {
            return Err("omit size when any component is a collection");
        }
        if common.is_some_and(|previous| previous != length) {
            return Err(
                "all component collections must have the same length; a length-one collection is not a scalar",
            );
        }
        common = Some(length);
    }
    common
        .or(size)
        .ok_or("all-scalar factory components require size; use collections for a single row")
}
