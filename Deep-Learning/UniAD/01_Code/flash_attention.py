"""
FlashAttention wrapper for UniAD
支持在 UniAD 中使用 FlashAttention-2 加速注意力计算

Requirements:
    pip install flash-attn --no-build-isolation
"""

import warnings
import torch
import torch.nn as nn
from mmcv.cnn.bricks.registry import ATTENTION
from mmcv.runner.base_module import BaseModule
from mmcv.utils import deprecated_api_warning

try:
    from flash_attn import flash_attn_qkvpacked_func, flash_attn_func
    FLASH_ATTN_AVAILABLE = True
except ImportError:
    FLASH_ATTN_AVAILABLE = False
    warnings.warn(
        "FlashAttention not installed. "
        "Install it with: pip install flash-attn --no-build-isolation"
    )


@ATTENTION.register_module()
class FlashMultiheadAttention(BaseModule):
    """
    FlashAttention-2 wrapper compatible with MMDetection
    
    替代标准的 MultiheadAttention，提供 2-4x 加速和更低的内存占用
    
    Args:
        embed_dims (int): The embedding dimension.
        num_heads (int): Parallel attention heads.
        attn_drop (float): Dropout rate for attention weights. Default: 0.0
        proj_drop (float): Dropout rate after projection. Default: 0.0
        dropout_layer (dict): Dropout layer config. Default: dict(type='Dropout', drop_prob=0.)
        init_cfg (dict): Initialization config. Default: None
        batch_first (bool): If True, batch is first dimension. Default: True
        causal (bool): If True, use causal attention. Default: False
        
    Note:
        - FlashAttention 要求 FP16 或 BF16 精度
        - 需要 CUDA 架构 >= sm_80 (A100, H100 等)
        - batch_first 必须为 True
    """
    
    def __init__(self,
                 embed_dims,
                 num_heads,
                 attn_drop=0.,
                 proj_drop=0.,
                 dropout_layer=dict(type='Dropout', drop_prob=0.),
                 init_cfg=None,
                 batch_first=True,
                 causal=False,
                 **kwargs):
        super().__init__(init_cfg)
        
        if not FLASH_ATTN_AVAILABLE:
            raise ImportError(
                "FlashAttention is not available. "
                "Install it with: pip install flash-attn --no-build-isolation"
            )
        
        if not batch_first:
            warnings.warn(
                "FlashAttention requires batch_first=True. "
                "Automatically setting batch_first=True"
            )
            batch_first = True
        
        self.embed_dims = embed_dims
        self.num_heads = num_heads
        self.head_dim = embed_dims // num_heads
        self.attn_drop = attn_drop
        self.proj_drop_rate = proj_drop
        self.batch_first = batch_first
        self.causal = causal
        
        assert embed_dims % num_heads == 0, \
            f"embed_dims {embed_dims} must be divisible by num_heads {num_heads}"
        
        # QKV projection
        self.qkv = nn.Linear(embed_dims, embed_dims * 3, bias=True)
        
        # Output projection
        self.proj = nn.Linear(embed_dims, embed_dims, bias=True)
        self.proj_drop = nn.Dropout(proj_drop)
        
        # Dropout layer (compatible with MMCV 1.6.1)
        if dropout_layer is not None:
            if isinstance(dropout_layer, dict):
                dropout_prob = dropout_layer.get('drop_prob', proj_drop)
                self.dropout_layer = nn.Dropout(dropout_prob)
            else:
                self.dropout_layer = dropout_layer
        else:
            self.dropout_layer = nn.Identity()
    
    def forward(self,
                query,
                key=None,
                value=None,
                identity=None,
                query_pos=None,
                key_pos=None,
                attn_mask=None,
                key_padding_mask=None,
                **kwargs):
        """
        Forward function for FlashMultiheadAttention.
        
        Args:
            query (Tensor): [bs, num_query, embed_dims] if batch_first else [num_query, bs, embed_dims]
            key (Tensor): Same shape as query. If None, use query (self-attention)
            value (Tensor): Same shape as query. If None, use key
            identity (Tensor): Identity tensor for residual connection
            query_pos (Tensor): Positional encoding for query
            key_pos (Tensor): Positional encoding for key
            attn_mask (Tensor): Attention mask (not supported in FlashAttention)
            key_padding_mask (Tensor): Key padding mask (not supported in FlashAttention)
            
        Returns:
            Tensor: Output with same shape as input query
        """
        
        # FlashAttention 只支持 self-attention（或需要相同的 seq_len）
        # 这里简化处理，主要用于 self-attention 场景
        if key is not None or value is not None:
            warnings.warn(
                "FlashMultiheadAttention primarily supports self-attention. "
                "Cross-attention may fall back to standard implementation."
            )
        
        # 处理输入
        if not self.batch_first:
            query = query.transpose(0, 1)
        
        if identity is None:
            identity = query
        
        # 添加位置编码
        if query_pos is not None:
            query = query + query_pos
        
        # 保存原始形状和 dtype
        bs, seq_len, _ = query.shape
        orig_dtype = query.dtype
        
        # FlashAttention 要求 FP16 或 BF16
        if orig_dtype not in [torch.float16, torch.bfloat16]:
            query = query.half()
        
        # QKV projection: [bs, seq_len, 3 * embed_dims]
        qkv = self.qkv(query)
        
        # Reshape to [bs, seq_len, 3, num_heads, head_dim]
        qkv = qkv.reshape(bs, seq_len, 3, self.num_heads, self.head_dim)
        
        # FlashAttention forward
        # flash_attn_qkvpacked_func: (batch, seqlen, 3, nheads, headdim)
        out = flash_attn_qkvpacked_func(
            qkv,
            dropout_p=self.attn_drop if self.training else 0.0,
            causal=self.causal,
            softmax_scale=None,  # 默认 1/sqrt(head_dim)
        )
        
        # out: [bs, seq_len, num_heads, head_dim]
        # Reshape to [bs, seq_len, embed_dims]
        out = out.reshape(bs, seq_len, self.embed_dims)
        
        # Output projection
        out = self.proj(out)
        out = self.proj_drop(out)
        
        # 恢复原始 dtype
        if orig_dtype != out.dtype:
            out = out.to(orig_dtype)
        
        # 添加残差连接
        if not self.batch_first:
            out = out.transpose(0, 1)
            identity = identity.transpose(0, 1)
        
        out = identity + self.dropout_layer(out)
        
        return out


@ATTENTION.register_module()
class FlashCrossAttention(BaseModule):
    """
    FlashAttention-2 for Cross-Attention
    
    支持 Query 和 Key/Value 长度不同的场景
    
    Args:
        embed_dims (int): Embedding dimension
        num_heads (int): Number of attention heads
        attn_drop (float): Attention dropout rate
        proj_drop (float): Projection dropout rate
        dropout_layer (dict): Dropout layer config
        init_cfg (dict): Initialization config
        batch_first (bool): Batch first format
    """
    
    def __init__(self,
                 embed_dims,
                 num_heads,
                 attn_drop=0.,
                 proj_drop=0.,
                 dropout_layer=dict(type='Dropout', drop_prob=0.),
                 init_cfg=None,
                 batch_first=True,
                 **kwargs):
        super().__init__(init_cfg)
        
        if not FLASH_ATTN_AVAILABLE:
            raise ImportError(
                "FlashAttention is not available. "
                "Install it with: pip install flash-attn --no-build-isolation"
            )
        
        self.embed_dims = embed_dims
        self.num_heads = num_heads
        self.head_dim = embed_dims // num_heads
        self.attn_drop = attn_drop
        self.batch_first = batch_first
        
        assert embed_dims % num_heads == 0
        
        # Separate Q, K, V projections for cross-attention
        self.q_proj = nn.Linear(embed_dims, embed_dims, bias=True)
        self.k_proj = nn.Linear(embed_dims, embed_dims, bias=True)
        self.v_proj = nn.Linear(embed_dims, embed_dims, bias=True)
        
        # Output projection
        self.proj = nn.Linear(embed_dims, embed_dims, bias=True)
        self.proj_drop = nn.Dropout(proj_drop)
        
        # Dropout layer (compatible with MMCV 1.6.1)
        if dropout_layer is not None:
            if isinstance(dropout_layer, dict):
                dropout_prob = dropout_layer.get('drop_prob', proj_drop)
                self.dropout_layer = nn.Dropout(dropout_prob)
            else:
                self.dropout_layer = dropout_layer
        else:
            self.dropout_layer = nn.Identity()
    
    def forward(self,
                query,
                key=None,
                value=None,
                identity=None,
                query_pos=None,
                key_pos=None,
                attn_mask=None,
                key_padding_mask=None,
                **kwargs):
        """Cross-attention forward"""
        
        if not self.batch_first:
            query = query.transpose(0, 1)
            if key is not None:
                key = key.transpose(0, 1)
            if value is not None:
                value = value.transpose(0, 1)
        
        if identity is None:
            identity = query
        if key is None:
            key = query
        if value is None:
            value = key
        
        # Add positional encoding
        if query_pos is not None:
            query = query + query_pos
        if key_pos is not None:
            key = key + key_pos
        
        bs, q_len, _ = query.shape
        _, kv_len, _ = key.shape
        orig_dtype = query.dtype
        
        # Convert to FP16/BF16
        if orig_dtype not in [torch.float16, torch.bfloat16]:
            query = query.half()
            key = key.half()
            value = value.half()
        
        # Project Q, K, V
        q = self.q_proj(query).reshape(bs, q_len, self.num_heads, self.head_dim)
        k = self.k_proj(key).reshape(bs, kv_len, self.num_heads, self.head_dim)
        v = self.v_proj(value).reshape(bs, kv_len, self.num_heads, self.head_dim)
        
        # FlashAttention cross-attention
        out = flash_attn_func(
            q, k, v,
            dropout_p=self.attn_drop if self.training else 0.0,
            causal=False,
            softmax_scale=None,
        )
        
        # Reshape and project
        out = out.reshape(bs, q_len, self.embed_dims)
        out = self.proj(out)
        out = self.proj_drop(out)
        
        # Restore dtype
        if orig_dtype != out.dtype:
            out = out.to(orig_dtype)
        
        # Residual
        if not self.batch_first:
            out = out.transpose(0, 1)
            identity = identity.transpose(0, 1)
        
        out = identity + self.dropout_layer(out)
        
        return out
