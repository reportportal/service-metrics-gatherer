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

from commons.model_remove_policy.model_remove_policy import ModelRemovePolicy


class AutoAnalysisModelRemovePolicy(ModelRemovePolicy):

    def __init__(self, app_config,
                 conditions_field="autoAnalysisModelRemovePolicy",
                 model_name="auto_analysis"):
        ModelRemovePolicy.__init__(
            self, app_config, conditions_field=conditions_field, model_name=model_name)

    def get_gathered_metrics(self, week_earlier, cur_tommorow, project_id):
        if not self.es_client.index_exists(self.es_client.main_index, print_error=False):
            return []
        else:
            res = self.es_client.es_client.search(self.es_client.main_index, body={
                "size": 1000,
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
            return res
