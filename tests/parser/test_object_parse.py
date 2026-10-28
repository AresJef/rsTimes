"""Focused object conversion contract; run against an explicitly installed wheel."""
import datetime as dt
import math
import sys
import unittest

from rstimes import parse
from rstimes.errors import ParseError


class ObjectParse(unittest.TestCase):
    def failed(self, value, cause=None, **kwargs):
        with self.assertRaises(cause or TypeError) as caught:
            parse(value, **kwargs)
        return caught.exception

    def test_datetime_identity_timezone_fold_and_subclasses(self):
        value = dt.datetime(2024, 11, 3, 1, 2, 3, 456789, dt.timezone.utc, fold=1)
        self.assertIs(parse(value), value)
        self.assertIs(parse(value, dtclass=dt.datetime), value)
        class Sub(dt.datetime):
            pass
        child = Sub(2024, 11, 3, 1, 2, 3, 456789, dt.timezone.utc, fold=1)
        self.assertIs(parse(child, dtclass=Sub), child)
        rebuilt = parse(child)
        self.assertIs(type(rebuilt), dt.datetime)
        self.assertEqual(rebuilt, value)
        self.assertEqual(rebuilt.fold, 1)
        self.assertIs(rebuilt.tzinfo, dt.timezone.utc)

    def test_date_and_numeric(self):
        self.assertEqual(parse(dt.date(2024, 2, 29)), dt.datetime(2024, 2, 29))
        for value in (0, -1, 1, -62135596800, 253402300799, 1.23456789, -1.23456789,
                      0.0000005, -0.0000005, 0.99999996, -0.99999996):
            fixed = '%.7f' % value
            whole, fraction = fixed.lstrip('-').split('.')
            micros = int(whole) * 1_000_000 + int(fraction[:6])
            if fixed.startswith('-'):
                micros = -micros
            self.assertEqual(parse(value), dt.datetime(1970, 1, 1) + dt.timedelta(microseconds=micros))
        for value in (False, True):
            self.failed(value, TypeError)
        class Integer(int):
            def __float__(self):
                return 2.5
        class Floating(float):
            def __float__(self):
                return 3.5
        self.assertEqual(parse(Integer(1)), dt.datetime(1970, 1, 1, 0, 0, 2, 500000))
        self.assertEqual(parse(Floating(1)), dt.datetime(1970, 1, 1, 0, 0, 1))

    def test_float_rounding_boundaries(self):
        values = [0.0, -0.0, math.ulp(0.0), -math.ulp(0.0),
                  sys.float_info.min, -sys.float_info.min,
                  0.00000095, 0.00000096, 0.99999995, 0.99999996,
                  -62135596800.0, 253402300799.0]
        for n in (1, 3, 63, 127, 255):
            midpoint = n / 256
            values.extend((math.nextafter(midpoint, -math.inf), midpoint,
                           math.nextafter(midpoint, math.inf)))
        values += [-value for value in values if value > 0 and value < 1]
        for value in values:
            with self.subTest(value=value):
                fixed = '%.7f' % value
                whole, fraction = fixed.lstrip('-').split('.')
                micros = int(whole) * 1_000_000 + int(fraction[:6])
                if fixed.startswith('-'):
                    micros = -micros
                expected = dt.datetime(1970, 1, 1) + dt.timedelta(microseconds=micros)
                self.assertEqual(parse(value), expected)
        limit = math.nextafter(9_223_372_036_854.775, math.inf)
        for value in (limit, math.nextafter(limit, math.inf),
                      -limit, math.nextafter(-limit, -math.inf)):
            self.failed(value, OverflowError)

    def test_errors_and_ignored_string_parameters(self):
        self.failed(float('nan'), ValueError)
        for value in (float('inf'), -float('inf'), 10**100):
            self.failed(value, OverflowError)
        for value in (None, b'2024', [], dt.time(), dt.timedelta()):
            self.failed(value)
        self.failed(-62135596801, OverflowError)
        self.failed(253402300800, OverflowError)
        value = dt.datetime(2024, 1, 1)
        self.assertIs(parse(value, default=object(), yearfirst=None, dayfirst=False), value)
        for option in ("yearfirst", "dayfirst"):
            with self.assertRaises(TypeError):
                parse(value, **{option: object()})

    def test_constructor_keywords_result_and_exceptions(self):
        calls = []
        def factory(**kwargs):
            calls.append(kwargs)
            return dt.datetime(**kwargs)
        source = dt.datetime(2024, 1, 2, 3, 4, 5, 6, dt.timezone.utc, fold=1)
        self.assertEqual(parse(source, dtclass=factory), source)
        self.assertEqual(list(calls[0]), ['year', 'month', 'day', 'hour', 'minute', 'second', 'microsecond', 'tzinfo', 'fold'])
        self.assertEqual(calls[0]['fold'], 1)
        self.assertIsNone(parse(0, dtclass=lambda **kw: None))
        self.failed(0, TypeError, dtclass=lambda **kw: 42)
        def broken(**kwargs):
            raise LookupError('constructor sentinel')
        error = self.failed(0, LookupError, dtclass=broken)
        self.assertEqual(str(error), 'constructor sentinel')
        def interrupt(**kwargs):
            raise KeyboardInterrupt('passthrough')
        with self.assertRaises(KeyboardInterrupt):
            parse(0, dtclass=interrupt)

    def test_numpy(self):
        import numpy as np
        for unit in ('Y', 'M', 'W', 'D', 'h', 'm', 's', 'ms', 'us', 'ns'):
            self.assertEqual(parse(np.datetime64(0, unit)), dt.datetime(1970, 1, 1))
        self.assertEqual(parse(np.datetime64(-1, 'ns')), dt.datetime(1969, 12, 31, 23, 59, 59, 999999))
        self.assertEqual(parse(np.datetime64(1, '10D')), dt.datetime(1970, 1, 11))
        self.failed(np.datetime64('NaT'), ValueError)
        self.failed(np.timedelta64(1, 'D'))
        self.failed(np.array(['2024-01-01'], dtype='datetime64[D]'))


if __name__ == '__main__':
    unittest.main()
