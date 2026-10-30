"""Pddt business state and the standard Python reconstruction protocol.

Only copy/save operations enter this module. Date operations never scan state.
"""
from copy import _reconstruct
from ._class_protocol import definition as _definition

from .errors import _own_error, _external_error
from ._range import _ARRAY_HAS_FREQ

# Actual DatetimeIndex-owned keys verified in all three supported environments.
# Other underscore-prefixed business fields remain ordinary user state.
_CORE_KEYS=frozenset(("_data","_name","_cache","_id","_references"))
if not _ARRAY_HAS_FREQ:
    # pandas3.1 owns frequency on the Index; it belongs to the date core.
    _CORE_KEYS = _CORE_KEYS | {"_freq"}


def capture(value):
    """Copy the default dictionary/slots containers, excluding date internals."""
    state=object.__getstate__(value)
    if state is None:
        return None
    dictionary,slots=state if isinstance(state,tuple) else (state,None)
    dictionary=None if dictionary is None else {key:item for key,item in dict.items(dictionary) if key not in _CORE_KEYS}
    slots=None if slots is None else {key:item for key,item in dict.items(slots) if key not in _CORE_KEYS}
    if slots:
        return dictionary or None,slots
    return dictionary or None


def apply(value,state):
    """Apply ordinary business state, leaving the validated date core alone."""
    if state is None:
        return
    if isinstance(state,tuple):
        if len(state)!=2:
            raise _own_error(ValueError("business state must contain a dictionary and slots"),"state",state)
        dictionary,slots=state
    else:
        dictionary,slots=state,None
    for name,part in (("dictionary",dictionary),("slots",slots)):
        if part is not None and not isinstance(part,dict):
            raise _own_error(TypeError("must be a dictionary or None"),"state."+name,part)
    entries=[] if slots is None else list(dict.items(slots))
    for part in (dictionary,slots):
        if part is not None and any(key in _CORE_KEYS for key in dict.keys(part)):
            raise _own_error(ValueError("business state cannot replace internal date or cache fields"),"state",state)
    if any(not isinstance(key,str) for key,_ in entries):
        raise _own_error(TypeError("slot names must be strings"),"state.slots",slots)
    try:
        if dictionary is not None:
            value.__dict__.update(dictionary)
        for key,item in entries:
            setattr(value,key,item)
    except Exception as error:
        raise _external_error(error)


def state(value):
    """Call the actual user state hook once, retaining its original failure."""
    try:
        return value.__getstate__()
    except Exception as error:
        raise _external_error(error)


def recipe(value,restore):
    """Snapshot a portable versioned date core, with separate business state."""
    data=value.asi8.astype("<i8",copy=False).tobytes()
    return restore,(type(value),"rstimes.pddt",1,data,value.unit,value.tz,value.name,value.freq),state(value)


def copy_value(value,base,restore_copy,deep,memo=None,name=None,honor_copy=False):
    """Use Python's complete reconstruction semantics, including one shared memo."""
    cls=type(value)
    if deep and memo is None:
        memo={}
    hook="__deepcopy__" if deep else "__copy__"
    if honor_copy and _definition(cls,hook) not in (None,_definition(base,hook)):
        try:
            callable=getattr(cls,hook)
            result=callable(value,memo) if deep else callable(value)
        except Exception as error:
            raise _external_error(error)
        return _named_result(value,result,name)
    custom=(_definition(cls,"__reduce_ex__") is not base.__reduce_ex__
        or _definition(cls,"__reduce__") is not base.__reduce__)
    if custom:
        try:
            reduction=value.__reduce_ex__(4)
        except Exception as error:
            raise _external_error(error)
    else:
        reduction=(restore_copy,(cls,value.array,value.name if name is None else name,value.freq),state(value))
    if isinstance(reduction,str):
        result=value
    else:
        # This is the same complete helper used by copy.copy/deepcopy themselves,
        # verified on the fixed Python3.11/3.13 environments, not a new interpreter.
        result=_reconstruct(value,memo if deep else None,*reduction)
    return _named_result(value,result,name) if custom else result


def _named_result(source,result,name):
    if name is not None:
        if result is source and result.name!=name:
            raise _own_error(ValueError("the copy hook returned the original object; it cannot be renamed without changing the source"),"name",name)
        try:
            result.name=name
        except Exception as error:
            raise _external_error(error)
    return result
