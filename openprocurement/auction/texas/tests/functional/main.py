# -*- coding: utf-8 -*-
import tempfile
import contextlib
import yaml
from datetime import datetime, timedelta
from dateutil.tz import tzlocal
from uuid import uuid4

from gevent import monkey
monkey.patch_all()

import os.path
import json
from gevent.subprocess import check_output, sleep
from openprocurement.auction.utils import calculate_hash


PAUSE_SECONDS = timedelta(seconds=120)
PWD = os.path.dirname(os.path.realpath(__file__))
CWD = os.getcwd()
TEST_FILE = '{}/src/openprocurement.auction.texas/openprocurement/auction/texas/tests/functional/data/auction_file.json'.format(CWD)

HASH_SECRET = yaml.load(open('{0}/etc/auction_worker_texas.yaml'.format(CWD), 'r'))['HASH_SECRET']


@contextlib.contextmanager
def update_auctionPeriod(path):
    with open(path) as file:
        data = json.loads(file.read())
    new_start_time = (datetime.now(tzlocal()) + PAUSE_SECONDS).isoformat()

    data['data']['auctionPeriod']['startDate'] = new_start_time
    with open(TEST_FILE, 'w') as auction_file:
        json.dump(data, auction_file)
    yield auction_file.name
    auction_file.close()


def run_texas(tender_file_path):
    with open(tender_file_path) as _file:
        auction_json = json.load(_file).get('data', {})
        auction_id = uuid4().hex
        bids = auction_json.get('bids', [])
        if auction_id:
            check_output(TESTS['texas']['worker_cmd'].format(CWD, auction_id).split())

    for bid in bids:
        print 'texas-auctions/{}/login?bidder_id={}&hash={}'.format(
            auction_id,
            bid["id"],
            calculate_hash(bid["id"], HASH_SECRET)
        )
    sleep(30)


TESTS = {
    "texas": {
        "worker_cmd": '{0}/bin/auction_texas planning {1}'
                      ' {0}/etc/auction_worker_texas.yaml'
                      ' --planning_procerude partial_db',
        "runner": run_texas,
        'auction_worker_defaults': 'auction_worker_defaults:{0}/etc/auction_worker_defaults.yaml',
        'suite': PWD
    }
}


def includeme(tests):
    tests.update(TESTS)
