 #!/bin/bash
 
# export carla
export CARLA_ROOT=/home/ubuntu/carla
export CARLA_SERVER=${CARLA_ROOT}/CarlaUE4.sh
export PYTHONPATH=$PYTHONPATH:${CARLA_ROOT}/PythonAPI
export PYTHONPATH=$PYTHONPATH:${CARLA_ROOT}/PythonAPI/carla
export PYTHONPATH=$PYTHONPATH:$CARLA_ROOT/PythonAPI/carla/dist/carla-0.9.15-py3.7-linux-x86_64.egg
# export srunner
export PYTHONPATH=$PYTHONPATH:scenario_runner
# export leaderboard
export LEADERBOARD_ROOT=/home/ubuntu/carla_leader/leaderboard
export PYTHONPATH=$PYTHONPATH:leaderboard # can access leaderboard/leaderboard/scenario by leaderboard/scenario


export TEAM_AGENT=$LEADERBOARD_ROOT/leaderboard/autoagents/human_agent.py

export ROUTES=$LEADERBOARD_ROOT/data/routes_devtest.xml 
export ROUTES_SUBSET=0
export REPETITIONS=1

export DEBUG_CHALLENGE=1
export CHALLENGE_TRACK_CODENAME=SENSORS
export CHECKPOINT_ENDPOINT="${LEADERBOARD_ROOT}/results.json"
export RECORD_PATH=
export RESUME=

#!/bin/bash

python3 ${LEADERBOARD_ROOT}/leaderboard/leaderboard_evaluator.py \
--routes=${ROUTES} \
--routes-subset=${ROUTES_SUBSET} \
--repetitions=${REPETITIONS} \
--track=${CHALLENGE_TRACK_CODENAME} \
--checkpoint=${CHECKPOINT_ENDPOINT} \
--debug-checkpoint=${DEBUG_CHECKPOINT_ENDPOINT} \
--agent=${TEAM_AGENT} \
--agent-config=${TEAM_CONFIG} \
--debug=${DEBUG_CHALLENGE} \
--record=${RECORD_PATH} \
--resume=${RESUME}
