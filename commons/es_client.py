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
import elasticsearch
import elasticsearch.helpers
from utils import utils
import requests
import json
import datetime

logger = logging.getLogger("metricsGatherer.es_client")


class EsClient:

    def __init__(self, esHost, grafanaHost):
        self.esHost = esHost
        self.grafanaHost = grafanaHost
        self.kibana_headers = {'kbn-xsrf': 'commons.elastic'}
        self.main_index = "rp_stats"
        self.task_done_index = "done_tasks"
        self.rp_aa_stats_index = "rp_aa_stats"
        self.rp_model_train_stats_index = "rp_model_train_stats"
        self.es_client = elasticsearch.Elasticsearch(self.esHost)

    def update_settings_after_read_only(self):
        requests.put(
            "{}/_all/_settings".format(
                self.esHost
            ),
            headers={"Content-Type": "application/json"},
            data="{\"index.blocks.read_only_allow_delete\": null}"
        ).raise_for_status()

    def delete_grafana_datasource_by_name(self, index_name):
        try:
            res = requests.get(
                "%s/api/datasources/name/%s" % (self.grafanaHost, index_name))
            res.raise_for_status()
        except Exception as err:
            logger.error(err)
            return
        try:
            index_id = json.loads(res.content)["id"]
            requests.delete("%s/api/datasources/%s" % (self.grafanaHost, index_id)).raise_for_status()
        except Exception as err:
            logger.error(err)

    def create_grafana_data_source(self, index_name, time_field, index_properties):
        index_exists = False
        if not self.index_exists(index_name, print_error=False):
            response = self.create_index(index_name, index_properties)
            if len(response):
                index_exists = True
        else:
            index_exists = True
        if index_exists:
            self.delete_grafana_datasource_by_name(index_name)
            es_user, es_pass = utils.get_credentials_from_url(self.esHost)
            try:
                requests.post(
                    "%s/api/datasources" % self.grafanaHost,
                    data=json.dumps({
                        "name": index_name,
                        "type": "elasticsearch",
                        "url": utils.remove_credentials_from_url(self.esHost),
                        "access": "proxy",
                        "basicAuth": len(es_user) > 0,
                        "basicAuthUser": es_user,
                        "secureJsonData": {
                            "basicAuthPassword": es_pass
                        },
                        "database": index_name,
                        "jsonData": {
                            "esVersion": 70,
                            "maxConcurrentShardRequests": "1",
                            "timeField": time_field}
                    }), headers={"content-type": "application/json"}
                ).raise_for_status()
                return True
            except Exception as err:
                logger.error("Can't create grafana datasource")
                logger.error(err)
                return False
        return False

    def import_dashboard(self, dashboard_id):
        dashboard_info = utils.read_json_file(
            "", "{}.json".format(dashboard_id), to_json=True)
        requests.post("%s/api/dashboards/db" % self.grafanaHost, data=json.dumps({
            "dashboard": dashboard_info["dashboard"],
            "folderId": dashboard_info["meta"]["folderId"],
            "refresh": True,
            "overwrite": True
        }), headers={'content-type': 'application/json'}).raise_for_status()

    @staticmethod
    def send_request(url, method):
        """Send request with specified url and http method"""
        try:
            response = requests.get(url) if method == "GET" else {}
            data = response._content.decode("utf-8")
            content = json.loads(data, strict=False)
            return content
        except Exception as err:
            logger.error("Error with loading url: %s", utils.remove_credentials_from_url(url))
            logger.error(err)
        return []

    def is_healthy(self):
        """Check whether elasticsearch is healthy"""
        try:
            url = utils.build_url(self.esHost, ["_cluster/health"])
            res = EsClient.send_request(url, "GET")
            return res["status"] in ["green", "yellow"]
        except Exception as err:
            logger.error("Elasticsearch is not healthy")
            logger.error(err)
            return False

    def is_grafana_healthy(self):
        """Check whether grafana is healthy"""
        try:
            url = utils.build_url(self.grafanaHost, ["api/health"])
            res = EsClient.send_request(url, "GET")
            return res["database"].lower() == "ok"
        except Exception as err:
            logger.error("Grafana is not healthy")
            logger.error(err)
            return False

    def index_exists(self, index_name, print_error=True):
        try:
            index = self.es_client.indices.get(index=str(index_name))
            return index is not None
        except Exception as err:
            if print_error:
                logger.error("Index %s was not found", str(index_name))
                logger.error("ES Url %s", self.host)
                logger.error(err)
            return False

    def create_index(self, index_name, index_properties):
        logger.debug("Creating '%s' Elasticsearch index", str(index_name))
        try:
            response = self.es_client.indices.create(index=str(index_name), body={
                'settings': {"number_of_shards": 1},
                'mappings': index_properties
            })
            logger.debug("Created '%s' Elasticsearch index", str(index_name))
            return response
        except Exception as err:
            logger.error("Couldn't create index")
            logger.error("ES Url %s", utils.remove_credentials_from_url(
                self.esHost))
            logger.error(err)
            return {}

    def bulk_index(self, index_name, bulk_actions):
        exists_index = False
        index_properties = utils.read_json_file(
            "", "%s_mappings.json" % index_name, to_json=True)
        if not self.index_exists(index_name, print_error=False):
            response = self.create_index(index_name, index_properties)
            if len(response):
                exists_index = True
        else:
            exists_index = True
        if exists_index:
            try:
                self.es_client.indices.put_mapping(
                    index=index_name,
                    body=index_properties)
                logger.debug('Indexing %d docs...' % len(bulk_actions))
                try:
                    success_count, errors = elasticsearch.helpers.bulk(self.es_client,
                                                                       bulk_actions,
                                                                       chunk_size=1000,
                                                                       request_timeout=30,
                                                                       refresh=True)
                except Exception as err:
                    logger.error(err)
                    self.update_settings_after_read_only()
                    success_count, errors = elasticsearch.helpers.bulk(self.es_client,
                                                                       bulk_actions,
                                                                       chunk_size=1000,
                                                                       request_timeout=30,
                                                                       refresh=True)

                logger.debug("Processed %d logs", success_count)
                if errors:
                    logger.debug("Occured errors %s", errors)
            except Exception as err:
                logger.error(err)
                logger.error("Bulking index for %s index finished with errors", index_name)

    def is_the_date_metrics_calculated(self, date):
        if not self.index_exists(self.task_done_index, print_error=False):
            return False
        res = self.es_client.search(self.task_done_index, body={
            "query": {
                "bool": {
                    "filter": [
                        {"term": {"gather_date": date.date()}}
                    ]
                }
            }})
        return len(res["hits"]["hits"]) > 0

    def get_activities(self, project_id, week_earlier, cur_tommorow):
        if not self.index_exists(self.rp_aa_stats_index, print_error=False):
            return []
        res = self.es_client.search(self.rp_aa_stats_index, body={
            "size": 10000,
            "query": {
                "bool": {
                    "filter": [
                        {"range": {"gather_date": {"gte": week_earlier.strftime("%Y-%m-%d %H:%M:%S"),
                                                   "lte": cur_tommorow.strftime("%Y-%m-%d %H:%M:%S")}}},
                        {"term": {"project_id": project_id}}
                    ]
                }
            }})
        return res["hits"]["hits"]

    def delete_old_info(self, max_days_store):
        for index in [self.main_index, self.rp_aa_stats_index, self.task_done_index]:
            last_allowed_date = datetime.datetime.now() - datetime.timedelta(days=int(max_days_store))
            last_allowed_date = last_allowed_date.strftime("%Y-%m-%d")
            all_ids = set()
            try:
                search_query = {
                    "size": 10000,
                    "query": {
                        "bool": {
                            "filter": [
                                {
                                    "range": {
                                        "gather_date": {
                                            "lte": last_allowed_date
                                        }
                                    }
                                }
                            ]
                        }
                    }
                }
                for res in elasticsearch.helpers.scan(self.es_client,
                                                      query=search_query,
                                                      index=index,
                                                      scroll="5m"):
                    all_ids.add(res["_id"])
                bodies = []
                for _id in all_ids:
                    bodies.append({
                        "_op_type": "delete",
                        "_id":      _id,
                        "_index":   index,
                    })
                success_count, errors = elasticsearch.helpers.bulk(self.es_client,
                                                                   bodies,
                                                                   chunk_size=1000,
                                                                   request_timeout=30,
                                                                   refresh=True)
            except Exception as err:
                logger.error("Couldn't delete old info in the index %s", index)
                logger.error(err)
            logger.debug("Finished deleting old info for index %s", index)
