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
import psycopg2
import re

logger = logging.getLogger("metricsGatherer.postgres_dao")


class PostgresDAO:

    def __init__(self, app_settings):
        self.app_settings = app_settings
        self.auto_analysis_attribute_id = self.get_auto_analysis_attribute_id()

    def transform_to_objects(self, query, results):
        try:
            transformed_results = []
            columns = [col.strip() for col in re.search(
                "select (.*) from", query, flags=re.IGNORECASE).group(1).split(",")]
            for r in results:
                obj = {}
                for idx, column in enumerate(columns):
                    obj[column] = r[idx]
                transformed_results.append(obj)
            return transformed_results
        except Exception as e:
            logger.error("Didn't derive columns from query")
            logger.error(e)
            return results

    def query_db(self, query, query_all=True, derive_scheme=True):
        connection = None
        try:
            connection = psycopg2.connect(user=self.app_settings["postgresUser"],
                                          password=self.app_settings["postgresPassword"],
                                          host=self.app_settings["postgresHost"],
                                          port=self.app_settings["postgresPort"],
                                          database=self.app_settings["postgresDatabase"])

            cursor = connection.cursor()
            cursor.execute(query)
            results = cursor.fetchall()
            results = self.transform_to_objects(query, results) if derive_scheme else results
            return results if query_all else results[0]
        except (Exception, psycopg2.Error) as error:
            logger.error("Error while connecting to PostgreSQL %s", error)
        finally:
            if(connection):
                cursor.close()
                connection.close()

    def test_query_handling(self):
        connection = None
        result = True
        try:
            connection = psycopg2.connect(user=self.app_settings["postgresUser"],
                                          password=self.app_settings["postgresPassword"],
                                          host=self.app_settings["postgresHost"],
                                          port=self.app_settings["postgresPort"],
                                          database=self.app_settings["postgresDatabase"])

            cursor = connection.cursor()
            cursor.execute("select * from information_schema.columns")
            result = cursor.fetchone() is not None
        except (Exception, psycopg2.Error) as error:
            logger.error("Error while connecting to PostgreSQL %s", error)
            result = False
        finally:
            if(connection):
                cursor.close()
                connection.close()
        return result

    def get_column_names_for_table(self, table_name):
        return self.query_db(
            """select column_name, data_type from
            information_schema.columns where table_name = '%s';""" % table_name)

    def get_auto_analysis_attribute_id(self):
        result = self.query_db(
            """select id, name from attribute
            where name = 'analyzer.isAutoAnalyzerEnabled'""", query_all=False)
        if result:
            return result["id"]
        return -1

    def is_auto_analysis_enabled_for_project(self, project_id):
        return self.query_db(
            "select value from project_attribute where project_id = %d and attribute_id = %d" % (
                project_id, self.auto_analysis_attribute_id), query_all=False)["value"].lower() == "true"

    def get_launch_id(self, item_id):
        return self.query_db(
            "select launch_id from test_item where item_id=%d" % item_id, query_all=False)["launch_id"]

    def get_activities_by_project(self, project_id, start_date, end_date):
        return self.query_db(
            """select entity, action, details, object_id, creation_date from activity
            where project_id=%d and creation_date >= '%s'::timestamp and
            creation_date <= '%s'::timestamp order by creation_date""" % (
                project_id, start_date, end_date))

    def get_all_projects(self):
        return self.query_db("select id, name from project")

    def get_all_unique_launch_ids(self, project_id, start_date, end_date):
        all_ids = self.query_db(
            """select id from launch
            where project_id=%d and start_time >= '%s'::timestamp and
            start_time <= '%s'::timestamp""" % (
                project_id, start_date, end_date))
        return list(set([obj["id"] for obj in all_ids]))
