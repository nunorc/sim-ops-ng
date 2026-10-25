#!/usr/bin/env python

"""Flask admin interface for SimOps - Starts the web UI"""

import os
from dotenv import load_dotenv
from gunicorn.app.base import BaseApplication

load_dotenv(override=False)

from so.admin import app, TRIGGER_TIMEOUT

def main():
    host = os.getenv("SIM_OPS_NG_ADMIN_HOST", "0.0.0.0")
    port = int(os.getenv("SIM_OPS_NG_ADMIN_PORT", "9131"))
    workers = int(os.getenv("SIM_OPS_NG_ADMIN_WORKERS", "4"))

    api_url = os.getenv("SIM_OPS_NG_API_URL", "http://localhost:9111")

    print("Starting SimOps Admin Interface")
    print(f"Listening on {host}:{port}")
    print(f"Connecting to API at {api_url}")
    print(f"Workers: {workers}")
    print()
    print(f"Access at: http://localhost:{port}")

    # init() is only called by gunicorn's own CLI parsing, which StandaloneApp doesn't use
    class StandaloneApp(BaseApplication):  # pylint: disable=abstract-method
        def __init__(self, wsgi_app, options=None):
            self.application = wsgi_app
            self.options = options or {}
            super().__init__()

        def load_config(self):
            for key, value in self.options.items():
                self.cfg.set(key.lower(), value)

        def load(self):
            return self.application

    options = {
        "bind": f"{host}:{port}",
        "workers": workers,
        "worker_class": "sync",
        # a trigger runs synchronously in the request: outlast its timeout, or the worker is killed first
        "timeout": TRIGGER_TIMEOUT + 30,
    }
    StandaloneApp(app, options).run()


if __name__ == "__main__":
    main()
