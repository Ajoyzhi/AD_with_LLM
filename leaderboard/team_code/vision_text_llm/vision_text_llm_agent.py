import os
import json
import json5
import random
import datetime
import pathlib
import time
import imp
from collections import deque
import math
import re

import yaml
import cv2
import torch
import carla
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from easydict import EasyDict
from torchvision import transforms
from transformers import Blip2Processor, Blip2ForConditionalGeneration

from leaderboard.autoagents import autonomous_agent
from team_code.planner import RoutePlanner, InstructionPlanner
from team_code.pid_controller import PIDController

try:
    import pygame
except ImportError:
    raise RuntimeError("cannot import pygame, make sure pygame package is installed")

import base64
from openai import OpenAI

SAVE_PATH = os.environ.get("SAVE_PATH", 'eval')
# why these number?
IMAGENET_DEFAULT_MEAN = (0.485, 0.456, 0.406)
IMAGENET_DEFAULT_STD = (0.229, 0.224, 0.225)


class DisplayInterface(object):
    def __init__(self):
        self._width = 1200
        self._height = 900
        self._surface = None

        pygame.init()
        pygame.font.init()
        self._clock = pygame.time.Clock()
        self._display = pygame.display.set_mode(
            (self._width, self._height), pygame.HWSURFACE | pygame.DOUBLEBUF
        )
        pygame.display.set_caption("Vision LLM Agent")

    def run_interface(self, input_data):
        # set the interface shown for human
        rgb = input_data['rgb_front']
        rgb_left = input_data['rgb_left']
        rgb_right = input_data['rgb_right']
        rgb_focus = input_data['rgb_center']
        # 3 channels
        surface = np.zeros((900, 1200, 3), np.uint8)
        # show images from left, right and center cameras at the top of surface
        surface[:, :1200] = rgb
        surface[:210, :280] = input_data['rgb_left']
        surface[:210, 920:1200] = input_data['rgb_right']
        surface[:210, 495:705] = input_data['rgb_center']
        # figure, text, location, font, font size, font color, textbf
        surface = cv2.putText(surface, 'Left  View', (60, 245), cv2.FONT_HERSHEY_TRIPLEX, 0.75, (139, 69, 19), 2)
        surface = cv2.putText(surface, 'Focus View', (535, 245), cv2.FONT_HERSHEY_TRIPLEX, 0.75, (139, 69, 19), 2)
        surface = cv2.putText(surface, 'Right View', (980, 245), cv2.FONT_HERSHEY_TRIPLEX, 0.75, (139, 69, 19), 2)
        # show some texts at the bottom of surface
        surface = cv2.putText(surface, input_data['time'], (20, 710), cv2.FONT_HERSHEY_TRIPLEX, 0.75, (0, 0, 255), 1)
        surface = cv2.putText(surface, input_data['meta_control'], (20, 740), cv2.FONT_HERSHEY_TRIPLEX, 0.75,
                              (0, 0, 255), 1)
        surface = cv2.putText(surface, input_data['waypoints'], (20, 770), cv2.FONT_HERSHEY_TRIPLEX, 0.75, (0, 0, 255),
                              1)
        surface = cv2.putText(surface, input_data['instruction'], (20, 800), cv2.FONT_HERSHEY_TRIPLEX, 0.75,
                              (0, 0, 255), 1)
        surface = cv2.putText(surface, input_data['notice'], (20, 830), cv2.FONT_HERSHEY_TRIPLEX, 0.75, (0, 0, 255), 1)

        # set the color of edge as brown
        surface[:210, 278:282] = [139, 69, 19]
        surface[:210, 493:497] = [139, 69, 19]
        surface[:210, 703:707] = [139, 69, 19]
        surface[:210, 918:922] = [139, 69, 19]
        surface[208:212, :280] = [139, 69, 19]
        surface[208:212, 920:1200] = [139, 69, 19]
        surface[208:212, 495:705] = [139, 69, 19]

        self._surface = pygame.surfarray.make_surface(surface.swapaxes(0, 1))

        if self._surface is not None:
            self._display.blit(self._surface, (0, 0))

        pygame.display.flip()
        pygame.event.get()
        return surface

    def _quit(self):
        pygame.quit()


def get_entry_point():
    return "VisionTextLLMAgent"


class Resize2FixedSize:
    def __init__(self, size):
        self.size = size

    def __call__(self, pil_img):
        pil_img = pil_img.resize(self.size)
        return pil_img


def create_carla_rgb_transform(
        input_size, need_scale=True, mean=IMAGENET_DEFAULT_MEAN, std=IMAGENET_DEFAULT_STD
):
    # parameter "input_size" seems like a indicator for resizing
    if isinstance(input_size, (tuple, list)):
        img_size = input_size[-2:]
    else:
        img_size = input_size
    tfl = []

    if isinstance(input_size, (tuple, list)):
        input_size_num = input_size[-1]
    else:
        input_size_num = input_size

    if need_scale:
        if input_size_num == 112:
            tfl.append(Resize2FixedSize((170, 128)))
        elif input_size_num == 128:
            tfl.append(Resize2FixedSize((195, 146)))
        elif input_size_num == 224:
            tfl.append(Resize2FixedSize((341, 256)))
        elif input_size_num == 256:
            tfl.append(Resize2FixedSize((288, 288)))
        else:
            raise ValueError("Can't find proper crop size")
    tfl.append(transforms.CenterCrop(img_size))
    tfl.append(transforms.ToTensor())
    tfl.append(transforms.Normalize(mean=torch.tensor(mean), std=torch.tensor(std)))

    return transforms.Compose(tfl)


class VisionTextLLMAgent(autonomous_agent.AutonomousAgent):
    # setup function will be automatically called each time a route is initialized
    def setup(self, path_to_conf_file):
        self._hic = DisplayInterface()  # set the surface shown for human
        self.track = autonomous_agent.Track.SENSORS
        self.step = -1
        self.wall_start = time.time()
        self.initialized = False
        self.rgb_front_transform = create_carla_rgb_transform(224)
        self.rgb_left_transform = create_carla_rgb_transform(128)
        self.rgb_right_transform = create_carla_rgb_transform(128)
        self.rgb_center_transform = create_carla_rgb_transform(128, need_scale=False)

        self.active_misleading_instruction = False
        self.remaining_misleading_frames = 0

        self.visual_feature_buffer = []

        self.config = imp.load_source("MainModel", path_to_conf_file).GlobalConfig()

        self.turn_controller = PIDController(K_P=self.config.turn_KP, K_I=self.config.turn_KI, K_D=self.config.turn_KD,
                                             n=self.config.turn_n)
        self.speed_controller = PIDController(K_P=self.config.speed_KP, K_I=self.config.speed_KI,
                                              K_D=self.config.speed_KD, n=self.config.speed_n)

        self.agent_use_notice = self.config.agent_use_notice
        self.traffic_light_notice = ''
        self.curr_notice = ''
        self.now_notice_frame_id = -1
        self.sample_rate = self.config.sample_rate * 2  # The frequency of CARLA simulation is 20Hz

        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        print('use gpt-o4-mini...')
        self.net = OpenAI(
            api_key="your_api")
        self.prev_lidar = None
        self.prev_control = None
        self.curr_instruction = 'Drive safely.'
        self.sampled_scenarios = []
        self.instruction = ''

        self.image_id = 0
        self.change_instruction = 0

        # load blip2 model
        print("load blip2 model...")
        s1 = time.time()
        self.cache_dir = "/home/ubuntu/FedDrive/src_data/models/blip2-opt-2.7B-cache"
        self.blip2_processor = Blip2Processor.from_pretrained("Salesforce/blip2-opt-2.7b",
                                                   revision="51572668da0eb669e01a189dc22abe6088589a24",
                                                   cache_dir=self.cache_dir)
        self.blip2_model = Blip2ForConditionalGeneration.from_pretrained("Salesforce/blip2-opt-2.7b",
                                                              revision="51572668da0eb669e01a189dc22abe6088589a24",
                                                              cache_dir=self.cache_dir).to(self.device)
        print(f"The time to load blip2 model is {time.time()-s1}")

        # save the meta images
        self.save_path = None
        if SAVE_PATH is not None:
            now = datetime.datetime.now()
            string = pathlib.Path(os.environ["ROUTES"]).stem + "_"
            string += "_".join(
                map(
                    lambda x: "%02d" % x,
                    (now.month, now.day, now.hour, now.minute, now.second),
                )
            )

            print("Data save path:", string)

            self.save_path = pathlib.Path(SAVE_PATH) / string
            self.save_path.mkdir(parents=True, exist_ok=False)
            (self.save_path / "meta").mkdir(parents=True, exist_ok=False)

    def _init(self):
        # get the instruction and waypoints
        self._route_planner = RoutePlanner(5, 50.0)
        self._route_planner.set_route(self._global_plan, True)
        self._instruction_planner = InstructionPlanner(True)
        self.initialized = True
        random.seed(''.join([str(x[0]) for x in self._global_plan]))

    def sensors(self):
        return [
            {
                "type": "sensor.camera.rgb",
                "x": 1.3,
                "y": 0.0,
                "z": 2.3,
                "roll": 0.0,
                "pitch": 0.0,
                "yaw": 0.0,
                "width": 1200,
                "height": 900,
                "fov": 100,
                "id": "rgb_front",
            },
            {
                "type": "sensor.camera.rgb",
                "x": 1.3,
                "y": 0.0,
                "z": 2.3,
                "roll": 0.0,
                "pitch": 0.0,
                "yaw": -60.0,
                "width": 400,
                "height": 300,
                "fov": 100,
                "id": "rgb_left",
            },
            {
                "type": "sensor.camera.rgb",
                "x": 1.3,
                "y": 0.0,
                "z": 2.3,
                "roll": 0.0,
                "pitch": 0.0,
                "yaw": 60.0,
                "width": 400,
                "height": 300,
                "fov": 100,
                "id": "rgb_right",
            },
            {
                "type": "sensor.camera.rgb",
                "x": -1.3,
                "y": 0.0,
                "z": 2.3,
                "roll": 0.0,
                "pitch": 0.0,
                "yaw": 180.0,
                "width": 400,
                "height": 300,
                "fov": 100,
                "id": "rgb_rear",
            },
            {
                "type": "sensor.other.imu",
                "x": 0.0,
                "y": 0.0,
                "z": 0.0,
                "roll": 0.0,
                "pitch": 0.0,
                "yaw": 0.0,
                "sensor_tick": 0.05,
                "id": "imu",
            },
            {
                "type": "sensor.other.gnss",
                "x": 0.0,
                "y": 0.0,
                "z": 0.0,
                "roll": 0.0,
                "pitch": 0.0,
                "yaw": 0.0,
                "sensor_tick": 0.01,
                "id": "gps",
            },
            {"type": "sensor.speedometer", "reading_frequency": 20, "id": "speed"},
        ]

    def _get_position(self, tick_data):
        gps = tick_data["gps"]
        gps = (gps - self._route_planner.mean) * self._route_planner.scale
        return gps

    def tick(self, input_data):
        # based on the input data to find the next ground_truth waypoint
        rgb_front = cv2.cvtColor(input_data["rgb_front"][1][:, :, :3], cv2.COLOR_BGR2RGB)
        rgb_left = cv2.cvtColor(input_data["rgb_left"][1][:, :, :3], cv2.COLOR_BGR2RGB)
        rgb_right = cv2.cvtColor(
            input_data["rgb_right"][1][:, :, :3], cv2.COLOR_BGR2RGB
        )
        rgb_rear = cv2.cvtColor(
            input_data["rgb_rear"][1][:, :, :3], cv2.COLOR_BGR2RGB
        )
        gps = input_data["gps"][1][:2]
        speed = input_data["speed"][1]["speed"]
        compass = input_data["imu"][1][-1]
        if (
                math.isnan(compass) == True
        ):  # It can happen that the compass sends nan for a few frames
            compass = 0.0

        result = {
            "rgb_front": rgb_front,
            "rgb_left": rgb_left,
            "rgb_right": rgb_right,
            'rgb_rear': rgb_rear,
            "gps": gps,
            "speed": speed,
            "compass": compass,
        }

        pos = self._get_position(result)
        result["gps"] = pos
        # there are waypoint and command in the route
        next_wp, next_cmd = self._route_planner.run_step(pos)
        result["next_waypoint"] = next_wp
        result["next_command"] = next_cmd.value
        result['measurements'] = [pos[0], pos[1], compass, speed]
        result['speed'] = speed

        theta = compass + np.pi / 2
        R = np.array([[np.cos(theta), -np.sin(theta)], [np.sin(theta), np.cos(theta)]])

        local_command_point = np.array([next_wp[0] - pos[0], next_wp[1] - pos[1]])
        local_command_point = R.T.dot(local_command_point)
        result["target_point"] = local_command_point

        return result

    def control_pid(self, waypoints: list, velocity):
        '''
        Predicts vehicle control with a PID controller.
        Args:
            waypoints (tensor): predicted waypoints
            velocity (tensor): speedometer input
        '''
        assert (len(waypoints) == 5)
        waypoints = np.array(waypoints)

        # flip y is (forward is negative in our waypoints)
        waypoints[:, 1] *= -1
        speed = velocity

        desired_speed = np.linalg.norm(waypoints[0] - waypoints[1]) * 2.0
        brake = desired_speed < self.config.brake_speed or (speed / desired_speed) > self.config.brake_ratio

        aim = (waypoints[1] + waypoints[0]) / 2.0
        angle = np.degrees(np.pi / 2 - np.arctan2(aim[1], aim[0])) / 90
        if (speed < 0.01):
            angle = np.array(0.0)  # When we don't move we don't want the angle error to accumulate in the integral
        steer = self.turn_controller.step(angle)
        steer = np.clip(steer, -1.0, 1.0)

        delta = np.clip(desired_speed - speed, 0.0, self.config.clip_delta)
        throttle = self.speed_controller.step(delta)
        throttle = np.clip(throttle, 0.0, self.config.max_throttle)
        throttle = throttle if not brake else 0.0

        metadata = {
            'speed': float(speed.astype(np.float64)),
            'steer': float(steer),
            'throttle': float(throttle),
            'brake': float(brake),
            'wp_2': tuple(waypoints[1].astype(np.float64)),
            'wp_1': tuple(waypoints[0].astype(np.float64)),
            'desired_speed': float(desired_speed.astype(np.float64)),
            'angle': float(angle.astype(np.float64)),
            'aim': tuple(aim.astype(np.float64)),
            'delta': float(delta.astype(np.float64)),
        }

        return steer, throttle, brake, metadata

    # This method will be called once per time step
    # to produce a new action in the form of a carla.VehicleControl object
    def run_step(self, input_data, timestamp):
        if not self.initialized:
            self._init()

        self.step += 1
        tick_data = self.tick(input_data)
        # tick_data["rgb_front"] numpy, the shape of each image is [900, 1200, 3]

        if self.step < 20:
            control = carla.VehicleControl()
            control.steer = float(0)
            control.throttle = float(0)
            control.brake = float(1)
            return control

        if self.step % 2 != 0 and self.step > 4:
            return self.prev_control

        velocity = tick_data["speed"]
        command = tick_data["next_command"]

        # concatenate the images from 4 cameras
        images_list = []
        # rgb_front is 1200*900, which needs to be resized to 400*300
        rgb_front_resize = cv2.resize(tick_data['rgb_front'], (400, 300))
        images_list.append(rgb_front_resize)
        images_list.append(tick_data["rgb_left"])
        images_list.append(tick_data["rgb_right"])
        images_list.append(tick_data["rgb_rear"])

        # the generation for instruction and notice is not based on the images, but rules.
        last_instruction = self._instruction_planner.command2instruct(tick_data, self._route_planner.route)
        last_notice = self._instruction_planner.pos2notice(self.sampled_scenarios, tick_data)
        last_traffic_light_notice = self._instruction_planner.traffic_notice(tick_data)
        # last_misleading_instruction = self._instruction_planner.command2mislead(tick_data)
        last_misleading_instruction = ''

        if last_notice == '':
            last_notice = last_traffic_light_notice

        if self.curr_instruction != last_instruction or len(self.visual_feature_buffer) > 400:
            if self.remaining_misleading_frames > 0:
                self.remaining_misleading_frames = self.remaining_misleading_frames - 1
            else:
                self.active_misleading_instruction = False
                if last_misleading_instruction != '' and random.random() < 0.2:
                    self.curr_instruction = last_misleading_instruction
                    self.active_misleading_instruction = True
                    self.remaining_misleading_frames = 20
                else:
                    self.curr_instruction = last_instruction
                self.visual_feature_buffer = []
                self.image_id = 0
                self.change_instruction += 1
                self.curr_notice = ''
                self.curr_notice_frame_id = -1

        input_data = {}
        input_data['target_point'] = torch.tensor(tick_data['target_point']).cuda().view(1, 2).float()
        input_data['velocity'] = torch.tensor([tick_data['speed']]).cuda().view(1, 1).float()
        input_data['text_input'] = [self.curr_instruction]

        if last_notice != '' and last_notice != self.curr_notice:
            new_notice_flag = True
            self.curr_notice = last_notice
            # self.curr_notice_frame_id = image_embeds.size(1) - 1
        else:
            new_notice_flag = False

        if self.agent_use_notice:
            input_data['notice_text'] = [self.curr_notice]
            input_data['notice_frame_id'] = [self.curr_notice_frame_id]

        with torch.cuda.amp.autocast(enabled=True):
            # translate the image to words
            image_descriptions = []
            for image_opcv in images_list:
                image = Image.fromarray(image_opcv)
                s2_time = time.time()
                inputs = self.blip2_processor(images=image, return_tensors="pt").to(self.device, self.blip2_model.dtype)
                generated_ids = self.blip2_model.generate(**inputs)
                caption = self.blip2_processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
                print(f"the time to descript the figure is {time.time() - s2_time}, and the caption is {caption}")
                image_descriptions.append(caption)

            # save the image with caption
            self.image_id += 1
            save_path = "./carla_outputs/vision_text_llm_camera/image_caption" + str(self.change_instruction) + "_" + str(self.image_id)
            save_image_with_caption(images_list, image_descriptions, save_path)

            if self.curr_notice is '':
                self.curr_notice = 'please notice the traffic lights. When the traffic light is red, please stop util the lights turn green.'

            prompt = (
                f"You are a driver assistant for autonomous driving. "
                f"The front camera shows {image_descriptions[0]}, and the left camera shows {image_descriptions[1]}."
                f"The right camera shows {image_descriptions[2]}, and the rear camera shows {image_descriptions[3]}."
                f"The current instruction you receive is {self.curr_instruction}. "
                f"The things you should notice is {self.curr_notice}. "
                f"Your current speed is {velocity}, and target point is {input_data['target_point']}."
                "Please analyze the surroundings of the vehicle, and generate 5 waypoints."
                "Then give a float number to show stop probability whether the vehicle should stop."
                "All the outputs are returned in a JSON format, such as {analysis: []; output_waypoints: [[x1,y1], ...]; end_prob: []}."
                # f"Do not add any comments to the output. If you want to exaplain the waypoints, add the commnets to analysis part."
            )
            print("The prompt is ", prompt)

            start_time = time.time()
            response = self.net.responses.create(
                model="o4-mini",
                input=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": prompt},
                            #{"type": "input_image", "image_url": f"data:image/jpeg;base64,{base64_image}"},
                        ],
                    }
                ],
                max_output_tokens=2500,
            )
            print("The time to generate waypoints is ", time.time() - start_time)
            print(response.output_text)  # json

            # find waypoints and end_prob in text
            output_text = clean_json_string(response.output_text)
            outputs = safe_json_extract(output_text, ["output_waypoints", "end_prob"])

        waypoints = outputs['output_waypoints']
        end_prob1 = outputs['end_prob']

        if isinstance(end_prob1, list):
            end_prob = end_prob1[0]
        else:
            end_prob = end_prob1

        steer, throttle, brake, metadata = self.control_pid(waypoints, velocity)

        if end_prob > 0.75:
            self.visual_feature_buffer = []
            self.curr_notice = ''
            self.curr_notice_frame_id = -1

        if brake < 0.05:
            brake = 0.0
        if brake > 0.1:
            throttle = 0.0

        control = carla.VehicleControl()
        control.steer = float(steer) * 0.8
        control.throttle = float(throttle)
        control.brake = float(brake)

        display_data = {}
        display_data['rgb_front'] = cv2.resize(tick_data['rgb_front'], (1200, 900))
        display_data['rgb_left'] = cv2.resize(tick_data['rgb_left'], (280, 210))
        display_data['rgb_right'] = cv2.resize(tick_data['rgb_right'], (280, 210))
        display_data['rgb_center'] = cv2.resize(tick_data['rgb_front'][330:570, 480:720], (210, 210))
        if self.active_misleading_instruction:
            display_data['instruction'] = "Instruction: [Misleading] %s" % input_data['text_input'][0]
        else:
            display_data['instruction'] = "Instruction: %s" % input_data['text_input'][0]
        display_data['time'] = 'Time: %.3f. Frames: %d. End prob: %.2f' % (
            timestamp, self.image_id, end_prob)
        display_data['meta_control'] = 'Throttle: %.2f. Steer: %.2f. Brake: %.2f' % (
            control.steer, control.throttle, control.brake
        )
        display_data['waypoints'] = 'Waypoints: (%.1f, %.1f), (%.1f, %.1f)' % (
            waypoints[0][0], -waypoints[0][1], waypoints[1][0], -waypoints[1][1])
        display_data['notice'] = "Notice: %s" % last_notice
        surface = self._hic.run_interface(display_data)
        tick_data['surface'] = surface

        if self.step % 2 != 0 and self.step > 4:
            control = self.prev_control
        else:
            self.prev_control = control

        if SAVE_PATH is not None:
            self.save(tick_data)

        return control

    def save(self, tick_data):
        frame = (self.step - 20)
        Image.fromarray(tick_data["surface"]).save(
            self.save_path / "meta" / ("%04d.jpg" % frame)
        )
        return

def clean_json_string(json_str):
    # Strip whitespace
    json_str = json_str.strip()
    # Try to find the outermost valid JSON structure
    if json_str.startswith('{'):
        bracket_count = 0
        for i, char in enumerate(json_str):
            if char == '{':
                bracket_count += 1
            elif char == '}':
                bracket_count -= 1
                if bracket_count == 0:
                    return json_str[:i+1]
    elif json_str.startswith('['):
        bracket_count = 0
        for i, char in enumerate(json_str):
            if char == '[':
                bracket_count += 1
            elif char == ']':
                bracket_count -= 1
                if bracket_count == 0:
                    return json_str[:i+1]
    return json_str


def safe_json_extract(text, fields):
    try:
        json_data = json5.loads(re.search(r'\{.*\}', text, re.DOTALL).group())
        return {field: json_data.get(field) for field in fields}
    except Exception as e:
        print(e)
        cleaned = re.sub(r'//.*?$|/\*.*?\*/', '', text, flags=re.MULTILINE | re.DOTALL)
        json_data = json.loads(re.search(r'\{.*\}', cleaned, re.DOTALL).group())
        return {field: json_data.get(field) for field in fields}

def save_image_with_caption(images: list, captions: list, save_path: str):
    for id, (image_opcv, caption) in enumerate(zip(images, captions)):
        image = Image.fromarray(image_opcv)
        # Draw the caption on the image
        draw = ImageDraw.Draw(image)

        # Choose a font (fallback to default if not available)
        try:
            font = ImageFont.truetype("arial.ttf", 20)
        except IOError:
            font = ImageFont.load_default()

        # Determine size and position
        text_position = (10, 10)  # top-left corner
        text_color = (255, 255, 255)  # white text
        outline_color = (0, 0, 0)  # black outline

        # Draw text with outline for better readability
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                draw.text((text_position[0] + dx, text_position[1] + dy), caption, font=font, fill=outline_color)
        draw.text(text_position, caption, font=font, fill=text_color)

        # Save or show the image
        if not os.path.exists(save_path):
            os.mkdir(save_path)
        image.save(save_path + "/" + str(id) + ".jpg")
        print("Captioned image saved to:", save_path)
