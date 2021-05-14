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
import json
from commons import amqp
from commons import es_client
from utils import utils
import datetime
import numpy as np

logger = logging.getLogger("metricsGatherer.models_remover")


class ModelsRemover:

    def __init__(self, app_config):
        self.app_config = app_config
        self.models_conditions = {
            "auto_analysis": utils.parse_conditions(app_config["autoAnalysisModelRemovePolicy"]),
            "suggest": utils.parse_conditions(app_config["suggestModelRemovePolicy"])
        }
        self.es_client = es_client.EsClient(
            esHost=app_config["esHost"],
            grafanaHost=app_config["grafanaHost"],
            app_config=app_config)

    def apply_remove_model_policies(self, project_id):
        _amqp_client = None
        try:
            _amqp_client = amqp.AmqpClient(self.app_config)
            for model_type in self.models_conditions:
                model_folder = _amqp_client.call(json.dumps(
                    {
                        "project": project_id,
                        "model_type": model_type
                    }), "get_models")
                should_be_deleted, cur_metrics = self.should_model_be_deleted(model_type, project_id)
                if model_folder.strip() and should_be_deleted:
                    response = _amqp_client.call(json.dumps(
                        {
                            "project": project_id,
                            "model_type": model_type
                        }), "remove_models")
                
                logger.debug("Response for model_type '%s': %s", model_type, response)
        except Exception as err:
            logger.error(err)

        if _amqp_client is not None:
            _amqp_client.close_connections()

    def check_metrics(self, res, model_type):
        if not res:
            return False, []
        cur_metrics = []
        should_be_deleted = False
        for field, operator, score in self.models_conditions[model_type]:
            scores = []
            for r in res["hits"]["hits"]:
                if field in r["_source"]:
                    scores.append(r["_source"][field])
            if scores:
                cur_metrics.append((field, np.mean(scores)))
                if utils.compare_metrics(np.mean(scores), score, operator):
                    should_be_deleted = True
        return should_be_deleted, cur_metrics

    def should_model_be_deleted(self, model_type, project_id):
        cur_date = utils.take_the_date_to_check()
        week_earlier = cur_date - datetime.timedelta(days=7)
        cur_tommorow = cur_date + datetime.timedelta(days=1)
        if model_type == "auto_analysis":
            if not self.index_exists(self.es_client.main_index, print_error=False):
                res = []
            else:
                res = self.es_client.search(self.es_client.main_index, body={
                "size": 10000,
                "query": {
                    "bool": {
                        "filter": [
                            {"range": {"gather_datetime": {
                                "gte": week_earlier.strftime("%Y-%m-%d %H:%M:%S"),
                                "lte": cur_tommorow.strftime("%Y-%m-%d %H:%M:%S")}}},
                            {"term": {"project_id": project_id}}
                        ]
                    }
                }})
            return self.check_metrics(res, model_type)
        elif model_type == "suggest":
            return False, []
        return False, []
