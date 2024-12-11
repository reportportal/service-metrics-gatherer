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
import logging.config
import os
import threading
import time

import schedule
from flask import Flask, Response
from flask import jsonify
from flask_cors import CORS

from app.commons import metrics_gatherer, es_client
from app.commons import postgres_dao, amqp
from app.utils import utils, text_processing

APP_CONFIG = {
    "esHost": os.getenv("ES_HOSTS", "http://localhost:9200").strip("/").strip("\\"),
    "esUser": os.getenv("ES_USER", "").strip(),
    "esPassword": os.getenv("ES_PASSWORD", "").strip(),
    "grafanaHost": os.getenv("GRAFANA_HOST", "").strip("/").strip("\\"),
    "esHostGrafanaDataSource": os.getenv(
        "ES_HOST_GRAFANA_DATASOURCE", "http://localhost:9200").strip("/").strip("\\"),
    "logLevel": os.getenv("LOGGING_LEVEL", "DEBUG"),
    "postgresUser": os.getenv("POSTGRES_USER", ""),
    "postgresPassword": os.getenv("POSTGRES_PASSWORD", ""),
    "postgresDatabase": os.getenv("POSTGRES_DB", "reportportal"),
    "postgresHost": os.getenv("POSTGRES_HOST", "localhost"),
    "postgresPort": os.getenv("POSTGRES_PORT", 5432),
    "allowedStartTime": os.getenv("ALLOWED_START_TIME", "22:00"),
    "allowedEndTime": os.getenv("ALLOWED_END_TIME", "08:00"),
    "maxDaysStore": os.getenv("MAX_DAYS_STORE", "500"),
    "timeInterval": os.getenv("TIME_INTERVAL", "hour").lower(),
    "turnOffSslVerification": json.loads(os.getenv("ES_TURN_OFF_SSL_VERIFICATION", "false").lower()),
    "esVerifyCerts": json.loads(os.getenv("ES_VERIFY_CERTS", "false").lower()),
    "esUseSsl": json.loads(os.getenv("ES_USE_SSL", "false").lower()),
    "esSslShowWarn": json.loads(os.getenv("ES_SSL_SHOW_WARN", "false").lower()),
    "esCAcert": os.getenv("ES_CA_CERT", ""),
    "esClientCert": os.getenv("ES_CLIENT_CERT", ""),
    "esClientKey": os.getenv("ES_CLIENT_KEY", ""),
    "esProjectIndexPrefix": os.getenv("ES_PROJECT_INDEX_PREFIX", "").strip(),
    "amqpUrl": os.getenv("AMQP_URL", "").strip("/").strip("\\") + "/" + os.getenv(
        "AMQP_VIRTUAL_HOST", "analyzer"),
    "exchangeName": os.getenv("AMQP_EXCHANGE_NAME", "analyzer"),
    "analyzerPriority": int(os.getenv("ANALYZER_PRIORITY", "1")),
    "analyzerIndex": json.loads(os.getenv("ANALYZER_INDEX", "true").lower()),
    "analyzerLogSearch": json.loads(os.getenv("ANALYZER_LOG_SEARCH", "true").lower()),
    "autoAnalysisModelRemovePolicy": os.getenv(
        "AUTO_ANALYSIS_MODEL_REMOVE_POLICY", "f1-score<=80|percent_not_found_aa>70"),
    "suggestModelRemovePolicy": os.getenv(
        "SUGGEST_MODEL_REMOVE_POLICY", "reciprocalRank<=80|notFoundResults>70"),
    "metricsHttpPort": int(os.getenv("METRICS_HTTP_PORT", 5000)),
    "metricsPathToLog": os.getenv("METRICS_FILE_LOGGING_PATH", "/tmp/metrics_config.log")
}


def create_application():
    """Creates a Flask application"""
    _application = Flask(__name__)
    return _application


def start_metrics_gathering():
    _es_client = es_client.EsClient(
        esHost=APP_CONFIG["esHost"], grafanaHost=APP_CONFIG["grafanaHost"], app_config=APP_CONFIG)
    if not utils.is_the_time_for_task_starting(APP_CONFIG["allowedStartTime"],
                                               APP_CONFIG["allowedEndTime"]):
        logger.debug("Starting of tasks is allowed only from %s to %s. Now is %s",
                     APP_CONFIG["allowedStartTime"],
                     APP_CONFIG["allowedEndTime"],
                     datetime.datetime.now())
        return
    date_to_check = utils.take_the_date_to_check()
    if not _es_client.is_the_date_metrics_calculated(date_to_check):
        logger.debug("Task started...")
        _metrics = metrics_gatherer.MetricsGatherer(APP_CONFIG)
        _metrics.gather_metrics(date_to_check,
                                date_to_check)
        _es_client.delete_old_info(APP_CONFIG["maxDaysStore"])
        _es_client.bulk_index(_es_client.task_done_index, [{
            '_index': _es_client.task_done_index,
            '_source': {
                "gather_date": date_to_check.date(),
                "started_task_time": datetime.datetime.now()
            }
        }])
        logger.debug("Task finished...")
    else:
        logger.debug("Task for today was already completed...")


log_file_path = 'res/logging.conf'
logging.config.fileConfig(log_file_path, defaults={'logfilename': APP_CONFIG["metricsPathToLog"]})
if APP_CONFIG["logLevel"].lower() == "debug":
    logging.disable(logging.NOTSET)
elif APP_CONFIG["logLevel"].lower() == "info":
    logging.disable(logging.DEBUG)
else:
    logging.disable(logging.INFO)
logger = logging.getLogger("metricsGatherer")

application = create_application()
CORS(application)

while True:
    try:
        if not APP_CONFIG["grafanaHost"].strip():
            break
        _es_client = es_client.EsClient(
            esHost=APP_CONFIG["esHost"], grafanaHost=APP_CONFIG["grafanaHost"], app_config=APP_CONFIG)
        data_source_created = []
        for index in [_es_client.main_index, _es_client.rp_aa_stats_index,
                      _es_client.rp_model_train_stats_index, _es_client.rp_suggest_metrics_index,
                      _es_client.rp_model_remove_stats_index]:
            date_field = "gather_date"
            if index == _es_client.rp_suggest_metrics_index:
                date_field = "savedDate"
            data_source_created.append(int(_es_client.create_grafana_data_source(
                APP_CONFIG["esHostGrafanaDataSource"], index, date_field)))
        if sum(data_source_created) == len(data_source_created):
            for dashboard_id in ["X-WoMD5Mz", "7po7Ga1Gz", "OM3Zn8EMz"]:
                _es_client.import_dashboard(dashboard_id)
                logger.info("Imported dashboard '%s' into Grafana %s" % (
                    dashboard_id, text_processing.remove_credentials_from_url(
                        APP_CONFIG["grafanaHost"])))
            break
    except Exception as e:
        logger.error(e)
        logger.error("Can't import dashboard into Grafana %s" % text_processing.remove_credentials_from_url(
            APP_CONFIG["grafanaHost"]))
        time.sleep(10)


@application.route('/', methods=['GET'])
def get_health_status():
    _es_client = es_client.EsClient(
        esHost=APP_CONFIG["esHost"], grafanaHost=APP_CONFIG["grafanaHost"], app_config=APP_CONFIG)
    _postgres_dao = postgres_dao.PostgresDAO(APP_CONFIG)

    status = ""
    if not _es_client.is_healthy():
        status += "Elasticsearch is not healthy;"
    if APP_CONFIG["grafanaHost"].strip() and not _es_client.is_grafana_healthy():
        status += "Grafana is not healthy;"
    if not _postgres_dao.test_query_handling():
        status += "Postgres is not healthy;"
    if APP_CONFIG["amqpUrl"].strip():
        try:
            _ = amqp.AmqpClient(APP_CONFIG)
        except Exception as err:
            logger.error(err)
            status += "Connection to Rabbitmq is not healthy;"
    if status:
        logger.error("Metrics gatherer health check status failed: %s", status)
        return Response(json.dumps({"status": status}), status=503, mimetype='application/json')
    return jsonify({"status": "healthy"})


def create_thread(func, args):
    """Creates a thread with specified function and arguments"""
    thread = threading.Thread(target=func, args=args)
    thread.start()
    return thread


def scheduling_tasks():
    logger.info("Started scheduling of metrics gathering...")
    allowed_intervals = {
        "hour": schedule.every().hour.do,
        "minute": schedule.every().minute.do,
        "day": schedule.every().day.at(APP_CONFIG["allowedStartTime"]).do
    }
    time_interval = "hour"
    if APP_CONFIG["timeInterval"] in allowed_intervals:
        time_interval = APP_CONFIG["timeInterval"]
    allowed_intervals[time_interval](start_metrics_gathering)
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except Exception as e:
        logger.error(e)
        logger.error("Metrics gatherer has finished with errors")
        os.kill(os.getpid(), 9)


def start_http_server():
    application.run(host='0.0.0.0', port=APP_CONFIG["metricsHttpPort"])


create_thread(scheduling_tasks, ())

if __name__ == '__main__':
    logger.info("Program started")

    start_http_server()

    logger.info("The metrics gatherer has finished")
    exit(0)
