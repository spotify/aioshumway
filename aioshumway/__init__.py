# -*- coding: utf-8 -*-
#
# Copyright 2018 Spotify AB
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Wrapper around shumway (https://github.com/spotify/shumway) that
uses asyncio features to make all IO operations non-blocking and compatible
with the async/await syntax.
"""

__author__ = 'Matt Obarzanek'
__version__ = '1.0.0'
__license__ = 'Apache 2.0'
__email__ = 'matto@spotify.com'
__description__ = 'Asynchronous metrics library for ffwd'
__uri__ = 'https://github.com/spotify/aioshumway'

import asyncio
import json
import logging

import shumway


FFWD_IP = shumway.FFWD_IP
FFWD_PORT = shumway.FFWD_PORT
GIGA_UNIT = shumway.GIGA_UNIT

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class FFWDClientProtocol(asyncio.DatagramProtocol):
    """Protocol for sending one-off messages to FFWD.

    Args:
        message (bytes): Message for FFWD agent.
    """
    def __init__(self, message):
        self.message = message
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport
        self.transport.sendto(self.message)
        self.transport.close()

    def error_received(self, exc):
        logger.warning(f'Error when sending metric: {exc}\n'
                       f'Metric value: {self.message}')


class Meter(shumway.Meter):
    """A single metric with updateable value."""
    async def flush(self, coro):
        """Pass map of data to coro for processing."""
        await coro({
            'key': self.key,
            'attributes': self._attributes,
            'value': self.value,
            'type': 'metric',
            'tags': self._tags
        })


class Counter(Meter, shumway.Counter):
    """Keep track of an incrementing metric."""
    pass


class Timer(Meter, shumway.Timer):
    """Time the execution of a block of code."""


class MetricRelay(shumway.MetricRelay):
    """Manage creating and sending metrics to FFWD.

    Args:
        default_key (str): Key assigned to each metric.
        ffwd_ip (str): IP address of FFWD agent.
        ffwd_port (int): Port that FFWD agents listens on.
        loop (obj): an asyncio.AbstractEventLoop-compatible event loop.
    """

    def __init__(self, default_key, ffwd_ip=FFWD_IP, ffwd_port=FFWD_PORT,
                 loop=None):
        super().__init__(default_key, ffwd_ip, ffwd_port)
        if loop is None:
            loop = asyncio.get_event_loop()
        self.loop = loop

    async def emit(self, metric, value, attributes=None, tags=None):
        """Emit a single metric.

        Args:
            metric (str): Name of metric.
            value (int/float): Value of metric.
            attributes (dict): Additional attributes attached to metric.
            tags (dict): Additional tags attached to metric.
        """
        one_time_metric = Meter(metric, key=self._default_key, value=value,
                                attributes=attributes, tags=tags)
        await self.flush_single(one_time_metric)

    def incr(self, metric, value=1):
        """Increment a metric. Create it if it does not exist.

        Args:
            metic (str): Name of metric.
            value (int/float): Amount to increment the metric by.
        """
        try:
            counter = self._metrics[metric]
        except KeyError:
            counter = Counter(metric, key=self._default_key)
            self._metrics[metric] = counter
        counter.incr(value)

    def timer(self, metric):
        """Retrieve or create a Timer metric.

        Args:
            metric (str): Name of metric.
        """
        timer_metric = f'timer-{metric}'
        try:
            timer = self._metrics[timer_metric]
        except KeyError:
            timer = Timer(metric, key=self._default_key)
            self._metrics[timer_metric] = timer
        return timer

    async def flush(self):
        """Send out all stored metrics to the FFWD agent."""
        for metric in self._metrics.values():
            await self.flush_single(metric)

    async def flush_single(self, metric):
        """Send out a single metric to the FFWD agent."""
        await metric.flush(self._sendto)

    async def _sendto(self, metric):
        message = json.dumps(metric).encode('utf-8')
        await self.loop.create_datagram_endpoint(
            lambda: FFWDClientProtocol(message),
            remote_addr=self._ffwd_address)
