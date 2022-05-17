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

import uuid
import json
import pika
import logging
import time

logger = logging.getLogger("metricsGatherer.amqpClient")


class AmqpClient:

    def __init__(self, app_config):
        self.app_config = app_config
        amqp_full_url = app_config["amqpUrl"].rstrip("\\").rstrip("/") + "?heartbeat=600"
        self.connection = pika.BlockingConnection(pika.connection.URLParameters(amqp_full_url))
        self.response = None
        self.corr_id = None

        self.channel = self.connection.channel()

        result = self.channel.queue_declare(queue='', exclusive=True)
        self.callback_queue = result.method.queue

        self.channel.basic_consume(
            queue=self.callback_queue,
            on_message_callback=lambda channel, method, props, body: self._on_response(props, body),
            auto_ack=True)

    def _on_response(self, props, body):
        if self.corr_id == props.correlation_id:
            self.response = body

    def call(self, message, method, timeout=120):
        self.response = None
        self.corr_id = str(uuid.uuid4())
        self.channel.basic_publish(
            exchange=self.app_config["exchangeName"],
            routing_key=method,
            properties=pika.BasicProperties(
                reply_to=self.callback_queue,
                correlation_id=self.corr_id,
            ),
            body=message)

        start_time = time.time()
        while self.response is None:
            if (start_time + timeout) < time.time():
                raise Exception("Rabbitmq timeout exception")
            self.connection.process_data_events()
        return json.loads(self.response, strict=False)

    def close_connections(self):
        try:
            self.channel.close()
            self.connection.close()
        except Exception as err:
            logger.error(err)
