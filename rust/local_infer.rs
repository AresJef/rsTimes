//! Ordered ambiguity inference shared by Python and native timezone backends.

/// Data failures and violated internal invariants remain separate at adapters.
#[derive(Clone, Copy, Debug)]
pub(crate) enum InferError {
    Data(&'static str),
    Internal(&'static str),
}

#[derive(Clone, Copy)]
pub(crate) struct Pending {
    pub first: i128,
    pub second: i128,
    pub zone: usize,
}

/// Infer within each consecutive ambiguous run in input order, never by sorting.
/// One non-increasing step separates its first and second actual UTC candidates.
pub(crate) fn infer(
    values: &mut [Option<i128>],
    pending: &[Option<Pending>],
) -> Result<(), InferError> {
    let mut start = 0;
    while start < pending.len() {
        let Some(first) = pending[start] else {
            start += 1;
            continue;
        };
        let mut end = start + 1;
        while end < pending.len() && pending[end].is_some_and(|v| v.zone == first.zone) {
            end += 1;
        }
        let mut switch = None;
        for i in start + 1..end {
            let previous =
                pending[i - 1].ok_or(InferError::Internal("missing inference candidate"))?;
            let current = pending[i].ok_or(InferError::Internal("missing inference candidate"))?;
            if current.first <= previous.first && switch.replace(i).is_some() {
                return Err(InferError::Data(
                    "cannot infer local time: multiple clock reversals occur within one repeated interval",
                ));
            }
        }
        let split=switch.ok_or(InferError::Data("cannot infer this repeated local time from input order; provide a boolean or boolean collection"))?;
        for i in start..end {
            let item = pending[i].ok_or(InferError::Internal("missing inference candidate"))?;
            values[i] = Some(if i < split { item.first } else { item.second });
        }
        start = end;
    }
    Ok(())
}
