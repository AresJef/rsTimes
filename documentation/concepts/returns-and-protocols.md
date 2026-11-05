# Return types, inheritance and application protocols

rsTimes date classes participate in their host container protocols, but the
receiver's class alone does not determine every result type. Each API page
states and executes its actual return role.

| Operation family | Read the result as |
|---|---|
| Own eager date transformation | The stated date class, unit, timezone and missingness |
| Date field or predicate | The stated scalar, array, Index or native Series dtype |
| Native inherited method | Its actual Python scalar, ordinary native container or rsTimes wrapper |
| `.pldt` expression | An Expr until select/collect executes it; collected columns are native Series |
| Application copy/state hook | The actual protocol result; legitimate hooks can choose another type |

For Polars, `.pldt` is the rsTimes date namespace and `.dt` is the native date
namespace. A native value replacement is separate from rsTimes date-field
replacement. On Pddt, use `.pddt.replace` for strict field replacement; on
Pldt/Polars use `.pldt.replace`. An inherited helper's visibility does not
convert Datetime to another dtype or promise that a numeric-only kernel accepts
date input.

Copying has both data and application-state responsibilities. Default shallow
and deep operations, real custom hooks, alias/cycle handling and reduction
fallback are documented with concrete examples. A different class chosen by
a legitimate hook is not automatically a failure. Named Pddt/Pldt copy still
has deferred custom reduction cases; see
[known rsTimes issues](../compatibility/known-issues.md).

Use the [scalar protocols](../guides/pydt-protocols.md),
[pandas protocols](../guides/pddt-protocols.md), and
[Polars state/copy guide](../guides/pldt-state.md) for exact guarantees and
exceptions. Inherited entry references show their own date-container examples
and link to the provider's complete parameter documentation; they do not
redefine the provider's unrelated APIs.
