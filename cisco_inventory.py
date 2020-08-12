#!/bin/env pyhon3
from nuaal.connections.cli import Cisco_IOS_Cli, CliMultiRunner
from nuaal.Writers import ExcelWriter
from nuaal.Parsers import CiscoIOSParser
import argparse
import getpass
import pathlib
import logging
import sys

def get_logger(name, verbosity=4, with_threads=False):
    """
    """
    threading_formatter_string = '[%(asctime)s] [%(levelname)s]\t[%(threadName)s][%(module)s][%(funcName)s]\t%(message)s'
    single_formatter_string = '[%(asctime)s] [%(levelname)s]\t[%(module)s][%(funcName)s]\t%(message)s'

    formatter_string = threading_formatter_string if with_threads else single_formatter_string

    verbosity_map = {
        1: logging.CRITICAL,
        2: logging.ERROR,
        3: logging.WARNING,
        4: logging.INFO,
        5: logging.DEBUG
    }

    logger = logging.getLogger(name)
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(formatter_string)
    handler.setFormatter(formatter)
    if not len(logger.handlers):
        logger.addHandler(handler)
    logger.setLevel(verbosity_map[verbosity])

    return logger



class CiscoInventory(object):

    def __init__(self, user, password, input_file=None, output_file=None, workers=5, verbosity=4):
        self.logger = get_logger(name="CiscoInventory", verbosity=verbosity, with_threads=True)
        self.user = user
        self.password = password
        self.input_file = self.check_path(input_file, mode="file")
        self.output_file = pathlib.Path(output_file).resolve().absolute()
        self.logger.info("Output File: {}".format(self.output_file))

        self.hosts = None
        self.workers = workers
        self.data = None

    def run(self):
        self.hosts = self.parse_input()
        self.logger.info("Loaded {} hosts.".format(len(self.hosts)))
        self.data = self.get_device_data()
        self.write_excel()

    def check_path(self, path, mode):
        """
        """
        self.logger.info("Checking Path: '{}'".format(path))
        try:
            if not isinstance(path, pathlib.Path):
                path = pathlib.Path(path)
            if path.exists():
                if path.is_file() and mode == "file":
                    self.logger.info("Path: '{}' Exists: File.".format(path))
                elif path.is_file() and mode == "directory":
                    self.logger.critical("Path: '{}' Exists but is not a file!".format(path))
                    path = None
                elif not path.is_file() and mode == "directory":
                    self.logger.info("Path: '{}' Exists: Directory.".format(path))
                elif not path.is_file() and mode == "file":
                    self.logger.critical("Path: '{}' Exists but is not a directory!".format(path))
                    path = None
                else:
                    self.logger.critical("Path: '{}' Unhandled error!".format(path))
            else:
                self.logger.critical("Path: '{}' Does not exist!".format(path))
        except Exception as e:
            self.logger.critical("Could not determine valid path for '{}'. Exception: {}".format(path, repr(e)))
        finally: 
            return path

    def build_provider(self):
        parser = CiscoIOSParser()
        provider = {
            "username": self.user,
            "password": self.password,
            "store_outputs": False,
            "enable": True,
            "DEBUG": False,
            "parser": parser
        }
        return provider

    def parse_input(self):
        hosts = []
        with self.input_file.open(mode="r") as f:
            for line in [x.strip() for x in f.readlines()]:
                if line.startswith("#"):
                    self.logger.debug("Skiping commented line: {}".format(line))
                    continue
                self.logger.debug("Adding host: {}".format(line))
                hosts.append(line)
        return hosts

    def get_device_data(self):
        runner = CliMultiRunner(provider=self.build_provider(), ips=self.hosts, actions=["get_inventory"], workers=self.workers, verbosity=self.verbosity)
        runner.run()
        return runner.data

    def get_flat_inventory(self):
        inventory_entries = []
        for device in self.data:
            if "inventory" not in device.keys():
                self.logger.error("Could not retrieve inventory for host {}".format(device["ipAddress"]))
                continue
            for entry in device["inventory"]:
                print(entry)
                updated_entry = dict(entry)
                updated_entry.update({"hostname": device["hostname"], "ip_addr": device["ipAddress"]})
                print(updated_entry)
                inventory_entries.append(updated_entry)
        return inventory_entries


    def write_excel(self):
        writer = ExcelWriter()
        data = self.get_flat_inventory()
        inventory_headers = ["hostname", "ip_addr", "name", "desc", "pid", "sn"]
        with writer.create_workbook(path=self.output_file.parent, filename=self.output_file.name) as workbook:
            writer.write_json(workbook=workbook, data=data, worksheetname="Inventory", headers=inventory_headers)



def get_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("-u", "--user", dest="user", help="Username to login to devices.", required=True)
    parser.add_argument("-p", "--password", dest="password", help="Password to login to devices.", default="")
    parser.add_argument("--ask-pass", dest="ask_pass", action="store_true")

    parser.add_argument("-i", "--input", dest="input_file", help="Name or path to input file.")
    parser.add_argument("-o", "--output", dest="output_file", help="Name or path to output file.")
    parser.add_argument("-v", "--verbosity", dest="verbosity", default=4, type=int)
    parser.add_argument("-w", "--workers", dest="workers", default=5, type=int)
    args = parser.parse_args()
    if args.ask_pass:
        args.password = getpass.getpass()
    return args

def main():
    args = get_arguments()
    inventory = CiscoInventory(user=args.user, password=args.password, input_file=args.input_file, workers=args.workers, output_file=args.output_file, verbosity=args.verbosity)
    inventory.run()



if __name__ == "__main__":
    main()