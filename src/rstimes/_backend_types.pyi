"""Type-only structural facts for validated external temporal buffers.

Runtime dispatch still uses the actual cached pandas classes. These protocols
describe their public integer storage, which some upstream stub versions omit;
they do not introduce runtime wrapper classes or conversions.
"""

from datetime import tzinfo
from typing import Literal, Protocol, runtime_checkable
import numpy as np
from numpy.typing import NDArray

_Unit = Literal["s", "ms", "us", "ns"]


@runtime_checkable
class _PandasTicks(Protocol):
    """A real pandas temporal array with integer ticks and one native unit."""

    def __len__(self) -> int:
        """Return the number of logical values, including missing positions."""
        ...

    @property
    def asi8(self) -> NDArray[np.int64]:
        """Return the existing int64 tick view; missing dates use pandas NaT."""
        ...

    @property
    def unit(self) -> _Unit:
        """Return the resolution associated with each integer tick."""
        ...


@runtime_checkable
class _PandasDateTicks(_PandasTicks, Protocol):
    """A real pandas date array, with its whole-column timezone metadata."""

    @property
    def tz(self) -> tzinfo | None:
        """Return the actual source timezone, or None for naive date storage."""
        ...
