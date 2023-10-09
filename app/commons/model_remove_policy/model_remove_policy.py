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

import numpy as np

from app.commons import es_client
from app.utils import utils


class ModelRemovePolicy:

    def __init__(self, app_config, conditions_field="", model_name=""):
        self.app_config = app_config
        self.model_name = model_name
        self.conditions_field = conditions_field
        self.conditions = utils.parse_conditions(app_config[conditions_field])
        self.es_client = es_client.EsClient(
            esHost=app_config["esHost"],
            grafanaHost=app_config["grafanaHost"],
            app_config=app_config)

    def get_gathered_metrics(self, week_earlier, cur_tommorow):
        """Should be implemented in subclasses"""
        return []

    def get_conditions(self):
        if self.conditions_field in self.app_config:
            return self.app_config[self.conditions_field]
        return ""

    def check_metrics(self, metrics):
        cur_metrics = []
        should_be_deleted = False
        module_version = set()
        for field, operator, score in self.conditions:
            scores = []
            for r in metrics["hits"]["hits"]:
                if field in r["_source"]:
                    scores.append(r["_source"][field])
                if "module_version" in r["_source"]:
                    module_version.update(r["_source"]["module_version"])
            if scores:
                metrics_mean = np.round(np.mean(scores), 2)
                cur_metrics.append((field, metrics_mean))
                if utils.compare_metrics(metrics_mean, score, operator):
                    should_be_deleted = True
        return should_be_deleted, cur_metrics, list(module_version)
