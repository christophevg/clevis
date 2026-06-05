import argparse

from clevis import configclass, get_config, get_factory, SecurityAction


# our own configuration
@configclass
class MyConfig:
  verbose: bool = False


# 2 external packages, providing App1 and App2 classes, each with Clevis config


@configclass
class App1Config:
  name: str | None = None


@configclass
class App2Config:
  name: str | None = None


class App1:
  def __init__(self):
    self.config: App1Config = get_config(
      App1Config,
      name="app1",
      security={
        "file_permissions": SecurityAction.LOG,
        "directory_permissions": SecurityAction.LOG,
      },
    )

  def __str__(self):
    return str(self.config)


class App2:
  def __init__(self):
    self.config: App2Config = get_config(
      App2Config,
      security={
        "file_permissions": SecurityAction.LOG,
        "directory_permissions": SecurityAction.LOG,
      },
    )

  def __str__(self):
    return str(self.config)


# now configure factories for the configurations of App1 and App2
# and apply a prefix to avoid config argument collisions between the two app's
# configs.
get_factory(App1Config).prefix = "app1"
get_factory(App2Config).prefix = "app2"

# optionally change the parser
parser = argparse.ArgumentParser(description="My Factory Parser")
get_factory(App1Config).parser = parser
get_factory(App2Config).parser = parser
get_factory(MyConfig).parser = parser

# both constructors
# - load their configurations using auto discovery (user/project)
# - since we created a factory for their configuration they'll use that
# this triggers the first get_config, and resolves cli args for the first time
app1 = App1()  # also would stop here in case of --help
app2 = App2()

if get_config(
  MyConfig,
  security={"file_permissions": SecurityAction.LOG, "directory_permissions": SecurityAction.LOG},
).verbose:
  print(app1)
  print(app2)

"""

% uv run python factory.py --help
usage: factory.py [-h] [--app1-name APP1.NAME] [--app2-name APP2.NAME]
                  [--verbose]

My Factory Parser

options:
  -h, --help            show this help message and exit
  --app1-name APP1.NAME
                        provide app1.name
  --app2-name APP2.NAME
                        provide app2.name
  --verbose             provide verbose

% uv run python factory.py --app2-name "cli > name" --verbose
App1Config(name='app1.toml > name')
App2Config(name='cli > name')

"""
