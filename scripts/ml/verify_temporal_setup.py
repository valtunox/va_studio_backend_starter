
import asyncio
import sys
import os
from typing import Dict, Any

# Add project root
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

async def verify_setup():
    print("Verifying Temporal SDK Setup...")
    
    try:
        import temporalio
        from temporalio.client import Client
        print("✅ temporalio installed")
    except ImportError:
        print("❌ temporalio not found. Run: pip install temporalio")
        return

    try:
        from app.services.visual_workflow.temporal_client import TemporalClientWrapper
        print("✅ TemporalClientWrapper importable")
    except ImportError as e:
        print(f"❌ Failed to import TemporalClientWrapper: {e}")
        return

    try:
        from app.services.visual_workflow.temporal_workflows import VisualWorkflow
        print("✅ VisualWorkflow importable")
    except ImportError as e:
        print(f"❌ Failed to import VisualWorkflow: {e}")
        return
        
    try:
        from app.services.visual_workflow.activities import execute_infrastructure_node
        print("✅ Activities importable")
    except ImportError as e:
        print(f"❌ Failed to import activities: {e}")
        return

    print("\nAttempting to connect to Temporal (localhost:7233)...")
    try:
        # Mock connection or short timeout
        client = await Client.connect("localhost:7233")
        print("✅ Connected to Temporal Server")
    except Exception as e:
        print(f"⚠️ Could not connect to Temporal: {e}")
        print("Make sure Temporal server is running: 'temporal server start-dev'")

    print("\nVerification Complete.")

if __name__ == "__main__":
    asyncio.run(verify_setup())
