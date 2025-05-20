## Autonomous driving with LLM

Some agents based on LLM are implemented in `leaderboard/team_code`, where CARLA simulator is used.

#### Environments

Since the project runs in CARLA leaderboard, the CARLA should be installed firstly.

```python
# python3.9 doesn't match the carla version 0.9.15, but python3.8 or 3.7 do.
conda create -n carla_py38 python=3.8
conda activate carla_py38

mkdir carla
cd carla
# you can also download carla from https://github.com/carla-simulator/carla/blob/master/Docs/download.md
# we choose the lastest version carla0.9.15
wget https://tiny.carla.org/carla-0-9-15-linux (--no-check-certificate)
tar -zxvf carla-0-9-15-linux
# run carla server
CUDA_VISIBLE_DEVICES=0 ./CarlaUE4.sh -RenderOffScreen -nosound -quality-level=Low --world-port=2000 -opengl&

# you can test whether the installation is successful with the following commonds.
cd carla/PythonAPI/examples
# install the requirements in the conda environment
pip install -r requirements.txt
python3 generate_traffic.py
```

Then, download the code and install the requirements in the conda environment.

```python
git clone git@github.com:Ajoyzhi/AD_with_LLM.git
cd AD_with_LLM
cd leaderboard
pip3 install -r requirements.txt
cd scenario_runner
pip3 install -r requirements.txt
# additional packages
pip3 install json5
pip3 install torch
pip3 install easydict
pip3 install torchvision
pip3 install openai
pip3 install transformers
```

#### Run

```
cd AD_with_LLM
# run the examples in carla leaderboard
CUDA_VISIBLE_DEVICES=1 ./leaderboard/run_leaderboard.sh
# run the agent based on GPT4
CUDA_VISIBLE_DEVICES=1 ./leaderboard/run_vision_llm.sh
# run the agent based on blip2 and GPT4. It translates images to words and the words is taken as the prompt for GPT4 
CUDA_VISIBLE_DEVICES=1 ./leaderboard/run_vision_text_llm.sh
```

#### Acknowledgement

Thanks [carla-simulator](https://github.com/carla-simulator/carla) and [LMDrive](https://github.com/opendilab/LMDrive).

