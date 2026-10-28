"""Pure outcome comparison shared by live and frozen upstream tests."""

def _legacy_error(record):
    """Remove the oracle's superseded parse/constructor wrappers only."""
    name = record.get('type', '').rsplit('.', 1)[-1]
    cause = record.get('cause')
    if cause and (name == 'ParserFailedError' or 'Cannot create datetime using custom' in record.get('message', '')):
        return _legacy_error(cause)
    return record


def error_category(record, *, legacy=False):
    """Classify approved input errors; unwrap only the legacy oracle."""
    if legacy:
        record = _legacy_error(record)
    name = record.get('type', '').rsplit('.', 1)[-1]
    if name in ('ParseError', 'ConfigError', 'ParserFailedError', 'InvalidArgumentError', 'InvalidConfigsValue', 'InvalidConfigsToken', 'InvalidMonthError', 'InvalidWeekdayError'):
        message = record.get('message', '')
        if legacy and name == 'InvalidArgumentError' and any(text in message for text in ('must be a string', 'incorrect type', 'an integer is required')):
            return 'TypeError'
        return 'ValueError'
    if name in ('InvalidTypeError', 'InvalidParserInfo', 'cyTimesTypeError'):
        return 'TypeError'
    return name


def outcomes_equal(actual, expected):
    """Keep every successful field exact; D37 changes only failure presentation."""
    if isinstance(actual, dict) and isinstance(expected, dict):
        if 'error' in actual and 'error' in expected:
            category = error_category(expected['error'], legacy=True)
            if category in ('TypeError', 'ValueError', 'OverflowError'):
                return error_category(actual['error']) == category
            return actual['error'] == _legacy_error(expected['error'])
        return actual.keys() == expected.keys() and all(outcomes_equal(actual[key], expected[key]) for key in actual)
    if isinstance(actual, list) and isinstance(expected, list):
        return len(actual) == len(expected) and all(outcomes_equal(a, e) for a, e in zip(actual, expected))
    return actual == expected
