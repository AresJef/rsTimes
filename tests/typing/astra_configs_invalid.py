"""Static rejection samples: these calls must produce type diagnostics."""
from types import MappingProxyType
from rstimes import Configs

class IntOnly:
    def __int__(self) -> int:
        return 1

Configs().set_tzoffset({"reviewtoken": 1.0})
Configs().set_tzoffset({"reviewtoken": "1"})
Configs().set_tzoffset({"reviewtoken": IntOnly()})
Configs().set_tzoffset(MappingProxyType({"reviewtoken": 1}))
Configs().set_month({"reviewtoken": 1.0})
Configs().set_month({"reviewtoken": "1"})
Configs().set_month({"reviewtoken": IntOnly()})
Configs().set_month(MappingProxyType({"reviewtoken": 1}))
Configs().set_weekday({"reviewtoken": 1.0})
Configs().set_weekday({"reviewtoken": "1"})
Configs().set_weekday({"reviewtoken": IntOnly()})
Configs().set_weekday(MappingProxyType({"reviewtoken": 1}))
Configs().set_hms({"reviewtoken": 1.0})
Configs().set_hms({"reviewtoken": "1"})
Configs().set_hms({"reviewtoken": IntOnly()})
Configs().set_hms(MappingProxyType({"reviewtoken": 1}))
Configs().set_ampm({"reviewtoken": 1.0})
Configs().set_ampm({"reviewtoken": "1"})
Configs().set_ampm({"reviewtoken": IntOnly()})
Configs().set_ampm(MappingProxyType({"reviewtoken": 1}))
