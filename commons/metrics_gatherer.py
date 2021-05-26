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
import datetime
from time import time
from sklearn.metrics import f1_score, accuracy_score
from commons import postgres_dao
from commons import es_client
from commons import models_remover
from utils import utils

logger = logging.getLogger("metricsGatherer.metrics_gatherer")


class MetricsGatherer:

    def __init__(self, app_settings):
        self.app_settings = app_settings
        self.postgres_dao = postgres_dao.PostgresDAO(app_settings)
        self.es_client = es_client.EsClient(
            esHost=app_settings["esHost"],
            grafanaHost=app_settings["grafanaHost"],
            app_config=app_settings)
        self.models_remover = models_remover.ModelsRemover(app_settings)

    def get_current_date_template(self, project_id, project_name, cur_date):
        return {"on": 0,  "changed_type": 0, "AA_analyzed": 0,
                "f1-score": 0, "accuracy": 0,
                "launch_analyzed": 0,
                "manually_analyzed": 0, "project_id": project_id,
                "project_name": project_name, "gather_date": cur_date.date().strftime("%Y-%m-%d"),
                "gather_datetime": cur_date.date().strftime("%Y-%m-%d %H:%M:%S"),
                "percent_not_found_aa": 0, "avg_processing_time_only_found_test_item_aa": 0.0,
                "avg_processing_time_test_item_aa": 0.0, "percent_not_found_suggest": 0,
                "avg_processing_time_test_item_suggest": 0.0,
                "avg_processing_time_test_item_cluster": 0.0,
                "launch_added": 0,
                "percent_not_found_cluster": 0,
                "module_version": [],
                "model_info": [],
                "errors": [],
                "errors_count": 0}

    def replace_issue_type_with_code(self, val, issue_types_dict):
        new_issue_value = val
        if new_issue_value in issue_types_dict:
            new_issue_value = issue_types_dict[new_issue_value]
        return new_issue_value

    def derive_item_activity_chain(self, activities, issue_types_dict):
        item_chain = {}
        for record in activities:
            if record["action"] == "analyzeItem":
                if record["object_id"] not in item_chain:
                    item_chain[record["object_id"]] = []
                for r in record["details"]["history"]:
                    if r["field"] == 'issueType':
                        item_chain[record["object_id"]].append(
                            ("analyze", self.replace_issue_type_with_code(r["newValue"], issue_types_dict)))
            if record["action"] == "updateItem":
                if record["object_id"] not in item_chain:
                    item_chain[record["object_id"]] = []
                for r in record["details"]["history"]:
                    if r["field"] == 'issueType':
                        item_chain[record["object_id"]].append(
                            ("manual",
                             self.replace_issue_type_with_code(r["newValue"], issue_types_dict),
                             self.replace_issue_type_with_code(r["oldValue"], issue_types_dict)))
        return item_chain

    def calculate_metrics(self, item_chain, cur_date_results):
        cnt_changed = 0
        cnt_all_analyzed = 0
        analyzed_test_item_types = []
        real_test_item_types = []
        unique_launch_ids = set()
        manually_analyzed_cnt = 0
        for item in item_chain:
            was_analyzed = False
            analyzed_test_item_type = None
            real_test_item_type = None
            for idx in range(len(item_chain[item])):
                action = item_chain[item][idx]
                if action[0] == "manual" and action[2][:2].lower() == "ti":
                    manually_analyzed_cnt += 1
                if action[0] == "manual" and (action[1][:2].lower() == "ti" or action[2][:2].lower() == "ti"):
                    continue
                if action[0] == "analyze":
                    was_analyzed = True
                if was_analyzed and action[0] == "manual":
                    cnt_changed += 1
                    break
            for idx in range(len(item_chain[item])):
                action = item_chain[item][idx]
                if action[0] == "analyze":
                    analyzed_test_item_type = action[1]
                    real_test_item_type = None
                if was_analyzed and action[0] == "manual":
                    real_test_item_type = action[1]
            if was_analyzed:
                cnt_all_analyzed += 1
                launch_id = self.postgres_dao.get_launch_id(item)
                if launch_id:
                    unique_launch_ids.add(launch_id)
            if analyzed_test_item_type is None:
                continue
            analyzed_test_item_types.append(analyzed_test_item_type)
            if real_test_item_type is not None:
                real_test_item_types.append(real_test_item_type)
            else:
                real_test_item_types.append(analyzed_test_item_type)
        cur_date_results["AA_analyzed"] = cnt_all_analyzed
        cur_date_results["changed_type"] = cnt_changed
        cur_date_results["launch_analyzed"] = max(
            len(unique_launch_ids), cur_date_results["launch_analyzed"])
        cur_date_results["manually_analyzed"] = manually_analyzed_cnt
        cur_date_results = self.calculate_accuracy_f1_score(
            real_test_item_types, analyzed_test_item_types, cur_date_results)
        return cur_date_results

    def calculate_accuracy_f1_score(
            self, real_test_item_types, analyzed_test_item_types, cur_date_results):
        if not analyzed_test_item_types:
            cur_date_results["accuracy"] = 100
            cur_date_results["f1-score"] = 100
        else:
            cur_date_results["accuracy"] = round(accuracy_score(
                y_true=real_test_item_types, y_pred=analyzed_test_item_types), 2) * 100
            cur_date_results["f1-score"] = round(f1_score(
                y_true=real_test_item_types, y_pred=analyzed_test_item_types,
                average="macro"), 2) * 100
        return cur_date_results

    def calculate_rp_stats_metrics(self, cur_date_results, project_id, cur_date):
        week_earlier = cur_date - datetime.timedelta(days=7)
        cur_tommorow = cur_date + datetime.timedelta(days=1)
        all_activities = self.es_client.get_activities(project_id, week_earlier, cur_tommorow)
        activities_res = {}
        unique_analyzed_launch_ids = set()
        for res in all_activities:
            if res["_source"]["method"] not in activities_res:
                activities_res[res["_source"]["method"]] = {
                    "percent_not_found": 0, "count": 0,
                    "avg_time_only_found_test_item_processed": 0.0,
                    "avg_time_test_item_processed": 0.0,
                    "model_info": [],
                    "module_version": [],
                    "errors": [],
                    "errors_count": 0}
            if res["_source"]["items_to_process"] == 0:
                continue
            if res["_source"]["method"] == "auto_analysis":
                unique_analyzed_launch_ids.add(res["_source"]["launch_id"])
            method_activity = activities_res[res["_source"]["method"]]
            percent_not_found = round(
                res["_source"]["not_found"] / res["_source"]["items_to_process"], 2) * 100
            method_activity["percent_not_found"] += percent_not_found
            method_activity["count"] += 1
            processed_fully = res["_source"]["items_to_process"] - res["_source"]["not_found"]
            if processed_fully == 0:
                processed_fully = 1
            avg_time_only_found = round(res["_source"]["processed_time"] / processed_fully, 2)
            avg_time_all = round(res["_source"]["processed_time"] / res["_source"]["items_to_process"], 2)
            method_activity["avg_time_only_found_test_item_processed"] += avg_time_only_found
            method_activity["avg_time_test_item_processed"] += avg_time_all
            if "model_info" in res["_source"]:
                method_activity["model_info"].extend(res["_source"]["model_info"])
            if "module_version" in res["_source"]:
                method_activity["module_version"].extend(res["_source"]["module_version"])
            if "errors" in res["_source"]:
                method_activity["errors"].extend(res["_source"]["errors"])
            if "errors_count" in res["_source"]:
                method_activity["errors_count"] += res["_source"]["errors_count"]
        for action_res, action_val in activities_res.items():
            for column in ["model_info", "module_version", "errors", "errors_count"]:
                default_obj = 0
                if type(action_val[column]) == list:
                    default_obj = []
                if column not in cur_date_results:
                    cur_date_results[column] = default_obj
                if type(action_val[column]) == list:
                    cur_date_results[column].extend(action_val[column])
                if type(action_val[column]) == int:
                    cur_date_results[column] += action_val[column]
            if action_val["count"] == 0:
                continue
            percent_not_found = round(action_val["percent_not_found"] / action_val["count"], 0)
            all_avg_time = round(action_val["avg_time_test_item_processed"] / action_val["count"], 2)
            if action_res == "auto_analysis":
                cur_date_results["percent_not_found_aa"] = percent_not_found
                avg_time = round(
                    action_val["avg_time_only_found_test_item_processed"] / action_val["count"], 2)
                cur_date_results["avg_processing_time_only_found_test_item_aa"] = avg_time
                cur_date_results["avg_processing_time_test_item_aa"] = all_avg_time
            if action_res == "suggest":
                cur_date_results["percent_not_found_suggest"] = percent_not_found
                cur_date_results["avg_processing_time_test_item_suggest"] = all_avg_time
            if action_res == "find_clusters":
                cur_date_results["percent_not_found_cluster"] = percent_not_found
                cur_date_results["avg_processing_time_test_item_cluster"] = all_avg_time
        for column in ["model_info", "module_version"]:
            cur_date_results[column] = list(set(cur_date_results[column]))
        cur_date_results["launch_analyzed"] = len(unique_analyzed_launch_ids)
        return cur_date_results

    def gather_metrics_by_project(self, project_id, project_name, cur_date):
        week_earlier = cur_date - datetime.timedelta(days=7)
        cur_tommorow = cur_date + datetime.timedelta(days=1)
        is_aa_enabled = self.postgres_dao.is_auto_analysis_enabled_for_project(project_id)
        cur_date_results = self.get_current_date_template(project_id, project_name, cur_date)
        cur_date_results["on"] = int(is_aa_enabled)
        cur_date_results = self.calculate_rp_stats_metrics(cur_date_results, project_id, cur_date)
        activities = self.postgres_dao.get_activities_by_project(project_id, week_earlier, cur_tommorow)
        issue_types_dict = self.postgres_dao.get_issue_type_dict(project_id)
        item_chain = self.derive_item_activity_chain(activities, issue_types_dict)
        cur_date_results = self.calculate_metrics(item_chain, cur_date_results)
        all_launch_ids = self.postgres_dao.get_all_unique_launch_ids(
            project_id, week_earlier, cur_tommorow)
        cur_date_results["launch_added"] = len(all_launch_ids)
        return cur_date_results

    def find_sequence_of_aa_enability(self, project_id, cur_date, project_aa_states):
        week_earlier = cur_date - datetime.timedelta(days=7)
        cur_tommorow = cur_date + datetime.timedelta(days=1)
        activities = self.postgres_dao.get_activities_by_project(project_id, week_earlier, cur_tommorow)
        for record in activities:
            if record["action"] == "updateAnalyzer":
                for r in record["details"]["history"]:
                    if r["field"] == 'analyzer.isAutoAnalyzerEnabled':
                        creation_date = record["creation_date"].date()
                        is_enabled = int(r["newValue"].lower() == "true")
                        if creation_date not in project_aa_states:
                            project_aa_states[creation_date] = (is_enabled, is_enabled)
                        project_aa_states[creation_date] = (project_aa_states[creation_date][0], is_enabled)
        return project_aa_states

    def fill_right_aa_enable_states(self, gathered_rows, project_aa_states):
        cur_state_ind = 0
        sorted_dates = sorted(project_aa_states.items(), key=lambda x: x[0])
        for row in gathered_rows:
            while len(project_aa_states) > cur_state_ind:
                if row["gather_date"] < sorted_dates[cur_state_ind][0]:
                    row["on"] = 1 - sorted_dates[cur_state_ind][1][0]
                    break
                elif row["gather_date"] == sorted_dates[cur_state_ind][0]:
                    row["on"] = sorted_dates[cur_state_ind][1][1]
                    cur_state_ind += 1
                else:
                    cur_state_ind += 1
        return gathered_rows

    def gather_metrics(self, period_start, period_end):
        all_projects = self.postgres_dao.get_all_projects()
        start_time = time()
        for project_info in all_projects:
            start_project_time = time()
            try:
                project_id = project_info["id"]
                project_name = project_info["name"]
                project_with_prefix = utils.unite_project_name(
                    str(project_id), self.app_settings["esProjectIndexPrefix"])
                if not self.es_client.index_exists(project_with_prefix, print_error=False):
                    continue
                gathered_rows = []
                project_aa_states = {}
                for st_date_day in range((period_end - period_start).days + 1):
                    cur_date = period_start + datetime.timedelta(days=st_date_day)
                    project_aa_states = self.find_sequence_of_aa_enability(
                        project_id, cur_date, project_aa_states)
                    gathered_row = self.gather_metrics_by_project(project_id, project_name, cur_date)
                    gathered_rows.append(gathered_row)
                gathered_rows = self.fill_right_aa_enable_states(gathered_rows, project_aa_states)
                bulk_actions = [{
                    '_id': "%s_%s" % (row["project_id"], row["gather_date"]),
                    '_index': self.es_client.main_index,
                    '_source': row,
                } for row in gathered_rows]
                self.es_client.bulk_index(self.es_client.main_index, bulk_actions)
                self.models_remover.apply_remove_model_policies(project_id)
            except Exception as err:
                logger.error("Error occured for project %s", project_info)
                logger.error(err)
            logger.debug("Project info %s gathering took %.2f s.",
                         project_info["id"], time() - start_project_time)
        logger.info("Finished gathering metrics for all projects for %.2f s.", time() - start_time)
