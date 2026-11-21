"""Observe the public receiver of an example while retaining its expected output."""

import ast
import builtins
from collections import defaultdict
from contextlib import redirect_stdout
import doctest
import inspect
import io
import json
import operator
import re
import sys
from types import (
    BuiltinFunctionType, FunctionType, MethodDescriptorType, MethodType, MethodWrapperType, ModuleType,
    WrapperDescriptorType,
)


CLASS_MODULES = {
    "Pldt": "rstimes.pldt", "Pddt": "rstimes.pddt", "Pydt": "rstimes.pydt",
    "Delta": "rstimes.delta", "Configs": "rstimes.parser",
    "RstimesError": "rstimes.errors", "ParseError": "rstimes.errors", "ConfigError": "rstimes.errors",
    "DependencyWarning": "rstimes.errors",
}
OPERATORS = {
    "Add": ("__add__", operator.add), "Sub": ("__sub__", operator.sub),
    "Mul": ("__mul__", operator.mul), "TrueDiv": ("__truediv__", operator.truediv),
    "FloorDiv": ("__floordiv__", operator.floordiv),
}
EXPR = "polars.expr.expr.Expr"
FRAME = "polars.dataframe.frame.DataFrame"
LAZY_FRAME = "polars.lazyframe.frame.LazyFrame"
QUERY_OWNERS = {FRAME, LAZY_FRAME, "polars.dataframe.group_by.GroupBy", "polars.lazyframe.group_by.LazyGroupBy"}
PROJECTIONS = {"select", "with_columns", "agg"}
KEEP_COLUMNS = {"lazy", "group_by", "sort", "filter", "slice", "head", "tail", "limit"}
NATIVE_SLOTS = (BuiltinFunctionType, MethodDescriptorType, WrapperDescriptorType)


def type_label(value):
    cls = value if isinstance(value, type) else type(value)
    return cls.__module__ + "." + cls.__qualname__


class Instrument(ast.NodeTransformer):
    def helper(self, helper, location, *arguments):
        call = ast.Call(ast.Name(helper, ast.Load()), list(arguments), [])
        return ast.copy_location(call, location)

    def visit_Call(self, node):
        target = node.func
        if isinstance(target, ast.Attribute):
            node.func = self.attribute(target, True)
        else:
            node.func = self.helper("_audit_callable", target, self.visit(target), ast.Constant(node.lineno))
        node.args = [self.visit(arg) for arg in node.args]
        node.keywords = [self.visit(arg) for arg in node.keywords]
        return node

    def attribute(self, node, invoked):
        return self.helper("_audit_attr", node, self.visit(node.value), ast.Constant(node.attr),
                           ast.Constant(invoked), ast.Constant(node.lineno))

    def visit_Attribute(self, node):
        return self.attribute(node, False) if isinstance(node.ctx, ast.Load) else self.generic_visit(node)

    def visit_BinOp(self, node):
        if type(node.op).__name__ not in OPERATORS:
            return self.generic_visit(node)
        return self.helper("_audit_binary", node, self.visit(node.left), self.visit(node.right),
                           ast.Constant(type(node.op).__name__), ast.Constant(node.lineno))


class Observer:
    def __init__(self, inventory):
        self.inventory = set(inventory)
        self.events = set()
        self.accessors = {}
        self.flows = {}
        self.columns = {}

    def owners(self, value):
        cls = value if isinstance(value, type) else type(value)
        for base in cls.__mro__:
            name = base.__name__
            module = sys.modules.get(CLASS_MODULES.get(name, ""))
            if module is not None and vars(module).get(name) is base:
                path = module.__name__ + "." + name if module.__name__ == "rstimes.errors" else "rstimes." + name
                yield path
        if type_label(value) in {"polars.series.series.Series", EXPR}:
            yield "polars." + cls.__name__

    def member(self, receiver, name):
        accessor = self.accessors.get(id(receiver))
        if accessor:
            _, path, actual = accessor
            return path + "." + name, actual
        if isinstance(receiver, ModuleType) and receiver.__name__.startswith("rstimes"):
            prefix = "rstimes.errors" if receiver.__name__ == "rstimes.errors" else "rstimes"
            return prefix + "." + name, receiver.__name__
        actual = type_label(receiver)
        for path in self.owners(receiver):
            member = path + "." + name
            if member in self.inventory:
                return member, actual
        return "", actual

    def record(self, path, receiver, effect, line):
        if path in self.inventory:
            self.events.add((path, receiver, effect, line))

    def flow(self, item, seen=None):
        if seen is None:
            seen = set()
        if id(item) in seen:
            return set()
        if type(item) in {tuple, list}:
            seen.add(id(item))
            return set().union(*(self.flow(value, seen) for value in item))
        if type(item) is dict:
            seen.add(id(item))
            return set().union(*(self.flow(value, seen) for value in item.values()))
        return self.flows.get(id(item), (None, set()))[1]

    def register_output(self, result, identities):
        if identities and type_label(result).startswith("polars.expr."):
            self.flows[id(result)] = (result, identities)

    def projection(self, source, args, kwargs):
        positional = []
        for item in args:
            positional.extend(item if type(item) in {list, tuple} else (item,))
        projected = {}
        for named, expr in [(None, item) for item in positional] + list(kwargs.items()):
            if type(expr) is str:
                output, roots = expr, (expr,)
            elif type_label(expr) == EXPR:
                meta = expr.meta
                try:
                    if meta.has_multiple_outputs():
                        return None
                    output, roots = (meta.output_name(raise_if_undetermined=False) if named is None else named,
                                     meta.root_names())
                except sys.modules["polars"].exceptions.PolarsError:
                    return None
                if output is None:
                    return None
            elif type_label(expr) == "polars.series.series.Series":
                output, roots = expr.name, ()
            else:
                return None
            projected[output if named is None else named] = self.flow(expr).union(
                *(source.get(root, set()) for root in roots))
        return projected

    def query(self, function, receiver, name, args, kwargs):
        incoming = self.columns.get(id(receiver), (None, {}))[1]
        if not incoming and not self.flow((args, kwargs)):
            return function(*args, **kwargs)
        if name in PROJECTIONS:
            projected = self.projection(incoming, args, kwargs)
            columns = {} if projected is None else (incoming | projected if name == "with_columns" else projected)
        else:
            columns = incoming

        try:
            result = function(*args, **kwargs)
        except Exception as error:
            if name in {"select", "collect"} and type_label(error) == "polars.exceptions.ComputeError":
                plugin = re.match(r"the plugin failed with message: Pldt\.(?:pldt\.)?(\w+)\b", str(error))
                if plugin:
                    entry = "polars.Expr.pldt." + plugin[1]
                    matching = {origin for origins in columns.values() for origin in origins if origin[0] == entry}
                    if len(matching) == 1:
                        _, actor, line = matching.pop()
                        self.record(entry, actor, name + "-raises", line)
            raise

        columns = {column: origins for column, origins in columns.items() if origins}
        materialized = type_label(result) == FRAME
        if columns and not materialized:
            self.columns[id(result)] = (result, columns)
        if materialized and result.height and name in {"select", "collect"}:
            for column in result.columns:
                for entry, actor, line in columns.get(column, ()):
                    self.record(entry, actor, name, line)
        return result

    def wrapped(self, function, receiver, name, path, actor, line):
        def observed(*args, **kwargs):
            if actor in QUERY_OWNERS and name in PROJECTIONS | KEEP_COLUMNS | {"collect"}:
                return self.query(function, receiver, name, args, kwargs)
            flow = self.flow((receiver, args, kwargs))
            own = {(path, actor, line)} if path.startswith("polars.Expr.pldt.") else set()
            try:
                result = function(*args, **kwargs)
            except Exception:
                self.record(path, actor, "raises", line)
                raise
            self.record(path, actor, "called", line)
            self.register_output(result, own | flow)
            return result
        return observed

    def attribute(self, receiver, name, invoked, line):
        value = getattr(receiver, name)
        path, actor = self.member(receiver, name)
        if name == "pldt":
            if actor == EXPR:
                root = "polars.Expr.pldt"
            elif actor == "polars.series.series.Series" or path == "rstimes.Pldt.pldt":
                root = "polars.Series.pldt"
            else:
                root = ""
            if root:
                self.accessors[id(value)] = (value, root, actor)
                self.record(root, actor, "read", line)
                if flow := self.flow(receiver):
                    self.flows[id(value)] = (value, flow)
        elif path in {"rstimes.Pddt.pddt", "rstimes.Pldt.dt", "rstimes.Pldt.plot", "rstimes.Pldt.ext"}:
            self.accessors[id(value)] = (value, path, actor)

        if invoked and callable(value):
            if isinstance(value, type) or isinstance(receiver, ModuleType):
                return self.callable(value, line)
            if path in self.inventory or actor.startswith("polars."):
                return self.wrapped(value, receiver, name, path, actor, line)
        else:
            self.record(path, actor, "read", line)
            own = {(path, actor, line)} if path.startswith("polars.Expr.pldt.") else set()
            self.register_output(value, own | self.flow(receiver))
        return value

    def constructor(self, cls, path, line):
        actor = type_label(cls)

        def observed(*args, **kwargs):
            self.record(path, actor, "constructor", line)
            if inspect.getattr_static(type(cls), "__call__") is not type.__call__:
                return cls(*args, **kwargs)

            name = path.rsplit(".", 1)[-1]
            owner = vars(sys.modules[CLASS_MODULES[name]])[name]
            methods = {}
            native = set()
            for member in ("__new__", "__init__"):
                descriptor = vars(owner).get(member)
                target = descriptor.__func__ if isinstance(descriptor, staticmethod) else descriptor
                if isinstance(target, FunctionType):
                    methods[target.__code__] = member
                elif isinstance(target, NATIVE_SLOTS) and inspect.getattr_static(cls, member) is descriptor:
                    native.add(member)

            def observe_slot(frame, event, arg):
                if event != "call" or frame.f_code not in methods:
                    return
                member = methods[frame.f_code]
                first_argument = frame.f_locals.get(frame.f_code.co_varnames[0])
                if (member == "__new__" and first_argument is cls
                        or member == "__init__" and type(first_argument) is cls):
                    self.record(path + "." + member, actor, "constructor", line)

            # type.__call__ enters the native allocator first. Returning an
            # exact instance through it also completes the effective init slot.
            if "__new__" in native:
                self.record(path + ".__new__", actor, "constructor", line)
            if methods:
                previous = sys.getprofile()
                sys.setprofile(observe_slot)
                try:
                    result = cls(*args, **kwargs)
                finally:
                    sys.setprofile(previous)
            else:
                result = cls(*args, **kwargs)
            if "__init__" in native and type(result) is cls:
                self.record(path + ".__init__", actor, "constructor", line)
            return result

        return observed

    def callable(self, value, line):
        if value is builtins.getattr:
            return self.named_attribute
        if isinstance(value, type):
            path = next(iter(self.owners(value)), "")
            if path in self.inventory:
                return self.constructor(value, path, line)
            return value
        if not isinstance(value, (BuiltinFunctionType, FunctionType, MethodType, MethodWrapperType)):
            return value
        host = getattr(value, "__self__", None)
        name = value.__name__
        if host is not None and host is not builtins:
            path, actor = self.member(host, name)
            if path in self.inventory or actor.startswith("polars."):
                return self.wrapped(value, host, name, path, actor, line)
        for module_name in ("rstimes", "rstimes.parser", "rstimes.pydt"):
            module = sys.modules.get(module_name)
            if module is not None and vars(module).get(name) is value:
                self.record("rstimes." + name, module_name, "called", line)
                break
        return value

    def named_attribute(self, receiver, name, *default):
        # A caller can use getattr for discovery without invoking the result.
        try:
            return self.attribute(receiver, name, False, 0)
        except AttributeError:
            if default:
                return default[0]
            raise

    def binary(self, left, right, kind, line):
        name, execute = OPERATORS[kind]
        reverse = "__r" + name[2:]
        watched = []
        for receiver, operation in ((left, name), (right, reverse)):
            path, actor = self.member(receiver, operation)
            if path in self.inventory:
                self.record(path, actor, "operator-candidate", line)
                target = inspect.getattr_static(type(receiver), operation, None)
                if isinstance(target, FunctionType):
                    watched.append((target.__code__, path, actor, receiver))

        def called(frame, event, arg):
            if event == "call":
                for code, path, actor, receiver in watched:
                    if frame.f_code is code and frame.f_locals.get(code.co_varnames[0]) is receiver:
                        self.record(path, actor, "operator", line)

        if watched:
            previous = sys.getprofile()
            sys.setprofile(called)
            try:
                result = execute(left, right)
            finally:
                sys.setprofile(previous)
        else:
            result = execute(left, right)
        self.register_output(result, self.flow((left, right)))
        return result

    def bindings(self):
        return {"_audit_attr": self.attribute, "_audit_callable": self.callable, "_audit_binary": self.binary}

    def observations(self):
        return [dict(entry=path, receiver=actor, effect=effect, line=line)
                for path, actor, effect, line in sorted(self.events)]


def rewrite(code, file, mode):
    return ast.fix_missing_locations(Instrument().visit(ast.parse(code, file, mode)))


def visible(source, observer, filename, expected_error):
    module = ModuleType("__main__")
    sys.modules["__main__"] = module
    scope = vars(module)
    scope.update(observer.bindings())
    stdout = io.StringIO()
    exception, message = None, None
    try:
        with redirect_stdout(stdout):
            exec(compile(rewrite(source, filename, "exec"), filename, "exec"), scope)
    except Exception as error:
        exception, message = type(error).__name__, str(error)
    printed = stdout.getvalue().rstrip("\n")
    if exception is not None and exception == expected_error:
        printed = "\n".join(part for part in (printed, f"{exception}: {message}") if part)
    return {"output": printed, "exception": exception, "uses": observer.observations()}


def contracts(groups, observer, filename):
    scope = {"__name__": "__rstimes_documentation_example__", **observer.bindings()}
    results = {}
    for name, code in groups.items():
        observer.events.clear()
        runner = doctest.DocTestRunner()
        log = io.StringIO()
        test = doctest.DocTestParser().get_doctest(code, scope, name, filename, 0)
        for example in test.examples:
            example.source = ast.unparse(rewrite(example.source, filename, "single")) + "\n"
        verdict = runner.run(test, out=log.write, clear_globs=False)
        scope.update(test.globs)
        results[name] = {"attempted": verdict.attempted, "failures": verdict.failed,
                         "errors": log.getvalue()[:5000], "uses": observer.observations()}
    return results


if __name__ == "__main__":
    config = json.load(sys.stdin)
    observer = Observer(config["inventory"])
    filename = config["filename"]
    if "code" in config:
        result = visible(config["code"], observer, filename, config.get("raises"))
    else:
        result = contracts(config["contracts"], observer, filename)
    print(json.dumps(result, ensure_ascii=False))
