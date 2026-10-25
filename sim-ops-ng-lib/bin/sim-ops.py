import os
import logging
from dotenv import load_dotenv

# before importing so: settings such as the MinIO endpoint are read at import
load_dotenv(override=False)

from so import SimOps
from so.utils import run_until_signalled

# Configure logging to output to stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    scenario = os.getenv("SIM_OPS_NG_SCENARIO", "data/demo.json")

    # ---- create SimOps instance ----
    # Authentication lives entirely in the API layer (SimOpsAPI); the sim engine holds no passwords.
    sim = SimOps(
        scenario=scenario,
    )

    # Socket server starts automatically (SIM_OPS_NG_SOCKET_HOST/PORT)
    address = sim.socket_address
    print(f"SimOps started with socket server on {address}")
    print(f"Connect API to: {address}")
    print(f"Scenario: {scenario}")

    run_until_signalled(sim.shutdown, "SimOps")


if __name__ == "__main__":
    main()
