#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
RemoteApp synchronization
"""
import argparse
import getpass
import os

from xml.etree import ElementTree

import jinja2
import requests

from requests_ntlm2 import HttpNtlmAuth

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
RDP_FILES_PATH = os.path.expanduser(os.path.join("~", ".cache", "remoteapp"))


def create_arguments():
    """
    Make client arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("url", metavar="URL", help="RemoteApp service url")
    parser.add_argument("-u", "--user")
    parser.add_argument("-p", "--password")
    parser.add_argument("-d", "--domain")

    return parser.parse_args()


def parse_icons(icons):
    """
    Get informations for application icons
    """
    icon_list = []
    for icon in icons:
        icon_list.append(icon.attrib)

    return icon_list


def parse_terminal_servers(terminal_servers):
    """
    Get terminal servers informations
    """
    terminal_server_list = []
    for server in terminal_servers:
        resource_file = server.find("./{*}ResourceFile").attrib
        terminal_server_ref = server.find("./{*}TerminalServerRef").attrib.get("Ref")
        terminal_server_list.append(
            {"resource_file": resource_file, "ref": terminal_server_ref}
        )

        return terminal_server_list


def parse_resource(resource):
    """
    Get informations from Resource element
    """
    icons = resource.find("./{*}Icons")
    icon_list = parse_icons(icons)

    terminal_servers = resource.find("./{*}HostingTerminalServers")
    terminal_server_list = parse_terminal_servers(terminal_servers)

    return {
        **resource.attrib,
        "icons": icon_list,
        "terminal_servers": terminal_server_list,
    }


def download_rdp(auth_cookie, server):
    """
    Download rdp files from the serve to .cache
    """
    url = f"https://{server['ref']}{server['resource_file']['URL']}"
    response = requests.get(url, cookies=auth_cookie)
    rdp_path = os.path.join(RDP_FILES_PATH, url.rsplit("/", 1)[1])
    with open(rdp_path, "wb") as rdp_file:
        rdp_file.write(response.content)

    return rdp_path


def generate_desktop(resource, rdp_file):
    """
    Create desktop file
    """
    loader = jinja2.FileSystemLoader(ROOT_DIR)
    env = jinja2.Environment(loader=loader)
    template = env.get_template("desktop-file.jinja2")
    rendered_content = template.render(
        comment=resource["Alias"], name=resource["Title"], rdp_file=rdp_file
    )
    application_path = os.path.expanduser(
        os.path.join("~", ".local", "share", "applications")
    )
    desktop_file_path = os.path.join(application_path, f'{resource["Alias"]}.desktop')
    with open(desktop_file_path, "w") as desktop_file:
        desktop_file.write(rendered_content)


def get_auth_info(args):
    """
    Prepare authentication
    """
    user = args.user if args.user else input("User:")
    password = args.password if args.password else getpass.getpass()
    domain = args.domain if args.domain else input("Domain:")

    return {
        "user": rf"{domain}\{user}",
        "password": password,
    }

def main():
    """
    The main function
    """
    args = create_arguments()
    auth = get_auth_info(args)
    session = requests.Session()
    session.auth = HttpNtlmAuth(auth["user"], auth["password"])
    response = session.get(args.url)
    cookie = {".ASPXauth": response.text}
    response = session.get(args.url, cookies=cookie)
    root = ElementTree.fromstring(response.text)
    os.makedirs(RDP_FILES_PATH, exist_ok=True)
    for item in root.findall("./{*}Publisher/{*}Resources/{*}Resource"):
        parsed_resource = parse_resource(item)
        for terminal_server in parsed_resource["terminal_servers"]:
            rdp_file = download_rdp(cookie, terminal_server)
            generate_desktop(parsed_resource, rdp_file)

if __name__ == "__main__":
    main()
