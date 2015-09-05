import logging
import logging.config
import yaml
import click

__author__ = 'cody'


def configure_logging(logging_cfg):
    logging.config.dictConfig(logging_cfg)


def load_config(cfg_file):
    return yaml.load(cfg_file)


with click.open_file("config.yml") as cfg_file:
    cfg = load_config(cfg_file)

    if "logging" not in cfg:
        click.secho("No logging configuration found", fg="red")
    else:
        configure_logging(cfg["logging"])

    logging.getLogger(__name__).info("Hello")
