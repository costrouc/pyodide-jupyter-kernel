import js
import pyodide
from pyodide.http import pyfetch

import asyncio
from urllib.parse import urlparse
import uuid
import json
import base64

import cloudpickle


class JupyterAPI:
    def __init__(self, notebook_url: str, api_token : str):
        self.api_url = f'{notebook_url}/api'
        self.api_token = api_token

    async def request(self, url : str, method : str = 'GET', data=None, headers=None):
        headers = headers or {}
        options = {
            'method': method,
            'headers': {
                'Authorization': f'token {self.api_token}',
                **headers
            },
        }
        if data:
            options['body'] = data
        return await pyfetch(url, **options)

    async def status(self):
        response = await self.request(self.api_url)
        return await response.json()

    async def create_kernel(self, kernel_spec=None):
        data = {"kernel_spec": kernel_spec} if kernel_spec else {}
        response = await self.request(
            f'{self.api_url}/kernels',
            method='POST',
            data=json.dumps(data),
        )
        return await response.json()

    async def list_kernel_specs(self):
        response = await self.request(f'{self.api_url}/kernelspecs')
        return await response.json()

    async def list_kernels(self):
        response = await self.request(f'{self.api_url}/kernels')
        return await response.json()

    async def get_kernel(self, kernel_id):
        response = await self.request(f'{self.api_url}/kernels/{kernel_id}')
        if response.status == 404:
            return None
        elif response.status == 200:
            return await response.json()

    async def ensure_kernel(self, kernel_spec=None):
        kernel_specs = await self.list_kernel_specs()
        if kernel_spec is None:
            kernel_spec = kernel_specs["default"]
        else:
            available_kernel_specs = list(kernel_specs["kernelspecs"].keys())
            if kernel_spec not in kernel_specs["kernelspecs"]:
                print(
                    f"kernel_spec={kernel_spec} not listed in available kernel specifications={available_kernel_specs}"
                )
                raise ValueError(
                    f"kernel_spec={kernel_spec} not listed in available kernel specifications={available_kernel_specs}"
                )

        kernel_id = (await self.create_kernel(kernel_spec=kernel_spec))["id"]
        jupyter_kernel = JupyterKernelAPI(
            f'{self.api_url}/kernels/{kernel_id}',
            self.api_token,
        )
        await jupyter_kernel.initialize()
        return kernel_id, jupyter_kernel


class JupyterKernelAPI:
    def __init__(self, kernel_url, api_token):
        self.api_url = kernel_url
        self.api_token = api_token

    async def initialize(self):
        parsed_url = urlparse(self.api_url)
        self.websocket = js.WebSocket.new(f'ws://{parsed_url.netloc}{parsed_url.path}/channels?token={self.api_token}')

        self.queue = asyncio.Queue()

        def handleMessage(event):
            self.queue.put_nowait(event.data)

        self.websocket.addEventListener(
            'message',
            pyodide.create_proxy(handleMessage))

        def handleOpen(event):
            self.queue.put_nowait('ready')

        self.websocket.addEventListener(
            'open',
            pyodide.create_proxy(handleOpen))

        # collect the 'ready' task
        await self.queue.get()

    def request_execute_code(self, msg_id, username, code):
        return {
            "header": {
                "msg_id": msg_id,
                "username": username,
                "msg_type": "execute_request",
                "version": "5.2",
            },
            "metadata": {},
            "content": {
                "code": code,
                "silent": False,
                "store_history": True,
                "user_expressions": {},
                "allow_stdin": True,
                "stop_on_error": True,
            },
            "buffers": [],
            "parent_header": {},
            "channel": "shell",
        }

    async def send_code(self, username, code, wait=True, timeout=None):
        msg_id = str(uuid.uuid4())

        self.websocket.send(
            json.dumps(self.request_execute_code(msg_id, username, code))
        )

        if not wait:
            return None

        stdout_lines = []
        stderr_lines = []
        result = None

        while True:
            message = await self.queue.get()
            msg = json.loads(message)

            if "parent_header" in msg and msg["parent_header"].get("msg_id") == msg_id:
                if msg["msg_type"] == "error":
                    raise eval(msg["content"]["ename"])(msg["content"]["evalue"])
                elif msg["channel"] == "iopub":
                    if msg["msg_type"] == "execute_result":
                        result = msg["content"]["data"]["text/plain"]
                        break
                    elif msg["msg_type"] == "stream" and msg['content']['name'] == 'stdout':
                        stdout_lines.append(msg["content"]["text"])
                    elif msg["msg_type"] == "stream" and msg['content']['name'] == 'stderr':
                        stderr_lines.append(msg["content"]["text"])
                    # cell did not produce output
                    elif msg["content"].get("execution_state") == "idle":
                        break

        return ''.join(stdout_lines), ''.join(stderr_lines), result

    def delayed(self, func):
        function_pickle = base64.b64encode(cloudpickle.dumps(func)).decode('utf-8')
        code = '''
import base64
import cloudpickle
function = cloudpickle.loads(base64.b64decode(b'{function_pickle}'))
args, kwargs = cloudpickle.loads(base64.b64decode(b'{function_args}'))
result = function(*args, **kwargs)
base64.b64encode(cloudpickle.dumps(result)).decode('utf-8')
'''

        async def wrapper(*args, **kwargs):
            function_args = base64.b64encode(cloudpickle.dumps((args, kwargs))).decode('utf-8')
            stdout, stderr, result = await self.send_code('jupyter-api', code.format(
                function_pickle=function_pickle, function_args=function_args)
            )

            result = cloudpickle.loads(base64.b64decode(result[1:-1].encode('utf-8')))
            return result

        return wrapper


# jupyter-server --ServerApp.allow_origin='*' --ServerApp.token='asdfqwerzxcvqwer'
jupyter_client = JupyterAPI('http://localhost:8888', api_token='asdfqwerzxcvqwer')


# import asyncio
# import jupyter
# jupyter_client = jupyter.jupyter_client
# kernel_id, kernel = await jupyter_client.ensure_kernel()
# print(await kernel.send_code('costrouc', 'print(1)'))


# def foo():
#     import os
#     return 42, os.getcwd()


# @kernel.delayed
# def foo_async():
#     import os
#     return 42, os.getcwd()


# print(foo())
# print(await foo_async())
