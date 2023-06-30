#!/usr/bin/env python3

import argparse
import io
import os
import sys
import json
import threading
import http.client
import urllib
import urllib.parse
from datetime import datetime
import collections

import pkg_resources
from jsonschema.validators import Draft4Validator
import requests
from requests.auth import HTTPBasicAuth
import singer

logger = singer.get_logger()

def emit_state(state):
    if state is not None:
        line = json.dumps(state)
        logger.debug('Emitting state {}'.format(line))
        sys.stdout.write("{}\n".format(line))
        sys.stdout.flush()
        
def persist_lines(config, lines):
    state = None
    schemas = {}
    key_properties = {}
    headers = {}
    validators = {}
    
    now = datetime.now().strftime('%Y%m%dT%H%M%S')

    url = config['url']
    headers = {}
    if 'post_headers' in config:
        headers = config['post_headers']
    
    method='GET'
    if 'method' in config:
        method = config['method']
    if method != 'POST' and method != 'GET':
        method='GET'

    # Maps property names from tap to target field names in the API
    property_mapping = {}
    for property in config['property_mapping']:
        property_mapping[property]=config['property_mapping'][property]["target_field_name"]

    # Loop over lines from stdin
    for line in lines:
        try:
            o = json.loads(line)
        except json.decoder.JSONDecodeError:
            logger.error("Unable to parse:\n{}".format(line))
            raise

        if 'type' not in o:
            raise Exception("Line is missing required key 'type': {}".format(line))
        t = o['type']

        if t == 'RECORD':
            if 'stream' not in o:
                raise Exception("Line is missing required key 'stream': {}".format(line))
            if o['stream'] not in schemas:
                raise Exception("A record for stream {} was encountered before a corresponding schema".format(o['stream']))

            # Get schema for this record's stream
            schema = schemas[o['stream']]

            # Validate record
            validators[o['stream']].validate(o['record'])

            data = {}
            for property in property_mapping:
                data[property_mapping[property]]=o['record'][property]

            if 'additional_properties' in config:
                for property in config['additional_properties']:
                    data[property]=config['additional_properties'][property]

            is_filtered = False
            filter_reason=''
            if 'filter_rules' in config:
                for field in config['filter_rules']:
                    if config['filter_rules'][field]['type'] == 'equals':
                        if o['record'][field] != config['filter_rules'][field]['value']:
                            is_filtered = True
                            filter_reason = "field {} does not equal {}".format(field, config['filter_rules'][field]['value'])
                    elif config['filter_rules'][field]['type'] == 'not_equals':
                        if o['record'][field] == config['filter_rules'][field]['value']:
                            is_filtered = True
                            filter_reason = "field {} does not equal {}".format(field, config['filter_rules'][field]['value'])
                    elif config['filter_rules'][field]['type'] == 'contains':
                        if o['record'][field].contains(config['filter_rules'][field]['value']) == False:
                            is_filtered = True
                            filter_reason = "field {} does not equal {}".format(field, config['filter_rules'][field]['value'])

                    elif config['filter_rules'][field]['type'] == 'not_contains':
                        if o['record'][field].contains(config['filter_rules'][field]['value']) == True:
                            is_filtered = True
                            filter_reason = "field {} does not equal {}".format(field, config['filter_rules'][field]['value'])
                    elif config['filter_rules'][field]['type'] == 'is_empty':
                        if config['filter_rules'][field]['value'] == False:
                            if field not in o['record'] or o['record'][field] == '':
                                is_filtered = True
                                filter_reason = "field {} is empty".format(field)
                        elif config['filter_rules'][field]['value'] == True:
                            if field in o['record'] and o['record'][field] != '':
                                is_filtered = True
                                filter_reason = "field {} is not empty".format(field)

            if is_filtered == True:
                print("Filtered record: {}, reason: {}".format(line, filter_reason))
            else:
                try:
                    if method == 'GET':
                        encoded_params = urllib.parse.urlencode( data )
                        page_url = "{}?{}".format(url, encoded_params)
                        response = requests.get(page_url)
                        print("url: {}, response: {}".format(page_url, response))
                    else:
                        if 'username' in config and 'password' in config:
                            response =  requests.post(url, data=data, headers=headers, auth=HTTPBasicAuth(config['username'], config['password']))
                        else:
                            response =  requests.post(url, data=data, headers=headers)
                        logger.debug("line: {}, response: {}".format(line, response))
                except:
                    logger.error("Unable to post:\n{}".format(line))
                    raise

            state = None
        elif t == 'STATE':
            logger.debug('Setting state to {}'.format(o['value']))
            state = o['value']
        elif t == 'SCHEMA':
            if 'stream' not in o:
                raise Exception("Line is missing required key 'stream': {}".format(line))
            stream = o['stream']
            schemas[stream] = o['schema']
            validators[stream] = Draft4Validator(o['schema'])
            if 'key_properties' not in o:
                raise Exception("key_properties field is required")
            key_properties[stream] = o['key_properties']
        else:
            raise Exception("Unknown message type {} in message {}"
                            .format(o['type'], o))
    
    return state

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--config', help='Config file')
    args = parser.parse_args()

    if args.config:
        with open(args.config) as input:
            config = json.load(input)
    else:
        config = {}

    # Validate config url value is present
    if 'url' not in config:
        raise Exception("config file must contain url.")
    if config['url'] == '':
        raise Exception("config file must contain value for url.")

    input = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8')
    state = persist_lines(config, input)
        
    emit_state(state)
    logger.debug("Exiting normally")


if __name__ == '__main__':
    main()
