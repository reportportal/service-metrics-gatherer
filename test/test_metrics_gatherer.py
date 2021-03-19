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

import unittest
import logging
import sure # noqa
from commons import metrics_gatherer
from datetime import datetime, date, timedelta
from unittest.mock import MagicMock


class TestMetricsGatherer(unittest.TestCase):

    def setUp(self):
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.DEBUG)

    def test_derive_item_activity_chain(self):
        _metrics_gatherer = metrics_gatherer.MetricsGatherer(
            {"esHost": "localhost:9200", "grafanaHost": "localhost:3000"})
        assert _metrics_gatherer.derive_item_activity_chain([
            {
                "object_id": 1,
                "action": "analyzeItem",
                "details": {
                    "history": [
                        {"field": "issueType", "oldValue": "To Investigate", "newValue": "Product Bug"}]}
            },
            {
                "object_id": 1,
                "action": "updateItem",
                "details": {
                    "history": [
                        {"field": "issueType", "oldValue": "Product Bug", "newValue": "Automation Bug"}]}
            },
            {
                "object_id": 2,
                "action": "updateItem",
                "details": {
                    "history": [
                        {"field": "issueType", "oldValue": "Automation Bug", "newValue": "System Issue"}]}
            }]) == {
                1: [('analyze', 'Product Bug'), ('manual', 'Automation Bug', 'Product Bug')],
                2: [('manual', 'System Issue', 'Automation Bug')]}

    def test_calculate_rp_stats_metrics(self):
        _metrics_gatherer = metrics_gatherer.MetricsGatherer(
            {"esHost": "localhost:9200", "grafanaHost": "localhost:3000"})
        _metrics_gatherer.es_client.get_activities = MagicMock(
            return_value=[
                {"_source": {
                    "method": "auto_analysis",
                    "items_to_process": 10,
                    "not_found": 1,
                    "launch_id": 123,
                    "processed_time": 0.8,
                    "model_info": ["global_model"],
                    "module_version": ["1.1.1"]
                }},
                {"_source": {
                    "method": "suggest",
                    "items_to_process": 12,
                    "not_found": 3,
                    "launch_id": 123,
                    "processed_time": 0.9,
                    "model_info": ["global_model"],
                    "module_version": ["1.1.1"]
                }},
                {"_source": {
                    "method": "suggest",
                    "items_to_process": 5,
                    "not_found": 8,
                    "launch_id": 125,
                    "processed_time": 0.4,
                    "model_info": ["global_model"],
                    "module_version": ["1.1.1"]
                }},
                {"_source": {
                    "method": "find_clusters",
                    "items_to_process": 6,
                    "not_found": 1,
                    "launch_id": 126,
                    "processed_time": 0.8,
                    "model_info": ["global_model"],
                    "module_version": ["1.1.1"]
                }},
            ])
        assert _metrics_gatherer.calculate_rp_stats_metrics({}, 1, datetime(2020, 10, 13)) == {
            'percent_not_found_aa': 10, 'avg_processing_time_only_found_test_item_aa': 0.09,
            'avg_processing_time_test_item_aa': 0.08, 'percent_not_found_suggest': 92,
            'avg_processing_time_test_item_suggest': 0.08, 'percent_not_found_cluster': 17,
            'avg_processing_time_test_item_cluster': 0.13, 'model_info': ['global_model'],
            'module_version': ['1.1.1'], "launch_analyzed": 1}

    def test_calculate_metrics(self):
        _metrics_gatherer = metrics_gatherer.MetricsGatherer(
            {"esHost": "localhost:9200", "grafanaHost": "localhost:3000"})
        _metrics_gatherer.postgres_dao.get_launch_id = MagicMock(return_value=10)
        assert _metrics_gatherer.calculate_metrics(
            {
                1: [('analyze', 'Product Bug'), ('manual', 'Automation Bug', 'Product Bug')],
                2: [('manual', 'System Issue', 'Automation Bug'), ('analyze', 'Product Bug')]
            },
            {'launch_analyzed': 0}) == {
                'AA_analyzed': 2, 'changed_type': 1, 'launch_analyzed': 1,
                'manually_analyzed': 0, 'accuracy': 50, 'f1-score': 33}
        assert _metrics_gatherer.calculate_metrics(
            {
                1: [('analyze', 'Product Bug'), ('manual', 'Automation Bug', 'Product Bug')],
                2: [('manual', 'System Issue', 'Automation Bug'), ('analyze', 'Product Bug')]
            },
            {'launch_analyzed': 5}) == {
                'AA_analyzed': 2, 'changed_type': 1, 'launch_analyzed': 5,
                'manually_analyzed': 0, 'accuracy': 50, 'f1-score': 33}

    def test_find_sequence_of_aa_enability(self):
        _metrics_gatherer = metrics_gatherer.MetricsGatherer(
            {"esHost": "localhost:9200", "grafanaHost": "localhost:3000"})
        _metrics_gatherer.postgres_dao.get_activities_by_project = MagicMock(return_value=[
            {
                "creation_date": datetime(2020, 10, 11),
                "action": "updateAnalyzer",
                "details": {
                    "history": [
                        {"field": "analyzer.isAutoAnalyzerEnabled", "oldValue": "true", "newValue": "false"}]}
            },
            {
                "creation_date": datetime(2020, 10, 14),
                "action": "updateAnalyzer",
                "details": {
                    "history": [
                        {"field": "analyzer.isAutoAnalyzerEnabled", "oldValue": "false", "newValue": "true"}]}
            },
            {
                "creation_date": datetime(2020, 10, 14),
                "action": "updateAnalyzer",
                "details": {
                    "history": [
                        {"field": "analyzer.isAutoAnalyzerEnabled", "oldValue": "true", "newValue": "false"}]}
            },
            {
                "creation_date": datetime(2020, 10, 15),
                "action": "updateAnalyzer",
                "details": {
                    "history": [
                        {"field": "analyzer.isAutoAnalyzerEnabled", "oldValue": "false", "newValue": "true"}]}
            }])
        assert _metrics_gatherer.find_sequence_of_aa_enability(1, datetime(2020, 10, 16), {}) == {
            date(2020, 10, 11): (0, 0), date(2020, 10, 14): (1, 0),
            date(2020, 10, 15): (1, 1)}

    def test_fill_right_aa_enable_states(self):
        _metrics_gatherer = metrics_gatherer.MetricsGatherer(
            {"esHost": "localhost:9200", "grafanaHost": "localhost:3000"})
        _metrics_gatherer.fill_right_aa_enable_states([
            {"gather_date": date(2020, 10, 10) + timedelta(days=i), "on": 0} for i in range(7)],
            {date(2020, 10, 11): (0, 0), date(2020, 10, 14): (1, 0), date(2020, 10, 15): (1, 1)}) == [
            {'gather_date': date(2020, 10, 10), 'on': 1},
            {'gather_date': date(2020, 10, 11), 'on': 0},
            {'gather_date': date(2020, 10, 12), 'on': 0},
            {'gather_date': date(2020, 10, 13), 'on': 0},
            {'gather_date': date(2020, 10, 14), 'on': 0},
            {'gather_date': date(2020, 10, 15), 'on': 1},
            {'gather_date': date(2020, 10, 16), 'on': 0}]
