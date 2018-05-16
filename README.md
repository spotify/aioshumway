# AIOShumway

[![Build Status](https://travis-ci.org/spotify/aioshumway.svg?branch=master)](https://travis-ci.org/spotify/aioshumway) 

A wrapper around the [shumway](https://github.com/spotify/shumway) library that uses [asyncio](https://docs.python.org/3/library/asyncio.html) to make all IO operations non-blocking and compatible with the async/await syntax.

**NOTE:** This is a lightly touched up copy of [shumway's](https://github.com/spotify/shumway) README since the only difference between these libraries is that this one provides an awaitable interface.

## Requirements

* Python 3.6
* Support for Linux & OS X

## To Use

```sh
(env) $ pip install aioshumway
```

### Counters

Create a default counter and send to FFWD:

```python
import aioshumway

mr = aioshumway.MetricRelay(SERVICE_NAME)
mr.incr(METRIC_NAME)
# inside an async context
await mr.flush()
```

#### Initialize a counter with a value

```python
import aioshumway

mr = aioshumway.MetricRelay(SERVICE_NAME)
counter = aioshumway.Counter(metric_name, SERVICE_NAME, value=10)
mr.set_counter(metric_name, counter)
mr.incr(metric_name)
# inside an async context
await mr.flush()
```

#### Different increment values

Create a named counter and increment by a value different than 1:

```python
import aioshumway

mr = aioshumway.MetricRelay(SERVICE_NAME)
mr.incr(METRIC_NAME, 2)
# inside an async context
await mr.flush()
```

#### Custom Counter Attributes

Set custom attributes for metrics:

```python
import aioshumway

mr = aioshumway.MetricRelay(SERVICE_NAME)
counter = aioshumway.counter(metric_name, SERVICE_NAME,
                          {attr_1: value_1,
                           attr_2: value_2})

mr.set_counter(metric_name, counter)
mr.incr(metric_name)
# inside an async context
await mr.flush()

```

**NB:** If you use duplicate names when calling `set_counter` it will overwrite the
counter. You will likely want to use a unique metric name for each set of
attributes you are setting.

### Timers

```python
import aioshumway

mr = aioshumway.MetricRelay(SERVICE_NAME)
timer = mr.timer('timing-this-thing')

# inside an async context
with timer:
    ...task you want to time

await mr.flush()
```

### Custom Timer Attributes
Timers can also be created independently in order to set custom attributes:

```python
import aioshumway

mr = aioshumway.MetricRelay(SERVICE_NAME)
timer = aioshumway.Timer('timing-this-thing', SERVICE_NAME,
                         {'attr_1': value_1, 'attr_2': value_2})

# inside an async context
with timer:
    # ...task you want to time

mr.set_timer('timing-this-thing', timer)
await mr.flush()
```

### Sending Metrics

There are two ways to send metrics to the `ffwd` agent:

#### Emit one metric

You can emit a one-off, event-type metric immediately:

```python
import aioshumway

mr = aioshumway.MetricRelay('my-service')

# inside an async context

# some event happened
await mr.emit('a-successful-event', 1)

# some event happened with attributes
await mr.emit('a-successful-event', 1, {'attr_1': value_1, 'attr_2': value_2})

# an event with a multiple value happened
await mr.emit('a-successful-event', 5)
```

#### Flushing all metrics

For batch-like metrics, you can flush metrics once you're ready:

```python
import aioshumway

mr = aioshumway.MetricRelay('my-service')

# measure all the things
# time all the things

# inside an async context
if not dry_run:
    await mr.flush()
```


### Existing Metrics
Check for existence of metrics in the MetricRelay with `in`:

```pycon
>>> import aioshumway
>>> mr = aioshumway.MetricRelay('my-service')
>>> counter = aioshumway.Counter('thing-to-count', 'my-service', value=5)
>>> mr.set_counter('thing-to-count', counter)
>>> 'thing-to-count' in mr
True
>>> 'not-a-counter' in mr
False
```

### Custom FFWD agents

By default, `aioshumway` will send metrics to a local [`ffwd`](https://github.com/spotify/ffwd) agent at `127.0.0.1:19000`. 

If your `ffwd` agent is elsewhere, then pass that information through when initializing the `MetricRelay`:

```python
import aioshumway

mr = aioshumway.MetricRelay(SERVICE_NAME, ffwd_ip='10.99.0.1', ffwd_port=19001)

# do the thing
```

# Developer Setup

For development and running tests, your system must have all supported versions of Python installed. We suggest using [pyenv](https://github.com/yyuu/pyenv).

## Setup

```sh
$ git clone git@github.com:spotify/aioshumway.git && cd aioshumway
# make a virtualenv
(env) $ pip install -r dev-requirements.txt
```

## Running tests

To run the entire test suite:

```sh
# outside of the virtualenv
# if tox is not yet installed
$ pip install tox
$ tox
```

To run an individual test, pass the test's name to pytest, through `tox`:

```sh
# inside virtualenv

(env) $ tox -- tests/test_aioshumway.py::TestSomething
```

# Code of Conduct

This project adheres to the [Open Code of Conduct][code-of-conduct]. By participating, you are expected to honor this code.

[code-of-conduct]: https://github.com/spotify/code-of-conduct/blob/master/code-of-conduct.md
