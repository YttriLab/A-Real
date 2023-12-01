"""
DeepLabStream
© J.Schweihoff, M. Loshakov
University Bonn Medical Faculty, Germany
https://github.com/SchwarzNeuroconLab/DeepLabStream
Licensed under GNU General Public License v3.0
"""

from utils.poser import transform_2pose
from utils.analysis import (
    angle_between_vectors,
    calculate_distance,
    EllipseROI,
    RectangleROI,
)
from utils.configloader import RESOLUTION, TIME_WINDOW, FRAMERATE
from collections import deque
from experiments.custom.featureextraction import (
    SimbaFeatureExtractor,
    BsoidFeatureExtractor,
)
import numpy as np
# import pandas as pd

import time
# from datetime import datetime
# import configparser as cfg



"""Multiple Animal, Social Interaction Triggers
can only be used with multiple animals/skeletons (e.g. with SLEAP)
Note that currently"""


class SocialInteractionTrigger:
    """Trigger to check if one animal's body part is close to (Proximity trigger) far away from (distance trigger) another animal's body part
    This trigger can be easily adapted to incorporate more complicated social interaction matching.
    Note that this Trigger can be used without realtime identity tracking (e.g. with maDLC or DeepPoseKit) but is less effective
     because no distinction between active/passive interaction partners can be made."""

    def __init__(
        self,
        threshold: float,
        identification_dict: dict,
        interaction_type: str = "proximity",
        debug: bool = False,
    ):
        """
        Initialising trigger with following parameters:
        :param float threshold: minimum distance between selected body parts for trigger to activate
        :param dict identification_dict: nested dictionary that specifies which animal/instance is taken as "active"/acting interaction partner and which is "passive"/recieving.
                    Identification of animal ('name') has to match DLStream naming parameters for calculate skeleton (default is 'Animal1', 'Animal2', etc.).
                    Idenification of relevant bodyparts ('bp') has to match Dlstream autonaming (default is 'bp1', 'bp2', etc.) or model specific bodypart naming,
                    whichever applies. This can be a single body part (e.g. ['nose']) or a list of body parts (e.g. ['nose', 'paw_left', 'paw_right']

                    Example: identification_dict = dict(
                                                        active = {'animal': 0,
                                                                   'bp': ['nose']]
                                                                   }
                                                        ,passive = {'animal': 1,
                                                                   'bp': ['center','tail_root']
                                                                   }
                                                        )

        :param str interaction_type: Type of interaction ('proximity' or 'distance'). Proximity is checking for distances lower than threshold,
                while distance is checking for distances higher than threshold. Default: 'proximity'
        :param debug: will add another reporting to reponse that is shown in the stream
        """

        self._threshold = threshold
        self._identification_dict = identification_dict
        # for easier use
        self._active_animal = self._identification_dict["active"]["animal"]
        self._active_bp = self._identification_dict["active"]["bp"]
        self._passive_animal = self._identification_dict["passive"]["animal"]
        self._passive_bp = self._identification_dict["passive"]["bp"]

        self._interaction_type = interaction_type
        self._debug = debug

    def check_skeleton(self, skeletons: dict):
        """
        Checking skeletons for trigger
        :param skeletons: a skeleton dictionary, returned by calculate_skeletons() from poser file
        :return: response, a tuple of result (bool) and response body
        Response body is used for plotting and outputting results to trials dataframes
        """

        results = []
        for active_bp in self._identification_dict["active"]["bp"]:
            active_coords = skeletons[self._active_animal][active_bp]
            for passive_bp in self._identification_dict["passive"]["bp"]:
                passive_coords = skeletons[self._passive_animal][passive_bp]
                temp_result = False
                # calculate distance for all combinations if none of the coordinates are NaN
                if not any(np.isnan([*active_coords, *passive_coords])):
                    distance = calculate_distance(active_coords, passive_coords)
                    if (
                        distance >= self._threshold
                        and self._interaction_type == "distance"
                    ):
                        temp_result = True
                    elif (
                        distance < self._threshold
                        and self._interaction_type == "proximity"
                    ):
                        temp_result = True
                    else:
                        pass
                else:
                    pass

                results.append(temp_result)

        result = any(results)

        color = (0, 255, 0) if result else (0, 0, 255)

        if self._debug:
            active_point_x, active_point_y = skeletons[self._active_animal][
                self._active_bp[0]
            ]
            passive_point_x, passive_point_y = skeletons[self._passive_animal][
                self._passive_bp[0]
            ]
            if not any(
                np.isnan(
                    [active_point_x, active_point_y, passive_point_x, passive_point_y]
                )
            ):
                response_body = {
                    "plot": {
                        "text": dict(
                            text=f"{self._interaction_type}: {result}",
                            org=(20, 20),
                            color=color,
                        ),
                        "line": dict(
                            pt1=(int(active_point_x), int(active_point_y)),
                            pt2=(int(passive_point_x), int(passive_point_y)),
                            color=color,
                        ),
                    }
                }
            else:
                response_body = {
                    "plot": {
                        "text": dict(
                            text=f"{self._interaction_type}: {result}",
                            org=(20, 20),
                            color=color,
                        )
                    }
                }

        else:
            response_body = {
                "plot": {
                    "text": dict(
                        text=f"{self._interaction_type}: {result}",
                        org=(20, 20),
                        color=color,
                    )
                }
            }
        response = (result, response_body)
        return response


"""Single posture triggers
can be used in single animal or multiple animal experiments
"""


class HeaddirectionROITrigger:
    """Trigger to check if animal is turning its head in a specific angle to a reference point (center of the region of interest)
    and if the animal is not in the ROI"""

    def __init__(
        self, center: tuple, radius: int, angle: float = 45, debug: bool = False
    ):
        """
        Initialising trigger with following parameters:
        :param int angle: angle to meet for condition
        :param tuple center: point used as reference to measure headdirection angle and center of ROI
        :param int radius: radius of the ROI
        :param debug: Not used in this trigger
        """

        self._headdirection_trigger = HeaddirectionTrigger(angle, center)
        self._region_trigger = RegionTrigger(
            region_type="circle", center=center, radius=radius, bodyparts="nose"
        )
        self._center = center
        self._angle = angle
        self._radius = radius
        self._debug = debug

    def check_skeleton(self, skeleton: dict):
        """
        Checking skeleton for trigger
        :param skeleton: a skeleton dictionary, returned by calculate_skeletons() from poser file
        :return: response, a tuple of result (bool) and response body
        Response body is used for plotting and outputting results to trials dataframes
         [point , 'neck', 'nose'] is used for headdirection
        """
        _, angle = angle_between_vectors(
            *skeleton["neck"], *skeleton["nose"], *self._center
        )
        true_angle = abs(angle)

        result_head, _ = self._headdirection_trigger.check_skeleton(skeleton)
        result_roi, _ = self._region_trigger.check_skeleton(skeleton)

        if result_head is True and result_roi is False:
            result = True
        else:
            result = False

        color = (0, 255, 0) if result else (0, 0, 255)

        if self._debug:
            point = skeleton["nose"]

            response_body = {
                "plot": {
                    "text": dict(
                        text=str(true_angle), org=point, color=(255, 255, 255)
                    ),
                    "circle": dict(
                        center=self._center, radius=self._radius, color=color
                    ),
                }
            }
        else:
            response_body = {"angle": true_angle}

        response = (result, response_body)
        return response


class HeaddirectionTrigger:
    """Trigger to check if animal is turning head in a specific angle to a reference point"""

    def __init__(self, angle: int, point: tuple = (0, 0), debug: bool = False):
        """
        Initialising trigger with following parameters:
        :param int angle: angle to meet for condition
        :param tuple point: point used as reference to measure headdirection angle

        """
        self._point = point
        self._angle = angle
        self._debug = debug

    def check_skeleton(self, skeleton: dict):
        """
        Checking skeleton for trigger
        :param skeleton: a skeleton dictionary, returned by calculate_skeletons() from poser file
        :return: response, a tuple of result (bool) and response body
        Response body is used for plotting and outputting results to trials dataframes
         [point , 'neck', 'nose'] you need to pass this to angle between vectors to get headdirection
        """
        ret_head_dir, angle = angle_between_vectors(
            *skeleton["neck"], *skeleton["nose"], *self._point
        )
        true_angle = abs(angle)

        if true_angle <= self._angle:
            result = True
        else:
            result = False

        color = (0, 255, 0) if result else (0, 0, 255)
        if self._debug:
            center = skeleton["nose"]

            response_body = {
                "plot": {
                    "text": dict(
                        text=str(true_angle),
                        org=skeleton[self._end_point],
                        color=(255, 255, 255),
                    ),
                    "circle": dict(center=center, radius=5, color=color),
                }
            }
        else:
            response_body = {"angle": true_angle}

        response = (result, response_body)
        return response


class EgoHeaddirectionTrigger:
    """Trigger to check if animal is turning head in a specific angle and egocentric direction"""

    def __init__(self, angle: int, head_dir: str = "both", debug: bool = False):
        """
        Initialising trigger with following parameters:
        :param int angle: angle to meet for condition
        :param str head_dir: head direction from egocentric position of the animal (left, right or both)

        """
        self._head_dir = head_dir
        self._angle = angle
        self._debug = debug

    def check_skeleton(self, skeleton: dict):
        """
        Checking skeleton for trigger
        :param skeleton: a skeleton dictionary, returned by calculate_skeletons() from poser file
        :return: response, a tuple of result (bool) and response body
        Response body is used for plotting and outputting results to trials dataframes
         ['tailroot', 'neck', 'nose'] you need to pass this to angle between vectors to get headdirection
        """
        tailroot_x, tailroot_y = skeleton["tailroot"]
        neck_x, neck_y = skeleton["neck"]
        nose_x, nose_y = skeleton["nose"]
        ret_head_dir, angle = angle_between_vectors(
            tailroot_x, tailroot_y, neck_x, neck_y, nose_x, nose_y
        )
        true_angle = 180 - abs(angle)

        if true_angle <= self._angle:
            if self._head_dir == ret_head_dir:
                result = True
            elif self._head_dir == "both":
                result = True
        else:
            result = False

        color = (0, 255, 0) if result else (0, 0, 255)
        if self._debug:
            center = (nose_x, nose_y)

            response_body = {
                "plot": {
                    "text": dict(
                        text=str(true_angle),
                        org=skeleton[self._end_point],
                        color=(255, 255, 255),
                    ),
                    "circle": dict(center=center, radius=5, color=color),
                }
            }
        else:
            response_body = {"angle": true_angle}

        response = (result, response_body)
        return response


class DirectionTrigger:
    """
    Trigger to check if animal is looking in direction of some point
    """

    def __init__(self, point: tuple, angle: int, bodyparts: iter, debug: bool = False):
        """
        Initialising trigger with following parameters:
        :param tuple point: a point of interest in (x,y) format.
        :param int angle: angle, at which animal is considered looking at the screen
        :param iter bodyparts: a pair of joints of animal (tuple or list) that represent 'looking vector' like (start, end)
        For example,
         ('neck', 'nose') pair would mean that direction in which animal is looking defined by vector from neck to nose
        """
        self._angle = angle
        self._debug = debug
        self._point = point
        self._start_point, self._end_point = bodyparts

    def check_skeleton(self, skeleton: dict):
        """
        Checking skeleton for trigger
        :param skeleton: a skeleton dictionary, returned by calculate_skeletons() from poser file
        :return: response, a tuple of result (bool) and response body
        Response body is used for plotting and outputting results to trials dataframes
        """
        start_x, start_y = skeleton[self._start_point]
        end_x, end_y = skeleton[self._end_point]
        direction_x, direction_y = self._point
        head_dir, angle = angle_between_vectors(
            direction_x, direction_y, start_x, start_y, end_x, end_y
        )
        true_angle = 180 - abs(angle)

        result = true_angle <= self._angle

        color = (0, 255, 0) if result else (0, 0, 255)
        if self._debug:
            response_body = {
                "plot": {
                    "line": dict(
                        pt1=skeleton[self._end_point], pt2=self._point, color=color
                    ),
                    "text": dict(
                        text=str(true_angle),
                        org=skeleton[self._end_point],
                        color=(255, 255, 255),
                    ),
                }
            }
        else:
            response_body = {"angle": true_angle}

        response = (result, response_body)
        return response


class ScreenTrigger(DirectionTrigger):
    """
    Trigger to check if animal is looking at the screen
    """

    def __init__(
        self, direction: str, angle: int, bodyparts: iter, debug: bool = False
    ):
        """
        Initialising trigger with following parameters:
        :param direction: a direction where the screen is located in the stream or video.
        All possible directions: 'North' (or top of the frame), 'East' (right), 'South' (bottom), 'West' (left)
        Note that directions are not tied to real-world cardinal directions
        :param angle: angle, at which animal is considered looking at the screen
        :param bodyparts: a pair of joints of animal (tuple or list) that represent 'looking vector' like (start, end)
        For example,
         ('neck', 'nose') pair would mean that direction in which animal is looking defined by vector from neck to nose
        """
        self._direction = direction
        max_x, max_y = RESOLUTION
        direction_dict = {
            "North": (int(max_x / 2), 0),
            "South": (int(max_x / 2), max_y),
            "West": (0, int(max_y / 2)),
            "East": (max_x, int(max_y / 2)),
        }
        super().__init__(direction_dict[self._direction], angle, bodyparts, debug)


class RegionTrigger:
    """
    Trigger to check if animal is in Region Of Interest (ROI)
    """

    def __init__(
        self,
        region_type: str,
        center: tuple,
        radius: float,
        bodyparts,
        debug: bool = False,
    ):
        """
        Initialising trigger with following parameters:
        :param region_type: type of a ROI
        Currently available ROIs are 'square' and 'circle'
        Both of them use the same scheme to define coordinates
        :param center: center of a ROI
        :param radius: radius of a ROI
        For circle - literally radius of a circle
        For square - half of a side
        :param bodyparts: joint or a list of joints for which we are checking the ROI
        """
        self._roi_type = region_type.lower()
        region_types = {"circle": EllipseROI, "square": RectangleROI}
        self._region_of_interest = region_types[self._roi_type](center, radius, radius)
        self._bodyparts = bodyparts
        self._debug = debug  # not used in this trigger

    def check_skeleton(self, skeleton: dict):
        """
        Checking skeleton for trigger
        :param skeleton: a skeleton dictionary, returned by calculate_skeletons() from poser file
        :return: response, a tuple of result (bool) and response body
        Response body is used for plotting and outputting results to trials dataframes
        """
        if isinstance(self._bodyparts, list):
            results = []
            for part in self._bodyparts:
                bp_x, bp_y = skeleton[part]
                results.append(self._region_of_interest.check_point(bp_x, bp_y))
            result = any(results)
        else:
            bp_x, bp_y = skeleton[self._bodyparts]
            result = self._region_of_interest.check_point(bp_x, bp_y)

        color = (0, 255, 0) if result else (0, 0, 255)

        if self._roi_type == "circle":
            response_body = {
                "plot": {
                    "circle": dict(
                        center=self._region_of_interest.get_center(),
                        radius=int(self._region_of_interest.get_x_radius()),
                        color=color,
                    )
                }
            }
        elif self._roi_type == "square":
            box = self._region_of_interest.get_box()
            x1, y1, x2, y2 = box
            pt1 = (x1, y2)
            pt2 = (x2, y1)
            response_body = {"plot": {"square": dict(pt1=pt1, pt2=pt2, color=color)}}

        response = (result, response_body)
        return response


class OutsideTrigger(RegionTrigger):
    """
    Trigger to check if animal is out of the Region Of Interest (ROI)
    """

    def __init__(
        self,
        region_type: str,
        center: tuple,
        radius: float,
        bodyparts,
        debug: bool = False,
    ):
        """
        Initialising trigger with following parameters:
        :param region_type: type of a ROI
        Currently available ROIs are 'square' and 'circle'
        Both of them use the same scheme to define coordinates
        :param center: center of a ROI
        :param radius: radius of a ROI
        For circle - literally radius of a circle
        For square - half of a side
        :param bodyparts: joint or a list of joints for which we are checking the ROI
        """
        super().__init__(region_type, center, radius, bodyparts, debug)

    def check_skeleton(self, skeleton: dict):
        """
        Checking skeleton for trigger
        :param skeleton: a skeleton dictionary, returned by calculate_skeletons() from poser file
        :return: response, a tuple of result (bool) and response body
        Response body is used for plotting and outputting results to trials dataframes
        """
        result, response_body = super().check_skeleton(skeleton)
        response = (not result, response_body)  # flips result bool
        return response


"""Posture sequence triggers"""


class FreezeTrigger:
    """
    Trigger to check if animal is moving below a certain speed
    """

    def __init__(
        self,
        threshold: int,
        bodypart: str,
        timewindow_len: int = 2,
        debug: bool = False,
    ):
        """
        Initializing trigger with given threshold
        :param threshold: int in pixel how much of a movement does not count
        :param bodypart: str of body part in skeleton used for speed calculation
        For example threshold of 5 would mean that all movements more then 5 pixels in the last timewindow length frames
        would be ignored
        """
        self._bodypart = bodypart
        self._threshold = threshold
        self._timewindow_len = timewindow_len
        self._timewindow = deque(maxlen=timewindow_len)
        self._skeleton = None
        self._debug = debug  # not used in this trigger

    def check_skeleton(self, skeleton: dict):
        """
        Checking skeleton for trigger
        :param skeleton: a skeleton dictionary, returned by calculate_skeletons() from poser file
        :return: response, a tuple of result (bool) and response body
        Response body is used for plotting and outputting results to trials dataframes
        """
        # choosing a point to draw near the skeleton
        org_point = skeleton[list(skeleton.keys())[0]]
        joint_moved = 0

        if self._skeleton is None:
            result = False
            text = "..."
            self._skeleton = skeleton
        else:
            joint_travel = calculate_distance(
                skeleton[self._bodypart], self._skeleton[self._bodypart]
            )
            self._timewindow.append(joint_travel)
            if len(self._timewindow) == self._timewindow_len:
                joint_moved = np.sum(self._timewindow)

            if abs(joint_moved) <= self._threshold:
                result = True
                text = "Freezing"
            else:
                result = False
                text = "Not Freezing"
        self._skeleton = skeleton
        color = (0, 255, 0) if result else (0, 0, 255)
        response_body = {"plot": {"text": dict(text=text, org=org_point, color=color)}}
        response = (result, response_body)

        return response


class SpeedTrigger:
    """
    Trigger to check if animal is moving above a certain speed
    """

    def __init__(
        self,
        threshold: int,
        bodypart: str,
        timewindow_len: int = 2,
        debug: bool = False,
    ):
        """
        Initializing trigger with given threshold
        :param threshold: int in pixel how much of a movement does not count
        :param bodypart: str of body part in skeleton used for speed calculation
        For example threshold of 5 would mean that all movements less then 5 pixels in the last timewindow length frames
        would be ignored
        """
        self._bodypart = bodypart
        self._threshold = threshold
        self._timewindow_len = timewindow_len
        self._timewindow = deque(maxlen=timewindow_len)
        self._skeleton = None
        self._debug = debug  # not used in this trigger

    def check_skeleton(self, skeleton: dict):
        """
        Checking skeleton for trigger
        :param skeleton: a skeleton dictionary, returned by calculate_skeletons() from poser file
        :return: response, a tuple of result (bool) and response body
        Response body is used for plotting and outputting results to trials dataframes
        """
        # choosing a point to draw near the skeleton
        org_point = skeleton[list(skeleton.keys())[0]]
        joint_moved = 0

        if self._skeleton is None:
            result = False
            text = "..."
            self._skeleton = skeleton
        else:
            joint_travel = calculate_distance(
                skeleton[self._bodypart], self._skeleton[self._bodypart]
            )
            self._timewindow.append(joint_travel)
            if len(self._timewindow) == self._timewindow_len:
                joint_moved = np.sum(self._timewindow)

            if abs(joint_moved) >= self._threshold:
                result = True
                text = "Running"
            else:
                result = False
                text = "Not Running"
        self._skeleton = skeleton
        color = (0, 255, 0) if result else (0, 0, 255)
        response_body = {"plot": {"text": dict(text=text, org=org_point, color=color)}}
        response = (result, response_body)

        return response


"""Behavior classifier trigger"""


class SimbaThresholdBehaviorPoolTrigger:
    """
    Trigger to check if animal's behavior is classified as specific motif above threshold probability.
    Uses processing pool with feature extraction and classification in the same process

    """

    def __init__(self, prob_threshold: float, class_process_pool, debug: bool = False):
        """
        Initialising trigger with following parameters:
        :param float prob_threshold: threshold probability of prediction that is returned by classifier and should be used as trigger.
        If you plan to use the classifier for multiple trial triggers in the same experiment with different thresholds. We recommend setting up the
        trigger_probability during check_skeleton
        :param class_process_pool: list of dictionaries with keys process: mp.Process, input: mp.queue, output: mp.queue;
         used for lossless frame-by-frame classification

        """
        self._trigger_threshold = prob_threshold
        self._process_pool = class_process_pool
        self._last_prob = 0.0
        self._feature_id = 0
        self._center = None
        self._debug = debug
        self._skeleton = None
        self._time_window_len = TIME_WINDOW
        # feature extraction will happen in the classification process
        # self.feat_extractor = None
        self._time_window = deque(maxlen=self._time_window_len)

    def fill_time_window(self, skeleton: dict):
        """Transforms skeleton input into flat numpy array of coordinates to pass to feature extraction"""
        # todo: remove bodyparts that are not used automatically
        key_selection = {"0_tail_tip", "1_tail_tip"}
        skeleton_selection = {
            k: skeleton[k] for k in skeleton.keys() if k not in key_selection
        }
        flat_values = transform_2pose(skeleton_selection).flatten()

        # if not enough animals are present, padd the rest with default value "0,0"
        # TODO: Padd automatically; remove hardcoding
        if flat_values.shape[0] < 28:
            flat_values = np.pad(
                flat_values,
                (0, 28 - flat_values.shape[0]),
                "constant",
                constant_values=0,
            )
        # this appends the new row to the deque time_window, which will drop the "oldest" entry due to a maximum
        # length of time_window_len
        self._time_window.append(flat_values)

    def check_skeleton(self, skeleton, target_prob: float = None):
        """
        Checking skeleton for trigger, will pass skeleton window to classifier if window length is reached and
        collect skeletons otherwise
        :param skeleton: a skeleton dictionary, returned by calculate_skeletons() from poser file
        :param target_prob: optional, overwrites self._trigger_prob with target probability. this is supposed to enable the
        set up of different trials (with different motif thresholds) in the experiment without the necessaty to init to
        classifiers: default None
        :return: response, a tuple of result (bool) and response body
        Response body is used for plotting and outputting results to trials dataframes
        """
        self.fill_time_window(skeleton)

        """Checks if necessary time window was collected and passes it to classifier"""
        # if enough postures where collected

        if len(self._time_window) == self._time_window_len:
            # if the last classification is done and was taken
            self._feature_id += 1
            self._process_pool.pass_time_window(
                (self._time_window, self._feature_id), debug=self._debug
            )
        # check if a process from the pool is done with the result
        result, feature_id = self._process_pool.get_result(debug=self._debug)
        if result is not None:
            self._last_prob = result
        # else:
        #     self._last_prob = 0.0

        if target_prob is not None:
            self._trigger_threshold = target_prob
        # choosing a point to draw near the skeleton
        self._center = (50, 50)
        result = False
        text = "Current probability: {:.2f}".format(self._last_prob)

        if self._trigger_threshold <= self._last_prob:
            result = True
            text = "Motif matched: {:.2f}".format(self._last_prob)

        color = (0, 255, 0) if result else (0, 0, 255)
        response_body = {
            "plot": {"text": dict(text=text, org=self._center, color=color)}
        }
        response = (result, response_body)
        return response

    def get_trigger_threshold(self):
        return self._trigger_threshold

    def get_last_prob(self):
        return self._last_prob

    def get_time_window_len(self):
        return self._time_window_len


class BsoidClassBehaviorPoolTrigger:
    """
    Trigger to check if animal's behavior is classified as specific motif with BSOID trained classifier.
    Uses processing pool with feature extraction and classification in the same process
    """

    def __init__(self, target_class: int, class_process_pool, debug: bool = False):
        """
        Initialising trigger with following parameters:
        :param int target_class: target classification category that should be used as trigger. Must match "Group" number of cluster in BSOID.
        If you plan to use the classifier for multiple trial triggers in the same experiment with different thresholds. We recommend setting up the
        target_class during check_skeleton
        :param class_process_pool: list of dictionaries with keys process: mp.Process, input: mp.queue, output: mp.queue;
         used for lossless frame-by-frame classification

        """
        self._trigger = target_class
        self._process_pool = class_process_pool
        self._last_result = [-1]
        self._feature_id = 0
        self._center = None
        self._debug = debug
        self._skeleton = None
        # TODO: alter to framerate/10 when feature extraction is updated
        # BSOID classifiers always look at 100 ms time windows, so framerate/10 frames
        self._time_window_len = int(np.ceil(FRAMERATE / 10 * 2))
        # not used in this version (directly called in process pool)
        self.feat_extractor = None
        self._time_window = deque(maxlen=self._time_window_len)

    def fill_time_window(self, skeleton):
        from utils.poser import transform_2pose

        pose = transform_2pose(skeleton)
        self._time_window.appendleft(pose)

    def check_skeleton(self, skeleton, target_class: int = None):
        """
        Checking skeleton for trigger, will pass skeleton window to classifier if window length is reached and
        collect skeletons otherwise
        :param skeleton: a skeleton dictionary, returned by calculate_skeletons() from poser file
        :param target_class: optional, overwrites self._trigger with target probability. this is supposed to enable the
        set up of different trials (with different motifs/categories) in the experiment without the necessity to init to
        classifiers: default None
        :return: response, a tuple of result (bool) and response body
        Response body is used for plotting and outputting results to trials dataframes
        """
        self.fill_time_window(skeleton)

        """Checks if necessary time window was collected and passes it to classifier"""
        if len(self._time_window) == self._time_window_len:
            #create feature id to track if the algorithm is skipping some
            self._feature_id += 1
            self._process_pool.pass_time_window(
                (self._time_window, self._feature_id), debug=self._debug
            )
            # check if a process from the pool is done with the result
        clf_result, feature_id = self._process_pool.get_result(debug=self._debug)
        # this is a redundancy because output is a tuple with only one element, but it can be used for further filtering
        # if a probability is passed
        if clf_result is not None:
            self._last_result = clf_result[0]
        # check if target class was passed. This allows to update the trigger cluster id with each function call
        if target_class is not None:
            self._trigger = target_class

        # choosing a point to draw near the skeleton
        #self._center = skeleton[list(skeleton.keys())[0]]
        self._center = (50,50)
        result = False
        # text = 'Current probability: {:.2f}'.format(self._last_prob)
        text = "Current Class: {}".format(self._last_result)

        for trigger in range(0, len(self._trigger)):
            if self._last_result[0] == self._trigger[trigger]:
                result = True
                text = "Motif matched: {}".format(self._last_result)
                # stim


            else:
                pass


        color = (0, 255, 0) if result else (0, 0, 255)
        response_body = {
            "plot": {"text": dict(text=text, org=self._center, color=color)}
        }
        response = (result, response_body)
        return response

    def get_trigger_threshold(self):
        return self._trigger

    def get_last_prob(self):
        return self._last_prob

    def get_time_window_len(self):
        return self._time_window_len


class SimbaThresholdBehaviorPoolTrigger_old:
    """
    THIS VERSION HAS A SEPERATE FEATURE EXTRACTION WHICH WILL AFFECT OVERALL PERFORMANCE
    Trigger to check if animal's behavior is classified as specific motif above threshold probability.
    """

    def __init__(self, prob_threshold: float, class_process_pool, debug: bool = False):
        """
        Initialising trigger with following parameters:
        :param float prob_threshold: threshold probability of prediction that is returned by classifier and should be used as trigger.
        If you plan to use the classifier for multiple trial triggers in the same experiment with different thresholds. We recommend setting up the
        trigger_probability during check_skeleton
        :param class_process_pool: list of dictionaries with keys process: mp.Process, input: mp.queue, output: mp.queue;
         used for lossless frame-by-frame classification

        """
        self._trigger_threshold = prob_threshold
        self._process_pool = class_process_pool
        self._last_prob = 0.0
        self._feature_id = 0
        self._center = None
        self._debug = debug
        self._skeleton = None
        self._time_window_len = TIME_WINDOW
        self.feat_extractor = SimbaFeatureExtractor(
            input_array_length=self._time_window_len
        )
        self._time_window = deque(maxlen=self._time_window_len)

    def fill_time_window(self, skeleton: dict):
        """Transforms skeleton input into flat numpy array of coordinates to pass to feature extraction"""
        # todo: remove bodyparts that are not used automatically
        key_selection = {"0_tail_tip", "1_tail_tip"}
        skeleton_selection = {
            k: skeleton[k] for k in skeleton.keys() if k not in key_selection
        }
        flat_values = transform_2pose(skeleton_selection).flatten()

        # if not enough animals are present, padd the rest with default value "0,0"
        # TODO: Padd automatically; remove hardcoding
        if flat_values.shape[0] < 28:
            flat_values = np.pad(
                flat_values,
                (0, 28 - flat_values.shape[0]),
                "constant",
                constant_values=0,
            )
        # this appends the new row to the deque time_window, which will drop the "oldest" entry due to a maximum
        # length of time_window_len
        self._time_window.append(flat_values)

    def check_skeleton(self, skeleton, target_prob: float = None):
        """
        Checking skeleton for trigger, will pass skeleton window to classifier if window length is reached and
        collect skeletons otherwise
        :param skeleton: a skeleton dictionary, returned by calculate_skeletons() from poser file
        :param target_prob: optional, overwrites self._trigger_prob with target probability. this is supposed to enable the
        set up of different trials (with different motif thresholds) in the experiment without the necessaty to init to
        classifiers: default None
        :return: response, a tuple of result (bool) and response body
        Response body is used for plotting and outputting results to trials dataframes
        """
        self.fill_time_window(skeleton)
        f_extract_output = None
        """Checks if necessary time window was collected and passes it to classifier"""
        if len(self._time_window) == self._time_window_len:
            start_time = time.time()
            f_extract_output = self.feat_extractor.extract_features(self._time_window)
            if self._debug:
                end_time = time.time()
                print(
                    "Feature extraction time: {:.2f} msec".format(
                        (end_time - start_time) * 1000
                    )
                )
        # if enough postures where collected and their features extracted
        if f_extract_output is not None:
            # if the last classification is done and was taken
            self._feature_id += 1
            self._process_pool.pass_features(
                (f_extract_output, self._feature_id), debug=self._debug
            )
        # check if a process from the pool is done with the result
        result, feature_id = self._process_pool.get_result(debug=self._debug)
        if result is not None:
            self._last_prob = result
        # else:
        #     self._last_prob = 0.0

        if target_prob is not None:
            self._trigger_threshold = target_prob
        # choosing a point to draw near the skeleton
        self._center = (50, 50)
        result = False
        text = "Current probability: {:.2f}".format(self._last_prob)

        if self._trigger_threshold <= self._last_prob:
            result = True
            text = "Motif matched: {:.2f}".format(self._last_prob)

        color = (0, 255, 0) if result else (0, 0, 255)
        response_body = {
            "plot": {"text": dict(text=text, org=self._center, color=color)}
        }
        response = (result, response_body)
        return response

    def get_trigger_threshold(self):
        return self._trigger_threshold

    def get_last_prob(self):
        return self._last_prob

    def get_time_window_len(self):
        return self._time_window_len


class BsoidClassBehaviorTrigger:
    """
    THIS VERSION HAS A SEPERATE FEATURE EXTRACTION WHICH CAN AFFECT OVERALL PERFORMANCE AND USES ONLY 1 CLASSIFIER AT A TIME
    WE RECOMMEND USING THE POOL VERSION.
    If you only want/need to run 1 classifier, just set pool_size to 1

    Trigger to check if animal's behavior is classified as specific motif with BSOID trained classifier.
    """

    def __init__(self, target_class: int, path_to_sav: str, debug: bool = False):
        """
        Initialising trigger with following parameters:
        :param int target_class: target classification category that should be used as trigger. Must match "Group" number of cluster in BSOID.
        If you plan to use the classifier for multiple trial triggers in the same experiment with different thresholds. We recommend setting up the
        target_class during check_skeleton
        :param str path_to_sav: path to saved classifier, will be passed to classifier module

        """
        self._trigger = target_class
        self._last_result = [0]
        self._center = None
        self._debug = debug
        self._skeleton = None
        self._classifier, self._time_window_len = self._init_classifier(
            path_to_sav
        )  # initialize classifier
        self.feat_extractor = BsoidFeatureExtractor(
            self._time_window_len, fps=FRAMERATE
        )
        self._time_window = deque(maxlen=self._time_window_len)

    @staticmethod
    def _init_classifier(path_to_sav):
        from experiments.custom.classifier import BsoidClassifier

        """Put your classifier of choice in here"""
        classifier = BsoidClassifier(path_to_clf=path_to_sav)
        win_len = classifier.get_win_len()
        return classifier, win_len

    def fill_time_window(self, skeleton):
        from utils.poser import transform_2pose

        pose = transform_2pose(skeleton)
        self._time_window.appendleft(pose)

    def check_skeleton(self, skeleton, trigger: float = None):
        """
        Checking skeleton for trigger, will pass skeleton window to classifier if window length is reached and
        collect skeletons otherwise
        :param skeleton: a skeleton dictionary, returned by calculate_skeletons() from poser file
        :param trigger: optional, overwrites self._trigger with target probability. this is supposed to enable the
        set up of different trials (with different motifs/categories) in the experiment without the necessity to init to
        classifiers: default None
        :return: response, a tuple of result (bool) and response body
        Response body is used for plotting and outputting results to trials dataframes
        """
        self.fill_time_window(skeleton)
        # self._time_window.append(temp_feature)
        # self._time_window = temp_feature
        f_extract_output = None
        """Checks if necessary time window was collected and passes it to classifier"""
        if len(self._time_window) == self._time_window_len:
            start_time = time.time()
            f_extract_output = self.feat_extractor.extract_features(self._time_window)
            end_time = time.time()
            if self._debug:
                print(
                    "Feature extraction time: {:.2f} msec".format(
                        (end_time - start_time) * 1000
                    )
                )
        if f_extract_output is not None:
            self._last_result, _, _ = self._classifier.classify(f_extract_output)
        else:
            self._last_result = [0]
        if trigger is not None:
            self._trigger = trigger
        # choosing a point to draw near the skeleton
        self._center = skeleton[list(skeleton.keys())[0]]
        # self._center = (50,50)
        result = False
        # text = 'Current probability: {:.2f}'.format(self._last_prob)
        text = "Current Class: {}".format(self._last_result)

        if self._last_result[0] == self._trigger:
            result = True
            text = "Motif matched: {}".format(self._last_result)

        color = (0, 255, 0) if result else (0, 0, 255)
        response_body = {
            "plot": {"text": dict(text=text, org=self._center, color=color)}
        }
        response = (result, response_body)
        return response

    def get_trigger_threshold(self):
        return self._trigger

    def get_last_prob(self):
        return self._last_prob

    def get_time_window_len(self):
        return self._time_window_len


class BsoidClassBehaviorPoolTrigger_old:
    """
        THIS VERSION HAS A SEPERATE FEATURE EXTRACTION WHICH CAN AFFECT OVERALL PERFORMANCE

    Trigger to check if animal's behavior is classified as specific motif with BSOID trained classifier.
    """

    def __init__(self, target_class: int, class_process_pool, debug: bool = False):
        """
        Initialising trigger with following parameters:
        :param int target_class: target classification category that should be used as trigger. Must match "Group" number of cluster in BSOID.
        If you plan to use the classifier for multiple trial triggers in the same experiment with different thresholds. We recommend setting up the
        target_class during check_skeleton
        :param class_process_pool: list of dictionaries with keys process: mp.Process, input: mp.queue, output: mp.queue;
         used for lossless frame-by-frame classification

        """
        self._trigger = target_class
        self._process_pool = class_process_pool
        self._last_result = [0]
        self._feature_id = 0
        self._center = None
        self._debug = debug
        self._skeleton = None
        # TODO: alter to framerate/10 when feature extraction is updated
        # BSOID classifiers always look at 100 ms time windows, so framerate/10 frames
        self._time_window_len = int(np.ceil(FRAMERATE / 10 * 2))
        self.feat_extractor = BsoidFeatureExtractor()
        self._time_window = deque(maxlen=self._time_window_len)

    def fill_time_window(self, skeleton):
        from utils.poser import transform_2pose

        pose = transform_2pose(skeleton)
        self._time_window.appendleft(pose)

    def check_skeleton(self, skeleton, target_class: int = None):
        """
        Checking skeleton for trigger, will pass skeleton window to classifier if window length is reached and
        collect skeletons otherwise
        :param skeleton: a skeleton dictionary, returned by calculate_skeletons() from poser file
        :param target_class: optional, overwrites self._trigger with target probability. this is supposed to enable the
        set up of different trials (with different motifs/categories) in the experiment without the necessity to init to
        classifiers: default None
        :return: response, a tuple of result (bool) and response body
        Response body is used for plotting and outputting results to trials dataframes
        """
        self.fill_time_window(skeleton)
        # self._time_window.append(temp_feature)
        # self._time_window = temp_feature
        f_extract_output = None
        """Checks if necessary time window was collected and passes it to classifier"""
        if len(self._time_window) == self._time_window_len:
            start_time = time.time()
            f_extract_output = self.feat_extractor.extract_features(self._time_window)
            end_time = time.time()
            if self._debug:
                print(
                    "Feature extraction time: {:.2f} msec".format(
                        (end_time - start_time) * 1000
                    )
                )
        if f_extract_output is not None:
            self._feature_id += 1
            self._process_pool.pass_features(
                (f_extract_output, self._feature_id), debug=self._debug
            )
            # check if a process from the pool is done with the result
        clf_result, feature_id = self._process_pool.get_result(debug=self._debug)
        if clf_result is not None:
            self._last_result = clf_result[0]
        if target_class is not None:
            self._trigger = target_class
        # choosing a point to draw near the skeleton
        self._center = skeleton[list(skeleton.keys())[0]]
        #self._center = (50,50)
        result = False
        # text = 'Current probability: {:.2f}'.format(self._last_prob)
        text = "Current Class: {}".format(self._last_result)

        if self._last_result[0] == self._trigger:
            result = True
            text = "Motif matched: {}".format(self._last_result)

        color = (0, 255, 0) if result else (0, 0, 255)
        response_body = {
            "plot": {"text": dict(text=text, org=self._center, color=color)}
        }
        response = (result, response_body)
        return response

    def get_trigger_threshold(self):
        return self._trigger

    def get_last_prob(self):
        return self._last_prob

    def get_time_window_len(self):
        return self._time_window_len
