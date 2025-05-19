## Autonomous driving with LLM

Some agents based on LLM are implemented in `leaderboard/team_code`, where CARLA simulator is used.

#### Environment

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
git clone 
cd leaderboard
pip3 install -r requirements.txt
cd scenario_runner
pip3 install -r requirements.txt
```

#### Run

```
cd AD_with_LLM
CUDA_VISIBLE_DEVICES=1 ./leaderboard/run_leaderboard.sh
```

#### Acknowledgement

