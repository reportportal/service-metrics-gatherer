"""
* Copyright 2019 EPAM Systems
*
* Licensed under the Apache License, Version 2.0 (the "License");
* you may not use this file except in compliance with the License.
* You may obtain a copy of the License at
*
* http://www.apache.org/licenses/LICENSE-2.0
*
* Unless required by applicable law or agreed to in writing, software
* distributed under the License is distributed on an "AS IS" BASIS,
* WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
* See the License for the specific language governing permissions and
* limitations under the License.
"""

import logging
import re
import os
import json
from urllib.parse import urlparse
import datetime

logger = logging.getLogger("metricsGatherer.utils")


def remove_credentials_from_url(url):
    parsed_url = urlparse(url)
    new_netloc = re.sub("^.+?:.+?@", "", parsed_url.netloc)
    return url.replace(parsed_url.netloc, new_netloc)


def get_credentials_from_url(url):
    parsed_url = urlparse(url)
    new_netloc = re.search("^(.+?):(.+?)@", parsed_url.netloc)
    try:
        username = new_netloc.group(1).strip()
        password = new_netloc.group(2).strip()
        return username, password
    except: # noqa
        return "", ""


def read_json_file(folder, filename, to_json=False):
    """Read fixture from file"""
    with open(os.path.join(folder, filename), "r") as file:
        return file.read() if not to_json else json.loads(file.read())


def is_the_time_for_task_starting(allowed_start_time, allowed_end_time):
    start = datetime.time(int(allowed_start_time.split(":")[0]), int(allowed_start_time.split(":")[1]))
    end = datetime.time(int(allowed_end_time.split(":")[0]), int(allowed_end_time.split(":")[1]))
    now_time = datetime.datetime.now().time()
    if start > end:
        return (now_time >= start and now_time <= datetime.time(23, 59)) or\
            (now_time >= datetime.time(0, 0) and now_time <= end)
    return now_time >= start and now_time <= end


def take_the_date_to_check():
    now_time = datetime.datetime.now().time()
    if (now_time >= datetime.time(12, 0) and now_time <= datetime.time(23, 59)):
        return datetime.datetime.now()
    return datetime.datetime.now() - datetime.timedelta(days=1)


def build_url(main_url, url_params):
    """Build url by concating url and url_params"""
    return main_url + "/" + "/".join(url_params)


def unite_project_name(project_id, prefix):
    return prefix + project_id


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
            except: # noqa
                try:
                    metric_score = float(condition_changed[1].strip())
                except: # noqa
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


def convert_metrics_to_string(cur_metrics):
    return ";".join(["%s:%s" % (metric[0], metric[1]) for metric in cur_metrics])
