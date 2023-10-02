#  Copyright 2023 EPAM Systems
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#  https://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import datetime
import json
import logging
import os
from typing import Union, Any

logger = logging.getLogger("metricsGatherer.utils")


def read_file(folder: str, filename: str) -> str:
    """Read file content as string (UTF-8)"""
    with open(os.path.join(folder, filename), "r") as file:
        return file.read()


def read_json_file(folder: str, filename: str, to_json=False) -> Union[str, Any]:
    """Read fixture from file"""
    content = read_file(folder, filename)
    return content if not to_json else json.loads(content)


def is_the_time_for_task_starting(allowed_start_time, allowed_end_time):
    start = datetime.time(int(allowed_start_time.split(":")[0]), int(allowed_start_time.split(":")[1]))
    end = datetime.time(int(allowed_end_time.split(":")[0]), int(allowed_end_time.split(":")[1]))
    now_time = datetime.datetime.now().time()
    if start > end:
        return (now_time >= start and now_time <= datetime.time(23, 59)) or \
            (now_time >= datetime.time(0, 0) and now_time <= end)
    return now_time >= start and now_time <= end


def take_the_date_to_check():
    now_time = datetime.datetime.now().time()
    if (now_time >= datetime.time(12, 0) and now_time <= datetime.time(23, 59)):
        return datetime.datetime.now()
    return datetime.datetime.now() - datetime.timedelta(days=1)


def parse_conditions(conditions):
    parsed_conditions = []
    for condition in conditions.split("|"):
        if not condition.strip():
            continue
        chosen_operator = ""
        for operator in [">=", "<=", "==", "=", "<", ">"]:
            if operator in condition:
                chosen_operator = operator
                break
        condition_changed = condition.replace(chosen_operator, " ").split()
        if len(condition_changed) == 2:
            metric_score = None
            try:
                metric_score = int(condition_changed[1].strip())
            except:  # noqa
                try:
                    metric_score = float(condition_changed[1].strip())
                except:  # noqa
                    pass
            if metric_score is not None:
                parsed_conditions.append(
                    (condition_changed[0].strip(), chosen_operator, metric_score))
    return parsed_conditions


def compare_metrics(cur_metric, metric_threshold, operator):
    if operator == ">=":
        return cur_metric >= metric_threshold
    if operator == ">":
        return cur_metric > metric_threshold
    if operator == "<=":
        return cur_metric <= metric_threshold
    if operator == "<":
        return cur_metric < metric_threshold
    if operator in ["==", "="]:
        return cur_metric == metric_threshold
    return False
