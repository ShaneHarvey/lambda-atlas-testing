# Lambda Atlas Load Testing function (Python)

See [DRIVERS-2721](https://jira.mongodb.org/browse/DRIVERS-2721).

![Architecture](/images/sample-blank-python.png)

The project source includes function code and supporting resources:

- `python/` - A Python function.
- `template.yml` - An AWS CloudFormation template that creates an application.
- `1-create-bucket.sh`, `2-build-layer.sh`, etc. - Shell scripts that use the AWS CLI to deploy and manage the application.

Use the following instructions to deploy the sample application.

# Requirements
- [Python 3.11](https://www.python.org/downloads/). Sample also works with Python 3.7+. 
- The Bash shell. For Linux and macOS, this is included by default. In Windows 10, you can install the [Windows Subsystem for Linux](https://docs.microsoft.com/en-us/windows/wsl/install-win10) to get a Windows-integrated version of Ubuntu and Bash.
- [The AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-install.html) v1.17 or newer.
- [hey](https://github.com/rakyll/hey) HTTP load testing tool. 

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

To create and deploy the lambda function and run the load test, run `deploy-loadtest.sh`.

    lambda-atlas-testing$ ./deploy-loadtest.sh
    ...

# Cleanup
To delete the application, run `cleanup.sh`.

    lambda-atlas-testing$ ./cleanup.sh
