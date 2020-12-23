# service-metrics-gatherer

# Environment variables for configuration

**ES_HOST** - Elasticsearch host (can be either like this "http://elasticsearch:9200", or with login and password delimited by : and separated from the host name by @)

**LOGGING_LEVEL** - logging level for the whole module, can be DEBUG, INFO, ERROR

**GRAFANA_HOST** - an url to the Grafana instance

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

