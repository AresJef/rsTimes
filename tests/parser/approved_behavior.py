"""Independent expectations for the approved departures from cyTimes 3.1.0.

This module never imports the Rust implementation. Unchanged cases use the
frozen official parser. Short years are expanded in the input before that
parser is called, so its system-year window cannot determine our answer.
"""
from datetime import date, datetime, timedelta, timezone
import operator
import re

from outcomes import _legacy_error, error_category, outcomes_equal

from cytimes.parser import Configs as OriginalConfigs, parse as original_parse
from cytimes.errors import InvalidConfigsValue


def reference_year(short, reference):
    """Map a short year into the approved inclusive 100-year window."""
    year = reference // 100 * 100 + short
    if year >= reference + 50:
        year -= 100
    elif year < reference - 50:
        year += 100
    if not 1 <= year <= 9999:
        raise ValueError("resolved reference-window year is outside 1..9999")
    return year


def expanded_year(text, kwargs):
    """Find a short-year role by verifying a full-century substitution."""
    try:
        old = original_parse(text, **kwargs)
    except Exception:
        return None
    reference = kwargs.get('default')
    if not isinstance(reference, date):
        return None
    candidates = []
    for match in re.finditer(r'(?<!\d)\d{1,2}(?!\d)', text):
        if int(match[0]) != old.year % 100:
            continue
        explicit = text[:match.start()] + f'{old.year:04}' + text[match.end():]
        proof_kwargs = dict(kwargs)
        if kwargs.get('dayfirst'):
            proof_kwargs['dayfirst'] = False
        try:
            proof = original_parse(explicit, **proof_kwargs)
            if proof != old and (proof.year, proof.month, proof.day) != (old.year, old.day, old.month):
                continue
        except Exception:
            continue
        year = reference_year(int(match[0]), reference.year)
        # With an explicit year-first input the old dayfirst path changes its
        # precedence. Keep the already established month/day roles instead.
        if kwargs.get('dayfirst') and match.start() == 0:
            return old.replace(year=year)
        candidates.append(text[:match.start()] + f'{year:04}' + text[match.end():])
    for match in re.finditer(r'(?<!\d)\d{6}(?!\d)', text):
        explicit = text[:match.start()] + f'{old.year:04}{old.month:02}{old.day:02}' + text[match.end():]
        try:
            if original_parse(explicit, **kwargs) != old:
                continue
        except Exception:
            continue
        year = reference_year(old.year % 100, reference.year)
        candidates.append(text[:match.start()] + f'{year:04}{old.month:02}{old.day:02}' + text[match.end():])
    values = [original_parse(candidate, **kwargs) for candidate in candidates]
    # The original general lexer forgets the leading zeroes of a full year in
    # a compact date. No weekday token occurs in these fixed compact inputs.
    if re.match(r'^\d{6}(?:\s|$)', text):
        return old.replace(year=reference_year(old.year % 100, reference.year))
    if not values:
        return None
    if any(value != values[0] for value in values):
        raise AssertionError(('Ambiguous approved-year expectation', text, values))
    return values[0]


def expected_parse(text, **kwargs):
    """Return the approved value without consulting a candidate's output."""
    default = kwargs.get('default', date(2024, 1, 31))
    if re.match(r'^0000(?:[-/.]|$)', text):
        raise ValueError("explicit year must be at least 1")
    week = re.match(r'^\d{4}-?W(\d{2})(?:-?(\d))?(?=$|[T\s])', text)
    if week and (int(week[1]) < 1 or week[2] is not None and int(week[2]) < 1):
        raise ValueError("ISO week and weekday must be at least 1")
    # Explicit fields that the old grammar dropped or rejected. These finite
    # entries are part of the retained public corpus, not a new parser.
    exact = {
        # F11: clamp the original 12-hour value before the AM/PM conversion.
        '0 PM': datetime(default.year, default.month, default.day, 13),
        '2023.02.08 22:01 PM': datetime(2023, 2, 8, 12, 1),
        'Jan 29, 1945 14:45 AM I going to see you there?': datetime(1945, 1, 29, 0, 45),
        
        '2023-366': datetime(2023, 12, 31),
        '2024-02-29T24:00:00': datetime(2024, 2, 29, 23),
        '2024-02-29T23:60:00': datetime(2024, 2, 29, 23, 59),
        '2024-02-29T23:59:60': datetime(2024, 2, 29, 23, 59, 59),
        '31 2024 12': datetime(2024, 12, 31),
        '29 февраля 2024': datetime(2024, 12, default.day),
        '24h': datetime(default.year, default.month, default.day, 23),
        '60m': datetime(default.year, default.month, default.day, 0, 59),
        '60s': datetime(default.year, default.month, default.day, 0, 0, 59),
    }
    if text in exact:
        return exact[text]
    if text == '10000-01-01':
        raise ValueError('standard datetime cannot represent year 10000')
    if text == '2024060':
        return datetime(2024, 1, 1) + timedelta(days=59)
    week_match = re.fullmatch(r'(\d{4})[ -]?W(\d{2})(?:-?(\d))?', text)
    if week_match:
        year, week, weekday = int(week_match[1]), int(week_match[2]), int(week_match[3] or 1)
        last_week = date(year, 12, 28).isocalendar().week
        return datetime.combine(date.fromisocalendar(year, min(week, last_week), min(weekday, 7)), datetime.min.time())
    if text == 'Feb 29 2024 12:34:56 +24:00':
        value = datetime(2024, 2, 29, 12, 34, 56)
        return value if kwargs.get('ignoretz', True) else value.replace(tzinfo=timezone(timedelta(hours=23)))
    if text == '2024 31 12' and not kwargs.get('dayfirst'):
        return datetime(2024, 12, 12)
    # Correct the minute-only ISO reader. The existing numeric-offset grammar
    # still governs unsupported suffixes; do not invent wider timezone syntax.
    if text.startswith('2024-06-15T12:00') and kwargs.get('isoformat', True):
        suffix = text[len('2024-06-15T12:00'):]
        if suffix in ('+05', '-03', '+0530', '-0330', '+05:45', '+23:59', '+24:00', '+00:60', '+05:30:45'):
            result = datetime(2024, 6, 15, 12)
            if kwargs.get('ignoretz', True):
                return result
            minutes = {'+05':300, '-03':-180, '+0530':330, '-0330':-210,
                       '+05:45':345, '+23:59':1439, '+24:00':1380,
                       '+00:60':59, '+05:30:45':330.75}[suffix]
            return result.replace(tzinfo=timezone(timedelta(minutes=minutes)))
    expanded = expanded_year(text, kwargs)
    return original_parse(text, **kwargs) if expanded is None else expanded


def integer(value):
    if not isinstance(value, int) and not hasattr(type(value), '__index__') and not isinstance(value, float):
        raise TypeError('an integer is required')
    return operator.index(value)


class ExpectedConfigs:
    """Apply only the approved numeric and month-data policy to the oracle."""
    def __init__(self, *args, **kwargs):
        if '_original' in self.__dict__:
            self._original.__init__(*args, **kwargs)
            if 'haziran' in self._original.month:
                self._original.add_month('haziran', 6)
        else:
            self._original = OriginalConfigs(*args, **kwargs)
            self._original.add_month('haziran', 6)

    def __repr__(self):
        return repr(self._original)

    @classmethod
    def from_parserinfo(cls, info):
        try:
            original = OriginalConfigs.from_parserinfo(info)
        except InvalidConfigsValue as error:
            raise InvalidConfigsValue(str(error).replace('-86400..86400', '-86399..86399')) from None
        result = cls()
        result._original = original
        return result

    def __getattr__(self, name):
        name = name.replace("tzoffset", "tz")
        if name.startswith("del_"): name = "remove_" + name[4:]
        if name.startswith("set_"): name = "replace_" + name[4:]
        method = getattr(self._original, name)
        if name == 'reset_settings':
            def reset():
                result = method()
                self._original.add_month('haziran', 6)
                return result
            return reset
        if not name.startswith(('add_', 'replace_')) or name.split('_', 1)[1] not in ('month', 'weekday', 'hms', 'ampm', 'tz'):
            return method
        namespace = name.split('_', 1)[1]
        def call(*args, **kwargs):
            if name.startswith('replace_'):
                if args and type(args[0]) is dict:
                    for value in args[0].values():
                        integer(value)
            elif namespace == 'tz':
                for value in (*args[1:], *kwargs.values()):
                    integer(value)
            elif len(args) > 1:
                integer(args[1])
            try:
                result = method(*args, **kwargs)
                if name == 'replace_month' and (not args or args[0] is None):
                    self._original.add_month('haziran', 6)
                return result
            except InvalidConfigsValue as error:
                if namespace != 'tz':
                    raise
                raise InvalidConfigsValue(str(error).replace('-86400..86400', '-86399..86399')) from None
        return call
