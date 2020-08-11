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


def read_json_file(folder, filename, to_json=False):
    """Read fixture from file"""
    with open(os.path.join(folder, filename), "r") as file:
        return file.read() if not to_json else json.loads(file.read())


def is_the_time_for_task_starting(allowed_start_time, allowed_end_time):
    start = datetime.time(int(allowed_start_time.split(":")[0]), int(allowed_start_time.split(":")[1]))
    end = datetime.time(int(allowed_end_time.split(":")[0]), int(allowed_end_time.split(":")[1]))
    now_time = datetime.datetime.now().time()
    return (now_time >= start and now_time <= datetime.time(23, 59)) or\
        (now_time >= datetime.time(0, 0) and now_time <= end)


def take_the_date_to_check():
    now_time = datetime.datetime.now().time()
    if (now_time >= datetime.time(12, 0) and now_time <= datetime.time(23, 59)):
        return datetime.datetime.now()
    return datetime.datetime.now() - datetime.timedelta(days=1)
