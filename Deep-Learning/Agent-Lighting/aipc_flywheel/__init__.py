"""
AIPC Agent Training Flywheel
============================

A complete closed-loop training pipeline using Agent Lightning framework.

Stages:
    1. Data Generation - Generate domain-specific training data
    2. SFT Training - Supervised fine-tuning for cold start
    3. GRPO Training - Reinforcement learning with domain rewards
    4. Evaluation - Assess model quality with LLM Judge
    5. Feedback Loop - Generate correction data from failures

Author: Xinyu Wei (xinyuwei@microsoft.com)
License: MIT
"""

__version__ = "1.0.0"
__author__ = "Xinyu Wei"
