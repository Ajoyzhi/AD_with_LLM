import os
import torch


class GlobalConfig:
    """base architecture configurations"""

    # Controller
    turn_KP = 1.25
    turn_KI = 0.75
    turn_KD = 0.3
    turn_n = 40  # buffer size

    speed_KP = 5.0
    speed_KI = 0.5
    speed_KD = 1.0
    speed_n = 40  # buffer size

    max_throttle = 0.75  # upper limit on throttle signal value in dataset
    brake_speed = 0.1  # desired speed below which brake is triggered
    brake_ratio = 1.1  # ratio of speed to desired speed at which brake is triggered
    clip_delta = 0.35  # maximum change in speed input to logitudinal controller

    agent_use_notice = False
    sample_rate = 2

    # openai
    openai_key = 'api'  # 'sk-xxxxxx'
    openai_chat_model = 'gpt-4-1106-preview'

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
