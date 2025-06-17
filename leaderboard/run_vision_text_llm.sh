# !/bin/bash
export PT=2000 # $(($RANDOM % 1000 + 16000))
# bash carla/CarlaUE4.sh --world-port=$PT &

sleep 4

export CARLA_ROOT=/home/ubuntu/carla
export CARLA_SERVER=${CARLA_ROOT}/CarlaUE4.sh
export PYTHONPATH=$PYTHONPATH:${CARLA_ROOT}/PythonAPI
export PYTHONPATH=$PYTHONPATH:${CARLA_ROOT}/PythonAPI/carla
export PYTHONPATH=$PYTHONPATH:$CARLA_ROOT/PythonAPI/carla/dist/carla-0.9.15-py3.7-linux-x86_64.egg
# export srunner
export PYTHONPATH=$PYTHONPATH:scenario_runner
# export leaderboard
export PYTHONPATH=$PYTHONPATH:leaderboard
export PYTHONPATH=$PYTHONPATH:leaderboard/team_code
export LEADERBOARD_ROOT=leaderboard

export CHALLENGE_TRACK_CODENAME=SENSORS
export PORT=$PT # same as the carla server port
export TM_PORT=$(($PT+500)) # port for traffic manager, required when spawning multiple servers/clients
export DEBUG_CHALLENGE=0
export REPETITIONS=1 # multiple evaluation runs

export ROUTES=$LEADERBOARD_ROOT/data/routes_devtest.xml
export TEAM_AGENT=$LEADERBOARD_ROOT/team_code/vision_text_llm_agent.py
export TEAM_CONFIG=$LEADERBOARD_ROOT/team_code/vision_text_llm_config.py
export CHECKPOINT_ENDPOINT=/home/ubuntu/AD_with_LLM/carla_outputs/vision_text_llm.json # results file
export SAVE_PATH=/home/ubuntu/AD_with_LLM/carla_outputs/ # path for saving episodes while evaluating
export RESUME=False
# new paramters
export ROUTES_SUBSET=0

echo ${LEADERBOARD_ROOT}/leaderboard/customized_leaderboard_evaluator.py
python3 -u  ${LEADERBOARD_ROOT}/leaderboard/customized_leaderboard_evaluator.py \
--routes-subset=${ROUTES_SUBSET} \
--routes=${ROUTES} \
--repetitions=${REPETITIONS} \
--track=${CHALLENGE_TRACK_CODENAME} \
--checkpoint=${CHECKPOINT_ENDPOINT} \
--agent=${TEAM_AGENT} \
--agent-config=${TEAM_CONFIG} \
--debug=${DEBUG_CHALLENGE} \
--record=${RECORD_PATH} \
--resume=${RESUME} \
--port=${PORT} \
--traffic-manager-port=${TM_PORT} >> carla_outputs/vision_text_llm.txt 2>&1 

