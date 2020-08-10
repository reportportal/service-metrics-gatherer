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
from sklearn.metrics import f1_score, accuracy_score
from commons import postgres_dao
from commons import es_client

logger = logging.getLogger("metricsGatherer.metrics_gatherer")


class MetricsGatherer:

    def __init__(self, app_settings):
        self.app_settings = app_settings
        self.postgres_dao = postgres_dao.PostgresDAO(app_settings)
        self.es_client = es_client.EsClient(app_settings)

    def get_current_date_template(self, project_id, project_name, cur_date):
        return {"on": 0,  "changed_type": 0, "AA_analyzed": 0,
                "f1-score": 0, "accuracy": 0,
                "launch_analyzed": 0,
                "manually_analyzed": 0, "project_id": project_id,
                "project_name": project_name, "gather_date": cur_date}

    def derive_item_activity_chain(self, activities):
        item_chain = {}
        for record in activities:
            if record["action"] == "analyzeItem":
                if record["object_id"] not in item_chain:
                    item_chain[record["object_id"]] = []
                for r in record["details"]["history"]:
                    if r["field"] == 'issueType':
                        item_chain[record["object_id"]].append(("analyze", r["newValue"]))
            if record["action"] == "updateItem":
                if record["object_id"] not in item_chain:
                    item_chain[record["object_id"]] = []
                for r in record["details"]["history"]:
                    if r["field"] == 'issueType':
                        item_chain[record["object_id"]].append(("manual", r["newValue"], r["oldValue"]))
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
                if action[0] == "manual" and action[2] == "To Investigate":
                    manually_analyzed_cnt += 1
                if action[0] == "manual" and (action[1] == "To Investigate" or action[2] == "To Investigate"):
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
        cur_date_results["launch_analyzed"] = len(unique_launch_ids)
        cur_date_results["manually_analyzed"] = manually_analyzed_cnt
        cur_date_results = self.calculate_accuracy_f1_score(
            real_test_item_types, analyzed_test_item_types, cur_date_results)
        return cur_date_results

    def calculate_accuracy_f1_score(
            self, real_test_item_types, analyzed_test_item_types, cur_date_results):
        if not analyzed_test_item_types:
            cur_date_results["accuracy"] = 1.0
            cur_date_results["f1-score"] = 1.0
        else:
            cur_date_results["accuracy"] = accuracy_score(
                y_true=real_test_item_types, y_pred=analyzed_test_item_types)
            cur_date_results["f1-score"] = f1_score(
                y_true=real_test_item_types, y_pred=analyzed_test_item_types, average="macro")
        return cur_date_results

    def gather_metrics_by_project(self, project_id, project_name, cur_date):
        week_earlier = cur_date - datetime.timedelta(days=7)
        cur_tommorow = cur_date + datetime.timedelta(days=1)
        is_aa_enabled = self.postgres_dao.is_auto_analysis_enabled_for_project(project_id)
        cur_date_results = self.get_current_date_template(project_id, project_name, cur_date)
        cur_date_results["on"] = int(is_aa_enabled)
        activities = self.postgres_dao.get_activities_by_project(project_id, week_earlier, cur_tommorow)
        item_chain = self.derive_item_activity_chain(activities)
        cur_date_results = self.calculate_metrics(item_chain, cur_date_results)
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
                if row["gather_date"].date() < sorted_dates[cur_state_ind][0]:
                    row["on"] = 1 - sorted_dates[cur_state_ind][1][0]
                    break
                elif row["gather_date"].date() == sorted_dates[cur_state_ind][0]:
                    row["on"] = sorted_dates[cur_state_ind][1][1]
                    cur_state_ind += 1
                else:
                    cur_state_ind += 1
        return gathered_rows

    def gather_metrics(self, period_start, period_end):
        all_projects = self.postgres_dao.get_all_projects()
        for project_info in all_projects:
            try:
                project_id = project_info["id"]
                project_name = project_info["name"]
                gathered_rows = []
                project_aa_states = {}
                for st_date_day in range((period_end - period_start).days + 1):
                    cur_date = period_start + datetime.timedelta(days=st_date_day)
                    project_aa_states = self.find_sequence_of_aa_enability(
                        project_id, cur_date, project_aa_states)
                    gathered_row = self.gather_metrics_by_project(project_id, project_name, cur_date)
                    gathered_rows.append(gathered_row)
                gathered_rows = self.fill_right_aa_enable_states(gathered_rows, project_aa_states)
                self.es_client.bulk_main_index(gathered_rows)
            except Exception as err:
                logger.error("Error occured for project %s", project_info)
                logger.error(err)
