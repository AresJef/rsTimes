# Run the demos

Check out the source at `v1.0.0`. These commands set up the two demo
environments on macOS with ordinary CPython 3.13.

```sh
python3.13 -m venv .local/demo-1.0.0-oracle
.local/demo-1.0.0-oracle/bin/python -m pip install -r requirements-oracle.txt "rsTimes==1.0.0"
python3.13 -m venv .local/demo-1.0.0-main
.local/demo-1.0.0-main/bin/python -m pip install -r requirements-test.txt "rsTimes==1.0.0"
mkdir -p .local/demo-1.0.0
curl -fL https://github.com/AresJef/rsTimes/releases/download/v1.0.0/release-manifest.json -o .local/demo-1.0.0/release-manifest.json
```

Delta, Parser, and Pydt use the comparison environment, which includes
CyTimes and Babel. Pddt uses the separate main environment. Both install
the rsTimes wheel for the interpreter and platform.

Run the scripts from the checkout.

```sh
python demo/delta.py
python demo/parser.py
python demo/pydt.py
python demo/pddt.py
```

From another directory, use the script's absolute path. The launcher selects
the interpreter in [runtime.json](runtime.json) and checks the installed
version, package location, and native SHA-256 against the release manifest.
On Windows, a virtual environment's interpreter is `Scripts/python.exe`.
The optional comparison dependencies must also be available on the chosen
platform. Timing snippets in the demos are for interactive exploration.

The Parser demo includes 128-bit integers, grouped digits, and invalid
grouping. See the [date parsing guide](../docs/Parser对象解析使用说明.md) and
[numeric parsing guide](../docs/NumericParsing.md) for the input rules.
