"""
Updates the currency codelist from ISO4217 files.
"""

import csv
import os.path
import re

import requests
from lxml import etree

from helper import json_dump, json_load, schema_dir


def get_and_parse_xml(url):
    response = requests.get(url)
    response.raise_for_status()
    return etree.fromstring(response.content)


if __name__ == '__main__':
    # "List one: Current currency & funds code list"
    # https://www.currency-iso.org/en/home/tables/table-a1.html
    current_codes = {}
    tree = get_and_parse_xml('https://www.currency-iso.org/dam/downloads/lists/list_one.xml')
    for node in tree.xpath('//CcyNtry'):
        match = node.xpath('./Ccy')
        # Entries like Antarctica have no universal currency.
        if match:
            code = node.xpath('./Ccy')[0].text
            title = node.xpath('./CcyNm')[0].text.strip()
            if code not in current_codes:
                current_codes[code] = title
            # We should expect currency titles to be consistent across countries.
            elif current_codes[code] != title:
                raise Exception('expected {}, got {}'.format(current_codes[code], title))

    # "List three: List of codes for historic denominations of currencies & funds"
    # https://www.currency-iso.org/en/home/tables/table-a3.html
    historic_codes = {}
    tree = get_and_parse_xml('https://www.currency-iso.org/dam/downloads/lists/list_three.xml')
    for node in tree.xpath('//HstrcCcyNtry'):
        code = node.xpath('./Ccy')[0].text
        title = node.xpath('./CcyNm')[0].text.strip()
        valid_until = node.xpath('./WthdrwlDt')[0].text
        # Use ISO8601 interval notation.
        valid_until = re.sub(r'^(\d{4})-(\d{4})$', r'\1/\2', valid_until.replace(' to ', '/'))
        if code not in current_codes:
            if code not in historic_codes:
                historic_codes[code] = {'Title': title, 'Valid Until': valid_until}
            # If the code is historical, use the most recent title and valid date.
            elif valid_until > historic_codes[code]['Valid Until']:
                historic_codes[code] = {'Title': title, 'Valid Until': valid_until}

    with open(os.path.join(schema_dir, 'codelists', 'currency.csv'), 'w') as fp:
        writer = csv.writer(fp, lineterminator='\n')
        writer.writerow(['Code', 'Title', 'Valid Until'])
        for code in sorted(current_codes.keys()):
            writer.writerow([code, current_codes[code], None])
        for code in sorted(historic_codes.keys()):
            writer.writerow([code, historic_codes[code]['Title'], historic_codes[code]['Valid Until']])

    release_schema = json_load('release-schema.json')
    codes = sorted(list(current_codes.keys()) + list(historic_codes.keys()))
    release_schema['definitions']['Value']['properties']['currency']['enum'] = codes + [None]

    json_dump('release-schema.json', release_schema)
