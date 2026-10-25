
import os
import logging
from dotenv import load_dotenv

# before importing so: settings such as the MinIO endpoint are read at import
load_dotenv(override=False)

from so.api import SimOpsAPI
from so.utils import run_until_signalled

# Configure logging to output to stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    api_host = os.getenv("SIM_OPS_NG_API_HOST", "0.0.0.0")
    api_port = int(os.getenv("SIM_OPS_NG_API_PORT", "9111"))

    simops_host = os.getenv("SIM_OPS_NG_SOCKET_HOST", "127.0.0.1")
    simops_port = int(os.getenv("SIM_OPS_NG_SOCKET_PORT", "5555"))

    # ---- create API instance ----
    api = SimOpsAPI(
        host=api_host,
        port=api_port,
        simops_host=simops_host,
        simops_port=simops_port
    )

    # ---- start API service ----
    print(f"Starting SimOpsAPI on {api_host}:{api_port}")
    print(f"Connecting to SimOps on {simops_host}:{simops_port}")

    api.start()

    print("API started successfully!")
    print(f"Access at: http://localhost:{api_port}")

    run_until_signalled(api.stop, "SimOpsAPI")


if __name__ == "__main__":
    main()
