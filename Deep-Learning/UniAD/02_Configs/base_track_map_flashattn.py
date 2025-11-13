_base_ = ['./base_track_map.py']

# Enable FP16 Mixed Precision Training
fp16 = dict(loss_scale=512.)

# FlashAttention Configuration
# Modify model attention layers to use FlashAttention
# Note: Encoder keeps original MultiheadAttention (not using FlashAttention)
# Mixing FlashAttention and MultiScaleDeformableAttention in Encoder
# causes dimension incompatibility
# Only use FlashAttention in Decoder for acceleration
model = dict(
    pts_bbox_head=dict(
        transformer=dict(
            decoder=dict(
                transformerlayers=dict(
                    attn_cfgs=[
                        # Self-attention: Use FlashAttention for acceleration
                        dict(
                            type='FlashMultiheadAttention',
                            embed_dims=256,
                            num_heads=8,
                            attn_drop=0.1,
                            proj_drop=0.1,
                            dropout_layer=dict(type='Dropout', drop_prob=0.1),
                            batch_first=False,
                        ),
                        # Cross-attention: Keep original
                        # CustomMSDeformableAttention
                        dict(
                            type='CustomMSDeformableAttention',
                            embed_dims=256,
                            num_levels=1,
                        )
                    ],
                    feedforward_channels=512,
                    ffn_dropout=0.1,
                    operation_order=(
                        'self_attn', 'norm',
                        'cross_attn', 'norm',
                        'ffn', 'norm'
                    ),
                )
            )
        )
    )
)

# DataLoader Optimization
data = dict(
    workers_per_gpu=8,
    persistent_workers=True,
)

# Checkpoint Optimization
checkpoint_config = dict(
    interval=1,
    max_keep_ckpts=3,
)

# Runner Configuration
total_epochs = 6
runner = dict(type='EpochBasedRunner', max_epochs=6)
