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

logger = logging.getLogger("metricsGatherer.es_client")


class EsClient:

    def __init__(self, app_settings):
        self.app_settings = app_settings
        self.kibana_headers = {'kbn-xsrf': 'commons.elastic'}
        self.es_client = elasticsearch.Elasticsearch(self.app_settings["esHost"])

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

    def create_index(self, index_name):
        logger.debug("Creating '%s' Elasticsearch index", str(index_name))
        try:
            response = self.es_client.indices.create(index=str(index_name), body={
                'settings': {"number_of_shards": 1},
                'mappings': {"default": utils.read_json_file("", "index_mapping_settings.json", to_json=True)}
            })
            logger.debug("Created '%s' Elasticsearch index", str(index_name))
            return response
        except Exception as err:
            logger.error("Couldn't create index")
            logger.error("ES Url %s", utils.remove_credentials_from_url(
                self.app_settings["esHost"]))
            logger.error(err)
            return {}

    def create_pattern(self, pattern_id, time_field):
        logger.debug("Creating '%s' Kibana index pattern object", pattern_id)
        attribs = {'title': pattern_id}
        if time_field is not None:
            attribs['timeFieldName'] = time_field
        requests.post(
            '%s/api/saved_objects/index-pattern/%s?overwrite=true' % (
                self.app_settings["kibanaHost"],
                pattern_id,
            ),
            headers=self.kibana_headers,
            data=json.dumps({
                'attributes': attribs
            })
        ).raise_for_status()

    def bulk_index(self, index_name, data):
        if not self.index_exists(index_name, print_error=False):
            self.create_index(index_name)

        bulk_actions = [{
            '_id': "%s_%s" % (row["project_id"], row["gather_date"]),
            '_index': index_name,
            '_type': "default",
            '_source': row,
        } for row in data]

        logger.debug('Indexing %d docs...' % len(bulk_actions))
        success_count, errors = elasticsearch.helpers.bulk(self.es_client,
                                                           bulk_actions,
                                                           chunk_size=1000,
                                                           request_timeout=30,
                                                           refresh=True)

        logger.debug("Processed %d logs", success_count)
        if errors:
            logger.debug("Occured errors %s", errors)

        self.create_pattern(pattern_id=index_name, time_field="gather_date")
