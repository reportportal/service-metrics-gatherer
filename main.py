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
import logging.config
import os
from commons import postgres_dao

APP_CONFIG = {
    "esHost":            os.getenv("ES_HOST", "http://elasticsearch:9201"),
    "logLevel":          os.getenv("LOGGING_LEVEL", "DEBUG"),
    "postgresUser":      os.getenv("POSTGRES_USER", ""),
    "postgresPassword":  os.getenv("POSTGRES_PASSWORD", ""),
    "postgresDatabase":  os.getenv("POSTGRES_DB", "reportportal"),
    "postgresHost":      os.getenv("POSTGRES_HOST", "localhost"),
    "postgresPort":      os.getenv("POSTGRES_PORT", 5432)
}


def initialize_connection():
    logger.info("Application started...")
    _postgres_dao = postgres_dao.PostgresDAO(APP_CONFIG)
    print(_postgres_dao.get_auto_analysis_attribute_id())


log_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logging.conf')
logging.config.fileConfig(log_file_path)
if APP_CONFIG["logLevel"].lower() == "debug":
    logging.disable(logging.NOTSET)
elif APP_CONFIG["logLevel"].lower() == "info":
    logging.disable(logging.DEBUG)
else:
    logging.disable(logging.INFO)
logger = logging.getLogger("metricsGatherer")
initialize_connection()
