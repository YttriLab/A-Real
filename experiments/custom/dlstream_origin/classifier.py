"""
DeepLabStream
© J.Schweihoff, M. Loshakov
University Bonn Medical Faculty, Germany
https://github.com/SchwarzNeuroconLab/DeepLabStream
Licensed under GNU General Public License v3.0
"""

import multiprocessing as mp
import time
import pickle
import numpy as np

from utils.configloader import PATH_TO_CLASSIFIER, TIME_WINDOW, FRAMERATE
from experiments.custom.featureextraction import (
    SimbaFeatureExtractor,
    SimbaFeatureExtractorStandard14bp,
    BsoidFeatureExtractor,
)


class Classifier:
    """Empty base class for classification trigger. Loads pretrained classifier, extracts features from skeleton sequence
    and passes it to the classifier. Returns found motif and result if used as trigger."""

    def __init__(self, win_len: int = 1):
        self._classifier = self.load_classifier(PATH_TO_CLASSIFIER)
        self._win_len = win_len
        self.last_result = None

    @staticmethod
    def load_classifier(path_to_sav):
        """Load saved classifier"""
        # import pickle
        file = open(path_to_sav, "rb")
        classifier = pickle.load(file)
        file.close()
        return classifier

    def classify(self, features):
        """predicts motif from features"""
        prediction = self._classifier.predict(features)
        self.last_result = prediction
        return prediction

    def get_last_result(self, skeleton_window: list):
        """Returns predicted last prediction"""
        return self.last_result

    def get_win_len(self):
        return self._win_len


class SiMBAClassifier:
    """SiMBA base class for simple behavior classification trigger. Loads pretrained classifier, gets passed features
    from SimbaFeatureExtractor. Returns probability of prediction that can be incorporated into triggers."""

    def __init__(self):
        self._classifier = self.load_classifier(PATH_TO_CLASSIFIER)
        self.last_result = 0.0
        self._pure = self._check_pure()

    @staticmethod
    def load_classifier(path_to_sav):
        """Load saved classifier"""
        # import pickle
        file = open(path_to_sav, "rb")
        classifier = pickle.load(file)
        file.close()
        return classifier

    def _check_pure(self):
        if "pure" in str(self._classifier):
            return True
        else:
            return False

    def classify(self, features):
        """predicts motif probability from features"""
        if self._pure:
            # pure-predict needs a list instead of a numpy array
            prediction = self._classifier.predict_proba(list(features))
            # pure-predict returns a nested list
            probability = prediction[0][1]
        else:
            prediction = self._classifier.predict_proba(features)
            probability = prediction.item(1)
        self.last_result = probability
        return probability

    def get_last_result(self):
        """Returns predicted last prediction"""
        return self.last_result


class BsoidClassifier:
    """BSOID base class for multiple behavior classification trigger. Loads pretrained classifier, gets passed features
    from SimbaFeatureExtractor. Returns probability of prediction that can be incorporated into triggers."""

    def __init__(self):
        self._classifier = self.load_classifier(PATH_TO_CLASSIFIER)
        self.last_result = 0.0

    @staticmethod
    def load_classifier(path_to_sav):
        """Load saved classifier"""
        import joblib

        file = open(path_to_sav, "rb")
        [_, _, _, clf, _, predictions] = joblib.load(file)
        file.close()
        return clf

    def classify(self, features):
        """predicts motif probability from features    :param feats: list, multiple feats (original feature space)
        :param clf: Obj, MLP classifier
        :return nonfs_labels: list, label/100ms
        Adapted from BSOID; https://github.com/YttriLab/B-SOID
        """
        labels_fslow = []
        # TODO: adapt to pure version of BSOID Classifier
        for i in range(0, len(features)):
            labels = self._classifier.predict(features[i].T)
            labels_fslow.append(labels)
        self.last_result = labels_fslow

        return labels_fslow

    def get_last_result(self):
        """Returns predicted last prediction"""
        return self.last_result


"""Feature Extraction and Classification in the same pool"""


def example_feat_classifier_pool_run(input_q: mp.Queue, output_q: mp.Queue):
    feature_extractor = SimbaFeatureExtractor(TIME_WINDOW)
    classifier = Classifier()  # initialize classifier
    while True:
        skel_time_window = None
        feature_id = 0
        if input_q.full():
            skel_time_window, feature_id = input_q.get()
        if skel_time_window is not None:
            start_time = time.time()
            features = feature_extractor.extract_features(skel_time_window)
            last_prob = classifier.classify(features)
            output_q.put((last_prob, feature_id))
            end_time = time.time()
            # print("Classification time: {:.2f} msec".format((end_time-start_time)*1000))
        else:
            pass


def simba_feat_classifier_pool_run(input_q: mp.Queue, output_q: mp.Queue):
    #feature_extractor = SimbaFeatureExtractorStandard14bp(TIME_WINDOW)
    feature_extractor = SimbaFeatureExtractor(TIME_WINDOW)
    classifier = SiMBAClassifier()  # initialize classifier
    report = False
    ft_list = []
    clf_list = []
    while True:
        skel_time_window = None
        feature_id = 0
        if input_q.full():
            skel_time_window, feature_id = input_q.get()
        if skel_time_window is not None:
            start_time_feat = time.time()
            features = feature_extractor.extract_features(skel_time_window)
            end_time_feat = time.time()
            start_time_clf = time.time()
            last_prob = classifier.classify(features)
            end_time = time.time()
            output_q.put((last_prob, feature_id))

            if report:
                feat_time = ((end_time_feat - start_time_feat) * 1000)
                clf_time = ((end_time-start_time_clf)*1000)
                print("Feature Extraction time: {:.2f} msec".format(feat_time))
                print("Classification time: {:.2f} msec".format(clf_time))
                print("Total time: {:.2f} msec".format((end_time-start_time_feat)*1000))
                print("Current probability: {:.2f}".format(last_prob))
                print("Feature ID: "+ str(feature_id))
                #skip first 10 to ignore numba jit initial slowness in stats
                if feature_id > 10:
                    ft_list.append(feat_time)
                    clf_list.append(clf_time)
                    print("Avg. feature extraction time: {:.2f} +/- {:.2f} msec".format(np.mean(ft_list), np.std(ft_list)),
                              "Avg. classification time: {:.2f} +/- {:.2f} msec".format(np.mean(clf_list), np.std(clf_list)),
                          f"Classfication Cycles: {len(ft_list)}")

        else:
            pass


def bsoid_feat_classifier_pool_run(input_q: mp.Queue, output_q: mp.Queue):
    feature_extractor = BsoidFeatureExtractor()
    classifier = BsoidClassifier()  # initialize classifier
    report = False
    ft_list = []
    clf_list = []

    while True:
        skel_time_window = None
        feature_id = 0
        if input_q.full():
            skel_time_window, feature_id = input_q.get()
        if skel_time_window is not None:
            start_time_feat = time.time()
            features = feature_extractor.extract_features(skel_time_window)
            end_time_feat = time.time()
            start_time_clf = time.time()
            last_prob = classifier.classify(features)
            output_q.put((last_prob, feature_id))
            end_time = time.time()
            if report:
                feat_time = ((end_time_feat - start_time_feat) * 1000)
                clf_time = ((end_time-start_time_clf)*1000)
                print("Feature Extraction time: {:.2f} msec".format(feat_time))
                print("Classification time: {:.2f} msec".format(clf_time))
                print("Total time: {:.2f} msec".format((end_time-start_time_feat)*1000))
                print("Current motif: ", *last_prob)
                print("Feature ID: "+ str(feature_id))
                ft_list.append(feat_time)
                clf_list.append(clf_time)
                print("Avg. feature extraction time: {:.2f} +/- {:.2f} msec".format(np.mean(ft_list), np.std(ft_list)),
                          "Avg. classification time: {:.2f} +/- {:.2f} msec".format(np.mean(clf_list), np.std(clf_list)),
                      f"Classfication Cycles: {len(ft_list)}")
        else:
            pass


class FeatureExtractionClassifierProcessPool:
    """
    Class to help work with protocol function in multiprocessing
    spawns a pool of processes that tackle the frame-by-frame issue.
    """

    def __init__(self, pool_size: int):
        """
        Setting up the three queues and the process itself
        """
        self._running = False
        self._pool_size = pool_size
        self._process_pool = self.initiate_pool(
            example_feat_classifier_pool_run, pool_size
        )

    @staticmethod
    def initiate_pool(process_func, pool_size: int):
        """creates list of process dictionaries that are used to classify features
        :param process_func: function that will be passed to mp.Process object, should contain classification
        :param pool_size: number of processes created by function, should be enough to enable constistent feature classification without skipped frames
        :"""
        process_pool = []

        for i in range(pool_size):
            input_queue = mp.Queue(1)
            output_queue = mp.Queue(1)
            classification_process = mp.Process(
                target=process_func, args=(input_queue, output_queue)
            )
            process_pool.append(
                dict(
                    process=classification_process,
                    input=input_queue,
                    output=output_queue,
                    running=False,
                )
            )

        return process_pool

    def start(self):
        """
        Starting all processes
        """
        for process in self._process_pool:
            process["process"].start()

    def end(self):
        """
        Ending all processes
        """
        for process in self._process_pool:
            process["input"].close()
            process["output"].close()
            process["process"].terminate()

    def get_status(self):
        """
        Getting current status of the running protocol
        """
        return self._running

    def pass_time_window(self, skel_time_window: tuple, debug: bool = False):
        """
        Passing the features to the process pool
        First checks if processes got their first input yet
        Checks which process is already done and then gives new input
        breaks for loop if an idle process was found
        :param features tuple: feature list from feature extractor and feature_id used to identify processing sequence
        :param debug bool: reporting of process + feature id to identify discrepancies in processing sequence
        """
        for process in self._process_pool:
            #if the process is not already busy, feed it some new input and break the loop
            #this should only be valid the first time the process is fed.
            if not process["running"]:
                if process["input"].empty():
                    process["input"].put(skel_time_window)
                    process["running"] = True
                    if debug:
                        print(
                            "First Input",
                            process["process"].name,
                            "ID: " + str(skel_time_window[1]),
                        )
                    break

            #if the process is busy but finished (has output), feed it some new input.
            #this should be the normal case
            elif process["input"].empty() and process["output"].full():
                process["input"].put(skel_time_window)
                if debug:
                    print(
                        "Input",
                        process["process"].name,
                        "ID: " + str(skel_time_window[1]),
                    )
                break

    def get_result(self, debug: bool = False):
        """
        Getting result from the process pool
        takes result from first finished process in pool
        :param debug bool: reporting of process + feature id to identify discrepancies in processing sequence

        """
        result = (None, 0)
        for process in self._process_pool:
            #check if process is finished
            if process["output"].full():
                #take result and break the loop. This way two simultaneously finished processes are emptied in sequence
                #rather then overwriting the results of each other
                #the disadvantage is that the result won't be the latest classification but in the next in sequential order (to the last).
                #the advantage is that we won't miss any results this way and have "consistent" latency, which is the intended behavior.
                result = process["output"].get()
                if debug:
                    print("Output", process["process"].name, "ID: " + str(result[1]))
                break
        return result


class FeatSimbaProcessPool(FeatureExtractionClassifierProcessPool):
    """
    Class to help work with protocol function in multiprocessing
    spawns a pool of processes that tackle the frame-by-frame issue.
    """

    def __init__(self, pool_size: int):
        """
        Setting up the three queues and the process itself
        """
        super().__init__(pool_size)
        self._process_pool = super().initiate_pool(
            simba_feat_classifier_pool_run, pool_size
        )


class FeatBsoidProcessPool(FeatureExtractionClassifierProcessPool):
    """
    Class to help work with protocol function in multiprocessing
    spawns a pool of processes that tackle the frame-by-frame issue.
    """

    def __init__(self, pool_size: int):
        """
        Setting up the three queues and the process itself
        """
        super().__init__(pool_size)
        self._process_pool = super().initiate_pool(
            bsoid_feat_classifier_pool_run, pool_size
        )


"""Simple process protocols """


def example_classifier_run(
    input_classification_q: mp.Queue, output_classification_q: mp.Queue
):
    classifier = Classifier()  # initialize classifier
    while True:
        features = None
        if input_classification_q.full():
            features = input_classification_q.get()
        if features is not None:
            last_prob = classifier.classify(features)
            output_classification_q.put(last_prob)
        else:
            pass


def simba_classifier_run(input_q: mp.Queue, output_q: mp.Queue):
    classifier = SiMBAClassifier()  # initialize classifier
    while True:
        features = None
        if input_q.full():
            features = input_q.get()
        if features is not None:
            start_time = time.time()
            last_prob = classifier.classify(features)
            output_q.put((last_prob))
            end_time = time.time()
            # print("Classification time: {:.2f} msec".format((end_time-start_time)*1000))
        else:
            pass


def bsoid_classifier_run(input_q: mp.Queue, output_q: mp.Queue):
    #takes features from input and feeds them into classifier. Outputs classification
    classifier = BsoidClassifier()  # initialize classifier
    while True:
        features = None
        if input_q.full():
            features = input_q.get()
        if features is not None:
            start_time = time.time()
            #last prob is a missleading name that comes from a binary classifier. B-SOID's output is a cluster id rather then the probability.
            last_prob = classifier.classify(features)
            output_q.put((last_prob))
            end_time = time.time()
            print(
                "Classification time: {:.2f} msec".format(
                    (end_time - start_time) * 1000
                )
            )
        else:
            pass


class ClassifierProcess:
    """
    Class to help work with protocol function in multiprocessing
    Modified from stimulus_process.py
    """

    def __init__(self):
        """
        Setting up the three queues and the process itself
        """
        self.input_queue = mp.Queue(1)
        self.output_queue = mp.Queue(1)
        self._classification_process = None
        self._running = False
        self._classification_process = mp.Process(
            target=example_classifier_run, args=(self.input_queue, self.output_queue)
        )

    def start(self):
        """
        Starting the process
        """
        self._classification_process.start()

    def end(self):
        """
        Ending the process
        """
        self.input_queue.close()
        self.output_queue.close()
        self._classification_process.terminate()

    def get_status(self):
        """
        Getting current status of the running protocol
        """
        return self._running

    def pass_features(self, features):
        """
        Passing the features to the process
        """
        if self.input_queue.empty():
            self.input_queue.put(features)
            self._running = True

    def get_result(self):
        """
        Getting result from the process
        """
        if self.output_queue.full():
            self._running = False
            return self.output_queue.get()


class SimbaClassifier_Process(ClassifierProcess):
    def __init__(self):
        super().__init__()
        self.input_queue = mp.Queue(1)
        self.output_queue = mp.Queue(1)
        self._classification_process = mp.Process(
            target=simba_classifier_run, args=(self.input_queue, self.output_queue)
        )


class BsoidClassifier_Process(ClassifierProcess):
    def __init__(self):
        super().__init__()
        self.input_queue = mp.Queue(1)
        self.output_queue = mp.Queue(1)
        self._classification_process = mp.Process(
            target=bsoid_classifier_run, args=(self.input_queue, self.output_queue)
        )


"""Processing pool for classification"""


def example_classifier_pool_run(input_q: mp.Queue, output_q: mp.Queue):
    classifier = Classifier()  # initialize classifier
    while True:
        features = None
        feature_id = 0
        if input_q.full():
            features, feature_id = input_q.get()
        if features is not None:
            start_time = time.time()
            last_prob = classifier.classify(features)
            output_q.put((last_prob, feature_id))
            end_time = time.time()
            # print("Classification time: {:.2f} msec".format((end_time-start_time)*1000))
        else:
            pass


def simba_classifier_pool_run(input_q: mp.Queue, output_q: mp.Queue):
    classifier = SiMBAClassifier()  # initialize classifier
    while True:
        features = None
        feature_id = 0
        if input_q.full():
            features, feature_id = input_q.get()
        if features is not None:
            start_time = time.time()
            last_prob = classifier.classify(features)
            output_q.put((last_prob, feature_id))
            end_time = time.time()
            # print("Classification time: {:.2f} msec".format((end_time-start_time)*1000))
        else:
            pass


def bsoid_classifier_pool_run(input_q: mp.Queue, output_q: mp.Queue):
    classifier = BsoidClassifier()  # initialize classifier
    while True:
        features = None
        feature_id = 0
        if input_q.full():
            features, feature_id = input_q.get()
        if features is not None:
            start_time = time.time()
            last_prob = classifier.classify(features)
            output_q.put((last_prob, feature_id))
            end_time = time.time()
            # print("Classification time: {:.2f} msec".format((end_time-start_time)*1000))
            # print("Feature ID: "+ feature_id)

        else:
            pass


class ClassifierProcessPool:
    """
    Class to help work with protocol function in multiprocessing
    spawns a pool of processes that tackle the frame-by-frame issue.
    """

    def __init__(self, pool_size: int):
        """
        Setting up the three queues and the process itself
        """
        self._running = False
        self._pool_size = pool_size
        self._process_pool = self.initiate_pool(example_classifier_pool_run, pool_size)

    @staticmethod
    def initiate_pool(process_func, pool_size: int):
        """creates list of process dictionaries that are used to classify features
        :param process_func: function that will be passed to mp.Process object, should contain classification
        :param pool_size: number of processes created by function, should be enough to enable constistent feature classification without skipped frames
        :"""
        process_pool = []

        for i in range(pool_size):
            input_queue = mp.Queue(1)
            output_queue = mp.Queue(1)
            classification_process = mp.Process(
                target=process_func, args=(input_queue, output_queue)
            )
            process_pool.append(
                dict(
                    process=classification_process,
                    input=input_queue,
                    output=output_queue,
                    running=False,
                )
            )

        return process_pool

    def start(self):
        """
        Starting all processes
        """
        for process in self._process_pool:
            process["process"].start()

    def end(self):
        """
        Ending all processes
        """
        for process in self._process_pool:
            process["input"].close()
            process["output"].close()
            process["process"].terminate()

    def get_status(self):
        """
        Getting current status of the running protocol
        """
        return self._running

    def pass_features(self, features: tuple, debug: bool = False):
        """
        Passing the features to the process pool
        First checks if processes got their first input yet
        Checks which process is already done and then gives new input
        breaks for loop if an idle process was found
        :param features tuple: feature list from feature extractor and feature_id used to identify processing sequence
        :param debug bool: reporting of process + feature id to identify discrepancies in processing sequence
        """
        for process in self._process_pool:
            if not process["running"]:
                if process["input"].empty():
                    process["input"].put(features)
                    process["running"] = True
                    if debug:
                        print(
                            "First Input",
                            process["process"].name,
                            "ID: " + str(features[1]),
                        )
                    break

            elif process["input"].empty() and process["output"].full():
                process["input"].put(features)
                if debug:
                    print("Input", process["process"].name, "ID: " + str(features[1]))
                break

    def get_result(self, debug: bool = False):
        """
        Getting result from the process pool
        takes result from first finished process in pool
        :param debug bool: reporting of process + feature id to identify discrepancies in processing sequence

        """
        result = (None, 0)
        for process in self._process_pool:
            if process["output"].full():
                result = process["output"].get()
                if debug:
                    print("Output", process["process"].name, "ID: " + str(result[1]))
                break
        return result


class SimbaProcessPool(ClassifierProcessPool):
    """
    Class to help work with protocol function in multiprocessing
    spawns a pool of processes that tackle the frame-by-frame issue.
    """

    def __init__(self, pool_size: int):
        """
        Setting up the three queues and the process itself
        """
        super().__init__(pool_size)
        self._process_pool = super().initiate_pool(simba_classifier_pool_run, pool_size)


class BsoidProcessPool(ClassifierProcessPool):
    """
    Class to help work with protocol function in multiprocessing
    spawns a pool of processes that tackle the frame-by-frame issue.
    """

    def __init__(self, pool_size: int):
        """
        Setting up the three queues and the process itself
        """
        super().__init__(pool_size)
        self._process_pool = super().initiate_pool(bsoid_classifier_pool_run, pool_size)
