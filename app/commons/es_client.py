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

import datetime
import json
import logging
import traceback

import elasticsearch
import elasticsearch.helpers
import requests
import urllib3
from elasticsearch import RequestsHttpConnection

from app.utils import utils, text_processing

logger = logging.getLogger("metricsGatherer.es_client")


class EsClient:

    def __init__(self, esHost, grafanaHost, app_config):
        self.esHost = esHost
        self.grafanaHost = grafanaHost
        self.app_config = app_config
        self.kibana_headers = {'kbn-xsrf': 'commons.elastic'}
        self.main_index = "rp_stats"
        self.task_done_index = "rp_done_tasks"
        self.rp_aa_stats_index = "rp_aa_stats"
        self.rp_model_train_stats_index = "rp_model_train_stats"
        self.rp_suggest_metrics_index = "rp_suggestions_info_metrics"
        self.rp_model_remove_stats_index = "rp_model_remove_stats"
        self.tables_to_recreate = [self.rp_aa_stats_index, self.rp_model_train_stats_index,
                                   self.rp_suggest_metrics_index, self.rp_model_remove_stats_index]
        self.es_client = self.create_es_client(self.esHost, app_config)

    def create_es_client(self, es_host, app_config):
        if not app_config["esVerifyCerts"]:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        kwargs = {
            "timeout": 30,
            "max_retries": 5,
            "retry_on_timeout": True,
            "use_ssl": app_config["esUseSsl"],
            "verify_certs": app_config["esVerifyCerts"],
            "ssl_show_warn": app_config["esSslShowWarn"],
            "ca_certs": app_config["esCAcert"],
            "client_cert": app_config["esClientCert"],
            "client_key": app_config["esClientKey"],
        }

        if app_config["esUser"]:
            kwargs["http_auth"] = (app_config["esUser"],
                                   app_config["esPassword"])

        if app_config["turnOffSslVerification"]:
            kwargs["connection_class"] = RequestsHttpConnection

        return elasticsearch.Elasticsearch([es_host], **kwargs)

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

    def create_grafana_data_source(self, esHostGrafanaDatasource, index_name, time_field):
        index_exists = False
        index_properties = utils.read_json_file(
            "res", "%s_mappings.json" % index_name, to_json=True)
        if not self.index_exists(index_name, print_error=False):
            response = self.create_index(index_name, index_properties)
            if len(response):
                index_exists = True
        else:
            index_exists = True
        if index_exists:
            self.delete_grafana_datasource_by_name(index_name)
            es_user, es_pass = text_processing.get_credentials_from_url(esHostGrafanaDatasource)
            try:
                requests.post(
                    "%s/api/datasources" % self.grafanaHost,
                    data=json.dumps({
                        "name": index_name,
                        "type": "elasticsearch",
                        "url": text_processing.remove_credentials_from_url(esHostGrafanaDatasource),
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
            "res", "{}.json".format(dashboard_id), to_json=True)
        requests.post("%s/api/dashboards/db" % self.grafanaHost, data=json.dumps({
            "dashboard": dashboard_info["dashboard"],
            "folderId": dashboard_info["meta"]["folderId"],
            "refresh": True,
            "overwrite": True
        }), headers={'content-type': 'application/json'}).raise_for_status()

    @staticmethod
    def send_request(url, method, username, password):
        """Send request with specified url and http method"""
        try:
            if username.strip() and password.strip():
                response = requests.get(url, auth=(username, password)) if method == "GET" else {}
            else:
                response = requests.get(url) if method == "GET" else {}
            data = response._content.decode("utf-8")
            content = json.loads(data, strict=False)
            return content
        except Exception as err:
            logger.error("Error with loading url: %s", text_processing.remove_credentials_from_url(url))
            logger.error(err)
        return []

    def is_healthy(self):
        """Check whether elasticsearch is healthy"""
        try:
            url = text_processing.build_url(self.esHost, ["_cluster/health"])
            res = EsClient.send_request(url, "GET", self.app_config["esUser"], self.app_config["esPassword"])
            return res["status"] in ["green", "yellow"]
        except Exception as err:
            logger.error("Elasticsearch is not healthy")
            logger.error(err)
            return False

    def is_grafana_healthy(self):
        """Check whether grafana is healthy"""
        try:
            url = text_processing.build_url(self.grafanaHost, ["api/health"])
            res = EsClient.send_request(url, "GET", "", "")
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

    def object_exists(self, index_name, row_id):
        try:
            _ = self.es_client.get(index_name, id=row_id)
            return True
        except Exception as err:  # noqa
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
            logger.error("ES Url %s", text_processing.remove_credentials_from_url(
                self.esHost))
            logger.error(err)
            return {}

    def delete_index(self, index_name):
        """Delete the whole index"""
        try:
            self.es_client.indices.delete(index=str(index_name))
            logger.info("ES Url %s", text_processing.remove_credentials_from_url(self.esHost))
            logger.debug("Deleted index %s", str(index_name))
            return True
        except Exception as err:
            logger.error("Not found %s for deleting", str(index_name))
            logger.error("ES Url %s", text_processing.remove_credentials_from_url(self.esHost))
            logger.error(err)
            return False

    def _recreate_index_if_needed(self, bodies, formatted_exception):
        index_name = ""
        if bodies:
            index_name = bodies[0]["_index"]
        if not index_name.strip():
            return
        index_properties = utils.read_json_file(
            "res", "%s_mappings.json" % index_name, to_json=True)
        if "'type': 'mapper_parsing_exception'" in formatted_exception or \
                "RequestError(400, 'illegal_argument_exception'" in formatted_exception:
            if index_name in self.tables_to_recreate:
                self.delete_index(index_name)
                self.create_index(index_name, index_properties)

    def bulk_index(self, index_name, bulk_actions):
        exists_index = False
        index_properties = utils.read_json_file(
            "res", "%s_mappings.json" % index_name, to_json=True)
        if not self.index_exists(index_name, print_error=False):
            response = self.create_index(index_name, index_properties)
            if len(response):
                exists_index = True
        else:
            exists_index = True
        if exists_index:
            try:
                try:
                    self.es_client.indices.put_mapping(
                        index=index_name,
                        body=index_properties)
                except:  # noqa
                    formatted_exception = traceback.format_exc()
                    self._recreate_index_if_needed(bulk_actions, formatted_exception)
                logger.debug('Indexing %d docs...' % len(bulk_actions))
                try:
                    success_count, errors = elasticsearch.helpers.bulk(self.es_client,
                                                                       bulk_actions,
                                                                       chunk_size=1000,
                                                                       request_timeout=30,
                                                                       refresh=True)
                except:  # noqa
                    formatted_exception = traceback.format_exc()
                    self._recreate_index_if_needed(bulk_actions, formatted_exception)
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
                        {"range": {"gather_datetime": {"gte": week_earlier.strftime("%Y-%m-%d %H:%M:%S"),
                                                       "lte": cur_tommorow.strftime("%Y-%m-%d %H:%M:%S")}}},
                        {"term": {"project_id": project_id}}
                    ]
                }
            }})
        return res["hits"]["hits"]

    def delete_old_info(self, max_days_store):
        for index in [
            self.main_index, self.rp_aa_stats_index,
            self.task_done_index, self.rp_model_train_stats_index,
            self.rp_suggest_metrics_index, self.rp_model_remove_stats_index]:
            last_allowed_date = datetime.datetime.now() - datetime.timedelta(days=int(max_days_store))
            last_allowed_date = last_allowed_date.strftime("%Y-%m-%d")
            all_ids = set()
            try:
                search_query = {
                    "size": 1000,
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
                        "_id": _id,
                        "_index": index,
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
