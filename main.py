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
from commons import metrics_gatherer
import datetime
from flask import Flask
from flask_cors import CORS

APP_CONFIG = {
    "esHost":            os.getenv("ES_HOST", "http://localhost:9202"),
    "kibanaHost":        os.getenv("KIBANA_HOST", "http://localhost:5602"),
    "logLevel":          os.getenv("LOGGING_LEVEL", "DEBUG"),
    "postgresUser":      os.getenv("POSTGRES_USER", ""),
    "postgresPassword":  os.getenv("POSTGRES_PASSWORD", ""),
    "postgresDatabase":  os.getenv("POSTGRES_DB", "reportportal"),
    "postgresHost":      os.getenv("POSTGRES_HOST", "localhost"),
    "postgresPort":      os.getenv("POSTGRES_PORT", 5432)
}


def create_application():
    """Creates a Flask application"""
    _application = Flask(__name__)
    return _application


def initialize_connection():
    logger.info("Application started...")
    _metrics = metrics_gatherer.MetricsGatherer(APP_CONFIG)
    print(_metrics.gather_metrics(datetime.datetime(2020, 8, 1),
          datetime.datetime(2020, 8, 10)))


log_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logging.conf')
logging.config.fileConfig(log_file_path)
if APP_CONFIG["logLevel"].lower() == "debug":
    logging.disable(logging.NOTSET)
elif APP_CONFIG["logLevel"].lower() == "info":
    logging.disable(logging.DEBUG)
else:
    logging.disable(logging.INFO)
logger = logging.getLogger("metricsGatherer")

application = create_application()
CORS(application)
initialize_connection()
logger.info("The metrics gatherer has finished")
exit(0)
