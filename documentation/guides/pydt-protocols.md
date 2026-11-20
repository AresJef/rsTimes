# Copy and restore a Pydt subclass

Pydt uses standard datetime comparison and hashing where their rules
apply. A supported external operand can supply its own arithmetic.
For application metadata, use ordinary copy and pickle protocols.

## Save an appointment with its label

(pydt-pickle-an-appointment)=
```python
import pickle

from rstimes import Pydt

class Appointment(Pydt):
    pass

event = Appointment(2024, 2, 29, 9, 30)
event.label = "Renewal"
restored = pickle.loads(pickle.dumps(event))
print(restored.isoformat())
print(restored.label)
```

**Output**

```text
2024-02-29T09:30:00
Renewal
```

The saved value retains its class, date fields, and default application
state. Load only trusted pickle data.

## Make a separate copy for editing

(pydt-deepcopy-appointment-notes)=
```python
from copy import deepcopy

from rstimes import Pydt

class Appointment(Pydt):
    pass

event = Appointment(2024, 2, 29, 9)
event.notes = ["Original slot"]
trial = deepcopy(event)
trial.notes.append("Check availability")
print(event.notes)
```

**Output**

```text
['Original slot']
```

Default shallow copy preserves references to application objects. Default
deep copy uses one memo for shared references and cycles. The datetime
fields stay immutable. Custom copy and state hooks control their own
restoration and errors. For a new date produced by a factory or
calculation, a real subclass constructor can participate in the normal
construction. For timezone methods that require an external datetime
protocol, see [the scalar timezone guide](pydt-timezones.md).
