"""Restore must keep captured entries when real callbacks edit original inputs."""
from datetime import timezone
from rstimes import Pydt

def test_restore_callbacks_cannot_change_captured_dict_or_slots():
    saved=[]
    first=[]
    dictionary={'saved':saved}
    slots={'payload_a':first,'payload_b':2}
    calls=[]
    class Child(Pydt):
        __slots__=('payload_a','payload_b')
        def __getattribute__(self,name):
            if name=='__dict__':
                calls.append('dictionary')
                dictionary[42]='late invaliddictionary key'
                slots['payload_b']=999
                slots[42]='late invalidslot key'
            return super().__getattribute__(name)
        def __setattr__(self,name,value):
            calls.append(name)
            if name=='payload_a':
                slots.clear()
                slots['late']='must not beapplied'
            return super().__setattr__(name,value)
    value=Child(2024,1,2,tzinfo=timezone.utc,fold=1)
    before_hash=hash(value)
    calls.clear()
    assert value.__setstate__((dictionary,slots)) is None
    actual=object.__getattribute__(value,'__dict__')
    assert actual=={'saved':saved}
    assert actual['saved'] is saved
    assert object.__getattribute__(value,'payload_a') is first
    assert object.__getattribute__(value,'payload_b')==2
    assert calls==['dictionary','payload_a','payload_b']
    assert 42 in dictionary and slots=={'late':'must not beapplied'}
    assert (value.year,value.month,value.day,value.hour,value.minute,value.second,value.microsecond,value.tzinfo,value.fold)==(2024,1,2,0,0,0,0,timezone.utc,1)
    assert hash(value)==before_hash
