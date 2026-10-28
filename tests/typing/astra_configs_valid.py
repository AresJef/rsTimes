"""Legal Configs dictionaries must remain accepted by public annotations."""
import numpy as np
from rstimes import Configs

class Index:
    def __index__(self) -> int:
        return 1

integers: dict[str, int] = {"reviewtoken": 1}
indices: dict[str, Index] = {"reviewtoken": Index()}
numpy_integers: dict[str, np.int64] = {"reviewtoken": np.int64(1)}
mixed: dict[str, int | Index] = {"reviewtoken": 1, "anothertoken": Index()}
Configs().set_tzoffset(integers)
Configs().set_tzoffset(indices)
Configs().set_tzoffset(numpy_integers)
Configs().set_tzoffset(mixed)
Configs().set_month(integers)
Configs().set_month(indices)
Configs().set_month(numpy_integers)
Configs().set_month(mixed)
Configs().set_weekday(integers)
Configs().set_weekday(indices)
Configs().set_weekday(numpy_integers)
Configs().set_weekday(mixed)
Configs().set_hms(integers)
Configs().set_hms(indices)
Configs().set_hms(numpy_integers)
Configs().set_hms(mixed)
Configs().set_ampm(integers)
Configs().set_ampm(indices)
Configs().set_ampm(numpy_integers)
Configs().set_ampm(mixed)
