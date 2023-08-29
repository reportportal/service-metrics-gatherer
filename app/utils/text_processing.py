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
import re
from typing import Tuple
from urllib.parse import urlparse


def remove_credentials_from_url(url: str) -> str:
    parsed_url = urlparse(url)
    new_netloc = re.sub("^.+?:.+?@", "", parsed_url.netloc)
    return url.replace(parsed_url.netloc, new_netloc)


def get_credentials_from_url(url: str) -> Tuple[str, str]:
    parsed_url = urlparse(url)
    new_netloc = re.search("^(.+?):(.+?)@", parsed_url.netloc)
    try:
        username = new_netloc.group(1).strip()
        password = new_netloc.group(2).strip()
        return username, password
    except:  # noqa
        return "", ""


def build_url(main_url: str, url_params: list) -> str:
    """Build url by concatenating url and url_params"""
    return main_url + "/" + "/".join(url_params)


def unite_project_name(project_id: str, prefix: str) -> str:
    return prefix + project_id


def convert_metrics_to_string(cur_metrics: list) -> str:
    return ";".join(["%s:%s" % (metric[0], metric[1]) for metric in cur_metrics])
