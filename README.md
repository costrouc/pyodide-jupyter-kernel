# Usage

```shell
cd src
python -m http.server &
jupyter-server --ServerApp.allow_origin='*' --ServerApp.token='asdfqwerzxcvqwer'
```

Load in your web browser `localhost:8000` and run the code in `src/code.py`

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
    raise Exception('asdfasdfasdfsadf')
    return os.getcwd(), socket.gethostname(), os.getuid()


print(add(1, await mult(3, 4)))
print(await get_host())
```
