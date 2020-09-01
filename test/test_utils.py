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
from utils import utils
import datetime
from freezegun import freeze_time


class TestUtils(unittest.TestCase):

    def setUp(self):
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.DEBUG)

    def test_take_the_date_to_check_yesterday(self):
        with freeze_time(datetime.datetime(2020, 10, 15, 7, 20)):
            assert utils.take_the_date_to_check() == datetime.datetime(2020, 10, 14, 7, 20)

    def test_take_the_date_to_check_today(self):
        with freeze_time(datetime.datetime(2020, 10, 15, 15, 34)):
            assert utils.take_the_date_to_check() == datetime.datetime(2020, 10, 15, 15, 34)

    def test_start_time_begin(self):
        with freeze_time(datetime.datetime(2020, 10, 15, 23, 34)):
            assert utils.is_the_time_for_task_starting("22:00", "08:00") is True

    def test_start_time_not_begin(self):
        with freeze_time(datetime.datetime(2020, 10, 15, 14, 22)):
            assert utils.is_the_time_for_task_starting("22:00", "08:00") is False

    def test_start_time_begin_range_day(self):
        with freeze_time(datetime.datetime(2020, 10, 15, 14, 22)):
            assert utils.is_the_time_for_task_starting("12:00", "16:00") is True

    def test_start_time_not_begin_range_day(self):
        with freeze_time(datetime.datetime(2020, 10, 16, 16, 22)):
            assert utils.is_the_time_for_task_starting("12:00", "16:00") is False
