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

    agent_use_notice = True # False
    sample_rate = 2

    # LLM
    llm_type = 'deepseek' # openai
    llm_key = 'api'  # 'sk-xxxxxx'
    llm_model = 'deepseek-chat' # gpt-4.0
    # memory
    rule_path = './Chroma/rule_db'
    memory_path = './Chroma/memory_db'
    # scenario_descriptor
    scenario_descriptor = 'blip2' # blip2, ours
    cache_path = '/home/ubuntu/FedDrive/src_data/models/blip2-opt-2.7B-cache'
    descriptor_name = 'Salesforce/blip2-opt-2.7b'
    # save
    image_path = "./carla_outputs/vision_text_llm_camera/image_caption"

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
