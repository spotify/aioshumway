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

import asyncio
import json

import pytest

import aioshumway


@pytest.fixture
def transport(mocker):
    return mocker.Mock(asyncio.transports.DatagramTransport)


class TestFFWDClientProtocol:
    def test_protocol_sends_msg_on_connect(self, transport):
        msg = 'message'.encode('utf-8')
        proto = aioshumway.FFWDClientProtocol(msg)
        proto.connection_made(transport)

        transport.sendto.assert_called_once_with(msg)

    def test_protocol_closes_transport_after_sending_msg(self, transport):
        msg = 'message'.encode('utf-8')
        proto = aioshumway.FFWDClientProtocol(msg)
        proto.connection_made(transport)

        transport.close.assert_called_once_with()

    def test_protocol_logs_exc(self, mocker):
        logger = mocker.Mock()
        mocker.patch.object(aioshumway, 'logger', new=logger)
        proto = aioshumway.FFWDClientProtocol(b'')
        proto.error_received(Exception('UDP error'))

        logger.warning.assert_called_once_with(
            'Error when sending metric: UDP error\nMetric value: b\'\'')


@pytest.fixture
def coro_tester(mocker):
    mock = mocker.Mock()

    async def _test_coro(*args, **kwargs):
        mock(*args, **kwargs)

    return mock, _test_coro


class TestMeter:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        'Meter',
        [aioshumway.Meter, aioshumway.Counter, aioshumway.Timer])
    async def test_aiometers_flush_awaits_coro(self, coro_tester, Meter):
        coro_mock, dummy_coro = coro_tester

        meter = Meter('dummy-what', 'dummy-key')
        await meter.flush(dummy_coro)

        coro_mock.assert_called_once_with({
            'key': meter.key,
            'attributes': meter._attributes,
            'value': meter.value,
            'type': 'metric',
            'tags': meter._tags
        })


@pytest.fixture
def aiometric_relay():
    return aioshumway.MetricRelay('dummy-key', '127.0.0.1', 1000)


class TestMetricRelay:
    @pytest.mark.asyncio
    async def test_relay_uses_provided_event_loop(self, event_loop):
        aiomr = aioshumway.MetricRelay('dummy-key', '127.0.0.1', '1000',
                                       event_loop)
        assert aiomr.loop is event_loop

    @pytest.mark.asyncio
    async def test_relay_gets_its_own_event_loop(self, event_loop):
        aiomr = aioshumway.MetricRelay('dummy-key', '127.0.0.1', '1000')
        assert aiomr.loop is event_loop

    @pytest.mark.asyncio
    async def test_emit_flushes_one_metric(self, mocker, aiometric_relay,
                                           coro_tester):
        coro_mock, dummy_coro = coro_tester
        mocker.patch.object(aiometric_relay, '_sendto', dummy_coro)

        await aiometric_relay.emit('some-metric', 127,
                                   attributes={'internal': True},
                                   tags={'tag1': 256})

        coro_mock.assert_called_once_with({
            'key': 'dummy-key',
            'attributes': {'what': 'some-metric', 'internal': True},
            'value': 127,
            'type': 'metric',
            'tags': {'tag1': 256}
        })

    def test_incr_existing_metric(self, mocker, aiometric_relay):
        counter = mocker.Mock()
        aiometric_relay._metrics['counter1'] = counter

        aiometric_relay.incr('counter1')

        counter.incr.assert_called_once_with(1)

    def test_incr_new_metric(self, mocker, aiometric_relay):
        counter = mocker.Mock()
        mocker.patch.object(
            aioshumway, 'Counter', mocker.Mock(return_value=counter))
        aiometric_relay.incr('counter1')
        counter.incr.assert_called_once_with(1)

    def test_timer_existing_metric(self, mocker, aiometric_relay):
        timer = mocker.Mock()
        aiometric_relay._metrics['timer-timer1'] = timer

        existing_timer = aiometric_relay.timer('timer1')

        assert existing_timer == timer

    def test_timer_new_metric(self, mocker, aiometric_relay):
        timer = mocker.Mock()
        mocker.patch.object(
            aioshumway, 'Timer', mocker.Mock(return_value=timer))

        existing_timer = aiometric_relay.timer('timer1')

        assert existing_timer == timer

    def test_timer_context_man_compatible(self, mocker, aiometric_relay):
        update_method = mocker.Mock()
        timer = aiometric_relay.timer('test-metric')
        mocker.patch.object(timer, 'update', update_method)
        with timer:
            pass
        assert timer._start is not None
        assert isinstance(update_method.call_args[0][0], float)

    @pytest.mark.asyncio
    async def test_flush_flushes_all_metrics(self, mocker, aiometric_relay,
                                             coro_tester):
        coro_mock, dummy_coro = coro_tester
        metric1 = mocker.Mock()
        metric2 = mocker.Mock()

        aiometric_relay._metrics['metric1'] = metric1
        aiometric_relay._metrics['metric2'] = metric2

        mocker.patch.object(aiometric_relay, 'flush_single', dummy_coro)

        await aiometric_relay.flush()

        coro_mock.assert_has_calls([
            mocker.call(metric1),
            mocker.call(metric2)
        ])

    @pytest.mark.asyncio
    async def test_flush_single(self, mocker, aiometric_relay, coro_tester):
        endpoint_mock, endpoint_coro = coro_tester
        mocker.patch.object(aiometric_relay.loop, 'create_datagram_endpoint',
                            endpoint_coro)
        await aiometric_relay.emit(
            'test-metric', 42, attributes={
                'attr1': 'val1'
            })
        call_kwargs = endpoint_mock.call_args[1]
        assert call_kwargs['remote_addr'] == ('127.0.0.1', 1000)

        call_lambda = endpoint_mock.call_args[0][0]
        lambda_result = call_lambda()
        assert lambda_result.message == json.dumps({
            'key': 'dummy-key',
            'attributes': {
                'what': 'test-metric',
                'attr1': 'val1'
            },
            'value': 42,
            'type': 'metric',
            'tags': []
        }).encode('utf-8')
