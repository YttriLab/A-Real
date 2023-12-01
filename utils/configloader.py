"""
DeepLabStream
© J.Schweihoff, M. Loshakov
University Bonn Medical Faculty, Germany
https://github.com/SchwarzNeuroconLab/DeepLabStream
Licensed under GNU General Public License v3.0
"""

import time
import os
import configparser as cfg

# loading DeepLabStream configuration
# remember when it was called DSC?
dsc_config = cfg.ConfigParser()
adv_dsc_config = cfg.ConfigParser()


def get_script_path():
    return os.path.dirname(os.path.join(os.path.dirname(__file__), ".."))


cfg_path = os.path.join(os.path.dirname(__file__), "..", "settings.ini")
with open(cfg_path) as cfg_file:
    dsc_config.read_file(cfg_file)

adv_cfg_path = os.path.join(os.path.dirname(__file__), "advanced_settings.ini")
with open(adv_cfg_path) as adv_cfg_file:
    adv_dsc_config.read_file(adv_cfg_file)
# DeepLabCut
# deeplabcut_config = dict(dsc_config.items('DeepLabCut'))

# poseestimation
MODEL_ORIGIN = dsc_config["Pose Estimation"].get("MODEL_ORIGIN")
model_path_string = [
    str(part).strip()
    for part in dsc_config["Pose Estimation"].get("MODEL_PATH").split(",")
]
MODEL_PATH = model_path_string[0] if len(model_path_string) <= 1 else model_path_string
MODEL_NAME = dsc_config["Pose Estimation"].get("MODEL_NAME")
ALL_BODYPARTS = tuple(
    part.strip()
    for part in dsc_config["Pose Estimation"].get("ALL_BODYPARTS").split(",")
)


# Streaming items

try:
    RESOLUTION = tuple(
        int(part) for part in dsc_config["Streaming"].get("RESOLUTION").split(",")
    )
except ValueError:
    print(
        "Incorrect resolution in config!\n"
        'Using default value "RESOLUTION = 848, 480"'
    )
    RESOLUTION = (848, 480)

FRAMERATE = dsc_config["Streaming"].getint("FRAMERATE")
OUT_DIR = dsc_config["Streaming"].get("OUTPUT_DIRECTORY")
TIME_STAMP = dsc_config["Streaming"].get("TIME_STAMP_DIRECTORY")
CAMERA_SOURCE = dsc_config["Streaming"].get("CAMERA_SOURCE")
STREAMING_SOURCE = dsc_config["Streaming"].get("STREAMING_SOURCE")
# Video
VIDEO_SOURCE = dsc_config["Video"].get("VIDEO_SOURCE")

# IPWEBCAM
PORT = dsc_config["IPWEBCAM"].get("PORT")


# experiment
EXP_ORIGIN = dsc_config["Experiment"].get("EXP_ORIGIN")
EXP_NAME = dsc_config["Experiment"].get("EXP_NAME")
RECORD_EXP = dsc_config["Experiment"].getboolean("RECORD_EXP")

START_TIME = time.time()

# Classification
PATH_TO_CLASSIFIER = dsc_config["Classification"].get("PATH_TO_CLASSIFIER")
POOL_SIZE = dsc_config["Classification"].getint("POOL_SIZE")

# SIMBA
PIXPERMM = dsc_config["Classification"].getfloat("PIXPERMM")
THRESHOLD = dsc_config["Classification"].getfloat("THRESHOLD")
triggerpre = dsc_config["Classification"].get("TRIGGER")
triggerpre2 = triggerpre.split(',')
TRIGGER = list(map(int, triggerpre2))
# BSOID
TIME_WINDOW = dsc_config["Classification"].getint("TIME_WINDOW")


"""advanced settings"""
STREAMS = [
    str(part).strip() for part in adv_dsc_config["Streaming"].get("STREAMS").split(",")
]
MULTI_CAM = adv_dsc_config["Streaming"].getboolean("MULTIPLE_DEVICES")
STACK_FRAMES = (
    adv_dsc_config["Streaming"].getboolean("STACK_FRAMES")
    if adv_dsc_config["Streaming"].getboolean("STACK_FRAMES") is not None
    else False
)
ANIMALS_NUMBER = (
    adv_dsc_config["Streaming"].getint("ANIMALS_NUMBER")
    if adv_dsc_config["Streaming"].getint("ANIMALS_NUMBER") is not None
    else 1
)
PASS_SEPARATE = adv_dsc_config["Streaming"].getboolean("PASS_SEPARATE")

REPEAT_VIDEO = adv_dsc_config["Video"].getboolean("REPEAT_VIDEO")
CROP = adv_dsc_config["Streaming"].getboolean("CROP")
CROP_X = [
    int(str(part).strip())
    for part in adv_dsc_config["Streaming"].get("CROP_X").split(",")
]
CROP_Y = [
    int(str(part).strip())
    for part in adv_dsc_config["Streaming"].get("CROP_Y").split(",")
]

USE_DLSTREAM_POSTURE_DETECTION = adv_dsc_config["Pose Estimation"].getboolean("USE_DLSTREAM_POSTURE_DETECTION")
FLATTEN_MA = adv_dsc_config["Pose Estimation"].getboolean("FLATTEN_MA")
SPLIT_MA = adv_dsc_config["Pose Estimation"].getboolean("SPLIT_MA")
HANDLE_MISSING = adv_dsc_config["Pose Estimation"].get("HANDLE_MISSING")
FILTER_LIKELIHOOD = adv_dsc_config["Pose Estimation"].getboolean("FILTER_LIKELIHOOD")
LIKELIHOOD_THRESHOLD = adv_dsc_config["Pose Estimation"].getfloat("LIKELIHOOD_THRESHOLD")
