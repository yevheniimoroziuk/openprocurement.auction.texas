# -*- coding: utf-8 -*-
from copy import deepcopy

def prepare_bid_stage(exist_stage_params, params={},  current_auction_value=0):
    # Should get amount of previous stage or initial_auction_value
    # current_auction_value += minimalStep
    stage = None
    return stage


def post_results_data(auction):
    pass


def prepare_public_document(self):
    public_document = deepcopy(dict(self.auction_document))
    return public_document


def filter_bids(results):

    bids_information = dict([
        (bid["id"], bid.get("tenderers"))
        for bid in results["data"].get("bids", [])
        if bid.get("status", "active") == "active"
    ])

    return bids_information


def set_bids_information(self, auction_document, bids_information):
    for field in ['results', 'stages']:
        for index, stage in enumerate(auction_document[field]):
            if 'bidder_id' in stage and stage['bidder_id'] in bids_information:
                auction_document[field][index].update({
                    "label": {
                        'uk': bids_information[stage['bidder_id']][0]["name"],
                        'en': bids_information[stage['bidder_id']][0]["name"],
                        'ru': bids_information[stage['bidder_id']][0]["name"],
                    }
                })
