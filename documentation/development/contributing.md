# Contribute to rsTimes source

Use an isolated development checkout and environment. Public
Python wrappers and declarations are in `src/rstimes`. Native
implementation is in `rust`. Record the source commit, actual
import path, wheel and native identity, and dependency profile
when you compare behavior.

## Build and check an installed artifact

Use the pinned toolchain and development requirements for the
source commit. Build in a fresh artifact directory and install
that wheel in the intended verification environment before
running its installed-package checks. Use the repository's
[release procedure](https://github.com/AresJef/rsTimes/blob/v1.1.1/docs/RELEASING.md)
and the [developer environment guide](https://github.com/AresJef/rsTimes/blob/v1.1.1/docs/development.md)
for reproducible commands. For a docs change, follow the
[separate documentation workflow](documentation.md).

## Check types and demos in their intended environments

Use the [type-checking guide](../compatibility/type-checking.md)
for the pinned Pyright version, consumer applications and
optional static types. The repository's
[installed-package type gate](https://github.com/AresJef/rsTimes/blob/v1.1.1/docs/type-checking.md)
covers typed interfaces and retained negative tests.

Official comparison demos use a separate oracle environment.
See the [demo guide](https://github.com/AresJef/rsTimes/blob/v1.1.1/demo/README.md)
for launcher and interpreter selection.

## Make a behavior change reviewable

Start with a concrete input, actual behavior, and an independent
expected result. Check the return type, unit, timezone, validity,
shape and the applicable protocol or error. Execute native
expressions on real data. When changing behavior, preserve existing
cases that still describe the intended contract.
