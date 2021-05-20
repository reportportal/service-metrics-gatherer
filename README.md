# service-metrics-gatherer

# Environment variables for configuration

**ES_HOST** - Elasticsearch host (can be either like this "http://elasticsearch:9200", or with login and password delimited by : and separated from the host name by @)

**ES_USER** - Elasticsearch host login, set up here the username for elasticsearch, if you choose setup username here, in the **ES_HOST** you should leave only url without login and password

**ES_PASSWORD** - Elasticsearch host password, set up here the password for elasticsearch, if you choose setup the password here, in the **ES_HOST** you should leave only url without login and password

**AMQP_URL** - an url to the rabbitmq instance

**AMQP_EXCHANGE_NAME** - Exchange name for the module communication for this module, by default "analyzer"

**LOGGING_LEVEL** - logging level for the whole module, can be DEBUG, INFO, ERROR

**GRAFANA_HOST** - an url to the Grafana instance. **NOTE** if you don't want to see dashboards in Grafana, leave this environment variable empty.

**ES_HOST_GRAFANA_DATASOURCE** - an url to the Elasticsearch instance, which is accessible from Grafana image, and this url will be used for creating datasources for Grafana

**POSTGRES_USER** - postgres username to access the postgres database

**POSTGRES_PASSWORD**  - postgres password to access the postgres database

**POSTGRES_DB** - the name of postgres database

**POSTGRES_HOST** - the host of postgres database location

**POSTGRES_PORT** - the port of postgres database location

**ALLOWED_START_TIME** - allowed start time for gathering metrics, default "22:00"

**ALLOWED_END_TIME** - allowed end time for gathering metrics, default "08:00"

**MAX_DAYS_STORE** - max days to store metrics, the metrics gatherer will delete data points which earlier than max days to store from today, default 500

**TZ** - time zone, it will let better understand allowed start and end time. default "Europe/Minsk"

**TIME_INTERVAL** - time intervsl for calculating metrics, available options "hour", "minute", "day"

**ES_VERIFY_CERTS** - turn on SSL certificates verification, by default "false"

**ES_USE_SSL** - turn on SSL, by default "false"

**ES_SSL_SHOW_WARN** - show warning on SSL certificates verification, by default "false"

**ES_CA_CERT** - provide a path to CA certs on disk, by default ""

**ES_CLIENT_CERT** - PEM formatted SSL client certificate, by default ""

**ES_CLIENT_KEY** - PEM formatted SSL client key, by default ""

**ES_TURN_OFF_SSL_VERIFICATION** - by default "false". Turn off ssl verification via using RequestsHttpConnection class instead of Urllib3HttpConnection class.

**ES_PROJECT_INDEX_PREFIX** - by default "", the prefix which is added to the created for each project indices. Our index name is the project id, so if it is 34, then the index "34" will be created. If you set ES_PROJECT_INDEX_PREFIX="rp_", then "rp_34" index will be created. We create several other indices which are sharable between projects, and this perfix won't influence them: rp_aa_stats, rp_stats, rp_model_train_stats, rp_done_tasks, rp_suggestions_info_metrics. **NOTE**: This prefix should be the same as for service-auto-analyzer image, this will ensure we check the same indices.

**AUTO_ANALYSIS_MODEL_REMOVE_POLICY** - by default "f1-score<=80|percent_not_found_aa>70", the conditions for removing custom auto-analysis models, so that they were retrained. The conditions are checked and applied if at least one condition is satisfied. The available metrics: f1-score, accuracy, percent_not_found_aa. The available comparison operators: >=, <=, <, >, =, ==.

**SUGGEST_MODEL_REMOVE_POLICY** - by default "reciprocalRank<=80|notFoundResults>70", the conditions for removing custom suggestion models, so that they were retrained. The conditions are checked and applied if at least one condition is satisfied. The available metrics: reciprocalRank, notFoundResults. The available comparison operators: >=, <=, <, >, =, ==.

# Instructions for analyzer setup without Docker

Install python with the version 3.7.4. (it is the version on which the service was developed, but it should work on the versions starting from 3.6).

Perform next steps inside source directory of the analyzer.

## For Linux:
1. Create a virtual environment with any name (in the example **/venv**)
```Shell
  python -m venv /venv
```
2. Install python libraries
```
  /venv/bin/pip install --no-cache-dir -r requirements.txt
```
3. Activate the virtual environment
```
  /venv/bin/activate
```
4. Start the uwsgi server, you can change properties, such as the workers quantity for running the metrics gatherer in the several processes
```
  /venv/bin/uwsgi -workers 1 --socket :3031 --wsgi-file main.py --master --http :5000 --threads 1 --lazy-apps 1 --wsgi-env-behavior holy --virtualenv /venv
  ```
 
## For Windows:
1. Create a virtual environment with any name (in the example **env**)
```
python -m venv env
```
2. Activate the virtual environment
```
call env\Scripts\activate.bat
```
3. Install python libraries
```
python -m pip install -r requirements_windows.txt
```
4. Start the program.
```
python main.py
```

