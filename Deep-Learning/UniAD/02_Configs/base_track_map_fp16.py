_base_ = './base_track_map_fp32.py'

# FP16 Mixed Precision Training
fp16 = dict(loss_scale='dynamic')

# Override optimizer_config, remove cumulative_iters
# (FP16 does not support gradient accumulation)
optimizer_config = dict(
    grad_clip=dict(max_norm=35, norm_type=2)
)

# Torch Compile Configuration
# These settings will be read and applied via torch.compile in training script
compile_config = dict(
    enabled=True,
    mode='reduce-overhead',  # default | reduce-overhead | max-autotune
    backend='inductor',
    fullgraph=False,  # Allow graph breaks for better compatibility
    dynamic=True,  # Support dynamic shapes
)
