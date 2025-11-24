import os
import sys
import torch

# Get path from command line or use default
if len(sys.argv) > 1:
    path = sys.argv[1]
else:
    path = os.path.join(
        os.getcwd(),
        'checkpoints/AgentLightningTutorial/math_agent_robust/global_step_125/actor/model_world_size_1_rank_0.pt'
    )
try:
    d = torch.load(path, map_location='cpu')
    print("Keys found:", len(d.keys()))
    print("Sample keys:", list(d.keys())[:10])
except Exception as e:
    print(e)
