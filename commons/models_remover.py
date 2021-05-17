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
from commons.model_remove_policy.auto_analysis_model_remove_policy import AutoAnalysisModelRemovePolicy
from commons.model_remove_policy.suggest_model_remove_policy import SuggestModelRemovePolicy

logger = logging.getLogger("metricsGatherer.models_remover")


class ModelsRemover:

    def __init__(self, app_config):
        self.app_config = app_config
        self.model_policies = {}
        for policy in [
                AutoAnalysisModelRemovePolicy(app_config),
                SuggestModelRemovePolicy(app_config)]:
            self.model_policies[policy.model_name] = policy
        self.es_client = es_client.EsClient(
            esHost=app_config["esHost"],
            grafanaHost=app_config["grafanaHost"],
            app_config=app_config)

    def apply_remove_model_policies(self, project_id):
        _amqp_client = None
        try:
            _amqp_client = amqp.AmqpClient(self.app_config)
            bulk_actions = []
            for model_type in self.model_policies:
                model_info = _amqp_client.call(json.dumps(
                    {
                        "project": project_id,
                        "model_type": model_type
                    }), "get_model_info")
                model_folder = model_info["model_folder"]
                if not model_folder.strip():
                    continue
                logger.debug("Model folder %s", model_folder)
                should_be_deleted, cur_metrics, module_version = self.should_model_be_deleted(
                    model_type, project_id)
                is_deleted = False
                if should_be_deleted:
                    is_deleted = _amqp_client.call(json.dumps(
                        {
                            "project": project_id,
                            "model_type": model_type
                        }), "remove_models")
                model_remove_info = {
                    "model_type": model_type,
                    "model_folder": model_folder,
                    "project_id": project_id,
                    "metric_conditions": self.model_policies[model_type].get_conditions(),
                    "metric_values": utils.convert_metrics_to_string(cur_metrics),
                    "model_removed": int(is_deleted),
                    "gather_date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "module_version": module_version
                }
                bulk_actions.append({
                    "_index": self.es_client.rp_model_remove_stats_index,
                    "_source": model_remove_info
                })
                logger.debug("Model type: '%s', is removed: %s, model folder: %s",
                             model_type, is_deleted, model_folder)
            self.es_client.bulk_index(
                self.es_client.rp_model_remove_stats_index,
                bulk_actions)
        except Exception as err:
            logger.error(err)

        if _amqp_client is not None:
            _amqp_client.close_connections()

    def should_model_be_deleted(self, model_type, project_id):
        cur_date = utils.take_the_date_to_check()
        week_earlier = cur_date - datetime.timedelta(days=7)
        cur_tommorow = cur_date + datetime.timedelta(days=1)
        if model_type in self.model_policies:
            metrics = self.model_policies[model_type].get_gathered_metrics(
                week_earlier, cur_tommorow, project_id)
            return self.model_policies[model_type].check_metrics(metrics)
        return False, [], []
