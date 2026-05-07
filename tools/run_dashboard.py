"""Runner script for local FastAPI dashboard."""

import sys
from pathlib import Path
import uvicorn

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config

def main():
    print(f"Starting dashboard on http://{config.DASHBOARD_HOST}:{config.DASHBOARD_PORT}")
    if not config.CREALITY_CONTROL_ENABLED:
        print("Warning: Real controls are disabled. Set PRINTSENTINEL_CREALITY_CONTROL_ENABLED=true to enable.")
        
    uvicorn.run(
        "web_dashboard.app:app",
        host=config.DASHBOARD_HOST,
        port=config.DASHBOARD_PORT,
        reload=False
    )

if __name__ == "__main__":
    main()
