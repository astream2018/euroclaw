# docs/generate_architecture.py
from diagrams import Diagram, Cluster
from diagrams.onprem.client import User
from diagrams.onprem.network import Internet
from diagrams.onprem.compute import Server
from diagrams.onprem.security import Vault
from diagrams.programming.language import Python

with Diagram("EuroClaw Zero-Trust Architecture", show=False, filename="docs/euroclaw_architecture"):
    user = User("Enterprise User")
    
    with Cluster("Sovereign Boundary (EU)"):
        gateway = Internet("OIDC / API Gateway")
        
        with Cluster("Agent Orchestration"):
            router = Python("Semantic Router")
            planner = Python("Planning Agent")
            
        with Cluster("Hardware Isolation (KVM)"):
            vm1 = Server("Firecracker MicroVM")
            vm2 = Server("Firecracker MicroVM")
            
        audit = Vault("OpenTelemetry Trace Log")

    # Define the execution flow
    user >> gateway >> router >> planner
    planner >> vm1
    planner >> vm2
    
    # Define the telemetry flow
    vm1 >> audit
    vm2 >> audit
    router >> audit