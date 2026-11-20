"""The direct, complete Configs allocator keeps concrete public typing."""
import numpy as np
from rstimes import Configs

cfg: Configs = Configs.__new__(Configs, yearfirst=np.bool_(False), dayfirst=True)
cfg.__init__(dayfirst=False)
cfg.set_month({"harvest": 10})
same: bool = cfg.dayfirst
