# Lambda Atlas Load Testing function (Python)

See [DRIVERS-2721](https://jira.mongodb.org/browse/DRIVERS-2721).

![Architecture](/images/sample-blank-python.png)

The project source includes function code and supporting resources:

- `python/` - A Python function.
- `template.yml` - An AWS CloudFormation template that creates an application.
- `deploy-loadtest.sh`, `cleaup.sh`, etc. - Shell scripts that use the AWS CLI to deploy and manage the application.
- `loadtest.py` - Python app that load tests the Lambda/MongoDB application.

Use the following instructions to deploy the sample application.

# Requirements
- [Python 3.11](https://www.python.org/downloads/). Sample also works with Python 3.7+. 
- The Bash shell. For Linux and macOS, this is included by default. In Windows 10, you can install the [Windows Subsystem for Linux](https://docs.microsoft.com/en-us/windows/wsl/install-win10) to get a Windows-integrated version of Ubuntu and Bash.
- [The AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-install.html) v1.17 or newer.
- [hey](https://github.com/rakyll/hey) HTTP load testing tool. 
- A `$MONGODB_URI` env var pointing to a publicly accessible MongoDB cluster.

If you use the AWS CLI v2, add the following to your [configuration file](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html) (`~/.aws/config`):

```
cli_binary_format=raw-in-base64-out
```

This setting enables the AWS CLI v2 to load JSON events from a file, matching the v1 behavior.

# Setup
Download or clone this repository.

    $ git clone https://github.com/ShaneHarvey/lambda-atlas-testing.git
    $ cd lambda-atlas-testing

Install [hey](https://github.com/rakyll/hey) HTTP load testing tool. 

# Repro
To create and deploy the lambda function and run the load test, run `deploy-loadtest.sh`.

    lambda-atlas-testing$ export MONGODB_URI="mongodb+srv://..."
    lambda-atlas-testing$ ./deploy-loadtest.sh
    ...

# Cleanup
To delete the application, run `cleanup.sh`.

    lambda-atlas-testing$ ./cleanup.sh

# Running loadtest.py itself

You can re-run the `loadtest.py` script on its own once the Lambda function is deployed: 

    lambda-atlas-testing$ export MONGODB_URI="mongodb+srv://..."
    lambda-atlas-testing$ export LAMBDA_FUNCTION_URL="https://<...>.lambda-url.us-east-1.on.aws/"
    lambda-atlas-testing$ ./python loadtest.py
    ...

loadtest.py supports a number of tuning parameters, for example to issue 2000 concurrent
requests (rather than the default 1000): 

    lambda-atlas-testing$ ./python loadtest.py --concurrency 2000
    ...

To incrementally ramp up the requests by increments of 50: 

    lambda-atlas-testing$ ./python loadtest.py --increment 50
    ...

# Example loadtest.py induced election
The following example shows an election on an Atlas M30 replica set caused by the
load induced by `hey -n 2000 -c 1000 FUNCTION_URL`. The script automatically stops
once an election is detected:
```
lambda-atlas-testing$ python loadtest.py
2023-09-29 18:54:36,024 INFO event_loggers Server ('drivers-2721-repl-shard-00-00.gh2ak.mongodb.net', 27017) added to topology 65171d6ce5c16406b0e9486b
2023-09-29 18:54:36,025 INFO event_loggers Server ('drivers-2721-repl-shard-00-01.gh2ak.mongodb.net', 27017) added to topology 65171d6ce5c16406b0e9486b
2023-09-29 18:54:36,025 INFO event_loggers Server ('drivers-2721-repl-shard-00-02.gh2ak.mongodb.net', 27017) added to topology 65171d6ce5c16406b0e9486b
2023-09-29 18:54:36,094 INFO loadtest initial topology description: <TopologyDescription id: 65171d6ce5c16406b0e9486b, topology_type: ReplicaSetWithPrimary, servers: [<ServerDescription ('drivers-2721-repl-shard-00-00.gh2ak.mongodb.net', 27017) server_type: RSSecondary, rtt: 0.0015551270043943077>, <ServerDescription ('drivers-2721-repl-shard-00-01.gh2ak.mongodb.net', 27017) server_type: RSSecondary, rtt: 0.0004950640141032636>, <ServerDescription ('drivers-2721-repl-shard-00-02.gh2ak.mongodb.net', 27017) server_type: RSPrimary, rtt: 0.0008535049855709076>]>
2023-09-29 18:54:36,095 INFO loadtest running: hey -n 2000 -c 1000 https://fxsgokhfgg3dt5vxayz7montku0gxirs.lambda-url.us-east-1.on.aws/
2023-09-29 18:54:37,026 INFO event_loggers Server ('drivers-2721-repl-shard-00-01.gh2ak.mongodb.net', 27017) changed type from Unknown to RSSecondary
2023-09-29 18:54:37,026 INFO event_loggers Server ('drivers-2721-repl-shard-00-02.gh2ak.mongodb.net', 27017) changed type from Unknown to RSPrimary
2023-09-29 18:54:37,026 INFO event_loggers Server ('drivers-2721-repl-shard-00-00.gh2ak.mongodb.net', 27017) changed type from Unknown to RSSecondary

Summary:
  Total:	9.0805 secs
  Slowest:	5.1216 secs
  Fastest:	3.0132 secs
  Average:	3.4397 secs
  Requests/sec:	220.2520

  Total data:	42000 bytes
  Size/request:	21 bytes

Response time histogram:
  3.013 [1]	|
  3.224 [37]	|■■
  3.435 [959]	|■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■
  3.646 [969]	|■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■
  3.857 [5]	|
  4.067 [27]	|■
  4.278 [0]	|
  4.489 [0]	|
  4.700 [0]	|
  4.911 [0]	|
  5.122 [2]	|


Latency distribution:
  10% in 3.3100 secs
  25% in 3.3375 secs
  50% in 3.4567 secs
  75% in 3.5382 secs
  90% in 3.5679 secs
  95% in 3.5875 secs
  99% in 3.9786 secs

Details (average, fastest, slowest):
  DNS+dialup:	0.1484 secs, 3.0132 secs, 5.1216 secs
  DNS-lookup:	0.0169 secs, 0.0000 secs, 0.0555 secs
  req write:	0.0048 secs, 0.0000 secs, 0.1256 secs
  resp wait:	3.2858 secs, 3.0114 secs, 5.1215 secs
  resp read:	0.0000 secs, 0.0000 secs, 0.0016 secs

Status code distribution:
  [502]	2000 responses



2023-09-29 18:54:45,287 INFO loadtest running: hey -n 2000 -c 1000 https://fxsgokhfgg3dt5vxayz7montku0gxirs.lambda-url.us-east-1.on.aws/
2023-09-29 18:54:46,029 INFO event_loggers Server ('drivers-2721-repl-shard-00-02.gh2ak.mongodb.net', 27017) changed type from RSPrimary to RSSecondary
2023-09-29 18:54:53,030 INFO event_loggers Server ('drivers-2721-repl-shard-00-01.gh2ak.mongodb.net', 27017) changed type from RSSecondary to RSPrimary

Summary:
  Total:	8.9604 secs
  Slowest:	5.6086 secs
  Fastest:	3.0110 secs
  Average:	3.3893 secs
  Requests/sec:	223.2040

  Total data:	42000 bytes
  Size/request:	21 bytes

Response time histogram:
  3.011 [1]	|
  3.271 [324]	|■■■■■■■■■■
  3.531 [1363]	|■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■
  3.790 [311]	|■■■■■■■■■
  4.050 [0]	|
  4.310 [0]	|
  4.570 [0]	|
  4.829 [0]	|
  5.089 [0]	|
  5.349 [0]	|
  5.609 [1]	|


Latency distribution:
  10% in 3.2423 secs
  25% in 3.2954 secs
  50% in 3.3605 secs
  75% in 3.5161 secs
  90% in 3.5384 secs
  95% in 3.5501 secs
  99% in 3.5697 secs

Details (average, fastest, slowest):
  DNS+dialup:	0.1427 secs, 3.0110 secs, 5.6086 secs
  DNS-lookup:	0.0134 secs, 0.0000 secs, 0.0647 secs
  req write:	0.0013 secs, 0.0000 secs, 0.0947 secs
  resp wait:	3.2452 secs, 3.0097 secs, 5.6085 secs
  resp read:	0.0000 secs, 0.0000 secs, 0.0011 secs

Status code distribution:
  [502]	2000 responses



2023-09-29 18:54:54,359 INFO loadtest running: hey -n 2000 -c 1000 https://fxsgokhfgg3dt5vxayz7montku0gxirs.lambda-url.us-east-1.on.aws/
2023-09-29 18:54:58,028 INFO loadtest stopping workload thread...

Summary:
  Total:	7.0252 secs
  Slowest:	3.7028 secs
  Fastest:	3.0131 secs
  Average:	3.3731 secs
  Requests/sec:	284.6880

  Total data:	42000 bytes
  Size/request:	21 bytes

Response time histogram:
  3.013 [1]	|
  3.082 [64]	|■■■■
  3.151 [97]	|■■■■■
  3.220 [314]	|■■■■■■■■■■■■■■■■■■
  3.289 [181]	|■■■■■■■■■■
  3.358 [363]	|■■■■■■■■■■■■■■■■■■■■■
  3.427 [59]	|■■■
  3.496 [102]	|■■■■■■
  3.565 [708]	|■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■
  3.634 [107]	|■■■■■■
  3.703 [4]	|


Latency distribution:
  10% in 3.1612 secs
  25% in 3.2273 secs
  50% in 3.3528 secs
  75% in 3.5292 secs
  90% in 3.5540 secs
  95% in 3.5683 secs
  99% in 3.5967 secs

Details (average, fastest, slowest):
  DNS+dialup:	0.1117 secs, 3.0131 secs, 3.7028 secs
  DNS-lookup:	0.0410 secs, 0.0000 secs, 0.2719 secs
  req write:	0.0024 secs, 0.0000 secs, 0.2246 secs
  resp wait:	3.2579 secs, 3.0114 secs, 3.7027 secs
  resp read:	0.0000 secs, 0.0000 secs, 0.0027 secs

Status code distribution:
  [502]	2000 responses



2023-09-29 18:55:01,496 INFO loadtest load test caused a server state change after 25.4016432762146 seconds: <ServerDescription ('drivers-2721-repl-shard-00-01.gh2ak.mongodb.net', 27017) server_type: RSSecondary, rtt: 0.0004950640141032636> changed event <ServerDescriptionChangedEvent ('drivers-2721-repl-shard-00-01.gh2ak.mongodb.net', 27017) changed from: <ServerDescription ('drivers-2721-repl-shard-00-01.gh2ak.mongodb.net', 27017) server_type: RSSecondary, rtt: 0.0004950640141032636>, to: <ServerDescription ('drivers-2721-repl-shard-00-01.gh2ak.mongodb.net', 27017) server_type: RSSecondary, rtt: 0.0004915874102152884>>
2023-09-29 18:55:01,496 INFO loadtest starting topology description:
<TopologyDescription id: 65171d6ce5c16406b0e9486b, topology_type: ReplicaSetWithPrimary, servers: [<ServerDescription ('drivers-2721-repl-shard-00-00.gh2ak.mongodb.net', 27017) server_type: RSSecondary, rtt: 0.0015551270043943077>, <ServerDescription ('drivers-2721-repl-shard-00-01.gh2ak.mongodb.net', 27017) server_type: RSSecondary, rtt: 0.0004950640141032636>, <ServerDescription ('drivers-2721-repl-shard-00-02.gh2ak.mongodb.net', 27017) server_type: RSPrimary, rtt: 0.0008535049855709076>]>
ending topology description:
<TopologyDescription id: 65171d6ce5c16406b0e9486b, topology_type: ReplicaSetWithPrimary, servers: [<ServerDescription ('drivers-2721-repl-shard-00-00.gh2ak.mongodb.net', 27017) server_type: RSSecondary, rtt: 0.002210055644391105>, <ServerDescription ('drivers-2721-repl-shard-00-01.gh2ak.mongodb.net', 27017) server_type: RSPrimary, rtt: 0.0017146901297383013>, <ServerDescription ('drivers-2721-repl-shard-00-02.gh2ak.mongodb.net', 27017) server_type: RSSecondary, rtt: 0.0012022389855701479>]>
```