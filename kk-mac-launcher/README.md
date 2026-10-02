# KK Mac Launcher core

`launcher.py` contains the side-effect-free pieces used by a macOS launcher:
SHA-256 validation, compatibility-runtime detection, and safe argv/env
construction.  It never invokes a shell and never downloads or executes the
attached Windows installer on its own.

Run the tests from this directory:

```sh
PYTHONPATH=. python -m unittest discover -s tests -v
```
