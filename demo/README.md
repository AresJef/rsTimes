# Run the demos

The selected demo environments use the verified rsTimes 1.1.1 public wheel.
The paths below match [runtime.json](runtime.json) on macOS with CPython 3.13.

```sh
python3.13 -m venv .local/releases/1.1.1/demo-public/oracle
.local/releases/1.1.1/demo-public/oracle/bin/python -m pip install -r requirements-oracle.txt "rsTimes==1.1.1"
python3.13 -m venv .local/releases/1.1.1/demo-public/main
.local/releases/1.1.1/demo-public/main/bin/python -m pip install -r requirements-test.txt "rsTimes==1.1.1"
curl -fL https://github.com/AresJef/rsTimes/releases/download/v1.1.1/release-manifest.json -o .local/releases/1.1.1/demo-public/release-manifest.json
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
For earlier releases, follow the demo guide and runtime selection in their own tags.
The optional comparison dependencies must also be available on the chosen
platform. Timing snippets in the demos are for interactive exploration.

The Parser demo includes 128-bit integers, grouped digits, and invalid
grouping. See the [date parsing guide (Chinese)](../docs/Parser对象解析使用说明.md) and
[numeric parsing guide](../docs/NumericParsing.md) for the input rules.
