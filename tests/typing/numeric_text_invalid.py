from rstimes.parser import parse_to_float, parse_to_integer

parse_to_integer(b"12")
parse_to_integer("12", strict=1)
parse_to_float("12", allow_grouping="yes")
parse_to_float("12", False)
parse_to_integer("12", comma_decimal=True)
parse_to_float("12", comma_decimal=True)
