from rstimes import Delta, Pydt, Pddt, parse_str, parse_to_epoch
Delta(unknown=1)
Pydt(2024, 1, 1).day_of_year()
Pydt(2024, 1, 1).weekday + 1
Pydt(2024, 1, 1).__add__(o=Delta(days=1))
Pddt(['2024-01-01'], as_unit='us')
Pddt(['2024-01-01']).round(unit='s')
Pddt(['2024-01-01']).as_unit(as_unit='us')
Pddt(['2024-01-01']).pddt.replace(day='1')
Pddt(['2024-01-01']).snap(freq='15min')
Pddt(['2024-01-01']).fsp([1, 2])
parse_str('2024-01-01', unknown=True)
parse_to_epoch('2024-01-01', unknown=True)

Pydt(2024, 1, 1).to_date(month="February")
Pydt(2024, 1, 1).to_datetime(month="February")
