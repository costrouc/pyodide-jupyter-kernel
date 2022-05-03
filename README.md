# Introduction

[Pyodide](https://pyodide.org/en/stable/) and
[PyScript](https://github.com/pyscript/pyscript) enable running a
native CPython interpreter in browser. There are several projects that
leverage this including
[jupyterlite](https://jupyterlite.readthedocs.io/en/latest/). The idea
of this project is to enable easily running code via an annotation in
a remote ipykernel or locally in the web browser seamlessly. This is
similar to marking a function via the decorator
[dask.delayed](https://docs.dask.org/en/stable/delayed.html) and
having the option to scale out a given computation.

The only dependency for this project is `cloudpickle` installed in the
ipykernel environment.

# Usage

```shell
cd src
python -m http.server &
jupyter-server --ServerApp.allow_origin='*' --ServerApp.token='asdfqwerzxcvqwer'
```

Load in your web browser `localhost:8000` and run the following code.

```python
import asyncio
import jupyter

kernel_id, kernel = await jupyter.jupyter_client.ensure_kernel()
print(await kernel.send_code('costrouc', 'print(1)'))


def add(a, b):
    return a + b


@kernel.delayed
def mult(a, b):
    return a * b


@kernel.delayed
def get_host():
    import os
    import socket
    return os.getcwd(), socket.gethostname(), os.getuid()


print(add(1, await mult(3, 4)))
print(await get_host())
```
