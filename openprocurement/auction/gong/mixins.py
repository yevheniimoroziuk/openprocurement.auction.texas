import logging
import json
from copy import deepcopy
from couchdb.http import HTTPError, RETRYABLE_ERRORS

from openprocurement.auction.utils import get_tender_data

from openprocurement.auction.gong.utils import (
    prepare_auction_document,
    post_results_data,
    announce_results_data,
    filter_bids,
    set_bids_information
)
from openprocurement.auction.gong.constants import (
   BIDS_KEYS_FOR_COPY
)
from openprocurement.auction.worker_core.mixins import (
    RequestIDServiceMixin, AuditServiceMixin
)
from openprocurement.auction.gong.journal import (
    AUCTION_WORKER_DB_GET_DOC,
    AUCTION_WORKER_DB_GET_DOC_ERROR,
    AUCTION_WORKER_DB_GET_DOC_UNHANDLED_ERROR,
    AUCTION_WORKER_DB_SAVE_DOC,
    AUCTION_WORKER_DB_SAVE_DOC_ERROR,
    AUCTION_WORKER_DB_SAVE_DOC_UNHANDLED_ERROR,
    AUCTION_WORKER_BIDS_LATEST_BID_CANCELLATION,
    AUCTION_WORKER_API_AUCTION_RESULT_NOT_APPROVED,
    AUCTION_WORKER_SERVICE_END_BID_STAGE,
    AUCTION_WORKER_SERVICE_START_STAGE,
    AUCTION_WORKER_SERVICE_START_NEXT_STAGE,
)


LOGGER = logging.getLogger("Auction Worker")


class DBServiceMixin(RequestIDServiceMixin):
    """ Mixin class to work with couchdb"""
    db_request_retries = 10
    db = None
    auction_document = None
    auction_doc_id = ''

    def get_auction_document(self, force=False):
        self.generate_request_id()
        retries = self.db_request_retries
        while retries:
            try:
                public_document = self.db.get(self.auction_doc_id)
                if public_document:
                    LOGGER.info("Get auction document {0[_id]} with rev {0[_rev]}".format(public_document),
                                extra={"JOURNAL_REQUEST_ID": self.request_id,
                                       "MESSAGE_ID": AUCTION_WORKER_DB_GET_DOC})
                    if not hasattr(self, 'auction_document'):
                        self.auction_document = public_document
                    if force:
                        return public_document
                    elif public_document['_rev'] != self.auction_document['_rev']:
                        LOGGER.warning("Rev error")
                        self.auction_document["_rev"] = public_document["_rev"]
                    LOGGER.debug(json.dumps(self.auction_document, indent=4))
                return public_document

            except HTTPError, e:
                LOGGER.error("Error while get document: {}".format(e),
                             extra={'MESSAGE_ID': AUCTION_WORKER_DB_GET_DOC_ERROR})
            except Exception, e:
                ecode = e.args[0]
                if ecode in RETRYABLE_ERRORS:
                    LOGGER.error("Error while get document: {}".format(e),
                                 extra={'MESSAGE_ID': AUCTION_WORKER_DB_GET_DOC_ERROR})
                else:
                    LOGGER.critical("Unhandled error: {}".format(e),
                                    extra={'MESSAGE_ID': AUCTION_WORKER_DB_GET_DOC_UNHANDLED_ERROR})
            retries -= 1

    def save_auction_document(self, auction_document):
        self.generate_request_id()
        public_document = auction_document
        retries = self.db_request_retries
        while retries:
            try:
                response = self.db.save(public_document)
                if len(response) == 2:
                    LOGGER.info("Saved auction document {0} with rev {1}".format(*response),
                                extra={"JOURNAL_REQUEST_ID": self.request_id,
                                       "MESSAGE_ID": AUCTION_WORKER_DB_SAVE_DOC})
                    self.auction_document['_rev'] = response[1]
                    return response
            except HTTPError, e:
                LOGGER.error("Error while save document: {}".format(e),
                             extra={'MESSAGE_ID': AUCTION_WORKER_DB_SAVE_DOC_ERROR})
            except Exception, e:
                ecode = e.args[0]
                if ecode in RETRYABLE_ERRORS:
                    LOGGER.error("Error while save document: {}".format(e),
                                 extra={'MESSAGE_ID': AUCTION_WORKER_DB_SAVE_DOC_ERROR})
                else:
                    LOGGER.critical("Unhandled error: {}".format(e),
                                    extra={'MESSAGE_ID': AUCTION_WORKER_DB_SAVE_DOC_UNHANDLED_ERROR})
            if "_rev" in public_document:
                LOGGER.debug("Retry save document changes")
            saved_auction_document = self.get_auction_document(force=True)
            public_document["_rev"] = saved_auction_document["_rev"]
            retries -= 1


class BiddersServiceMixin(object):
    """Mixin class to work with bids data"""
    _bids_data = []

    def add_bid(self, round_id, bid):
        if round_id not in self._bids_data:
            self._bids_data[round_id] = []
        self._bids_data[round_id].append(bid)

    def filter_bids_keys(self, bids):
        filtered_bids_data = []
        for bid_info in bids:
            bid_info_result = {key: bid_info[key] for key in BIDS_KEYS_FOR_COPY}
            bid_info_result["bidder_name"] = self.mapping[bid_info_result['bidder_id']]
            filtered_bids_data.append(bid_info_result)
        return filtered_bids_data

    def approve_bids_information(self):
        pass


class AuctionAPIServiceMixin(
    RequestIDServiceMixin,
    AuditServiceMixin,
):
    auction_doc_id = ''
    with_document_service = False
    tender_url = ''
    api_token = ''
    session = None

    def put_auction_data(self, auction_document):
        if self.with_document_service:
            doc_id = self.upload_audit_file_with_document_service()
        else:
            doc_id = self.upload_audit_file_without_document_service()

        results = post_results_data(self)

        if results:
            bids_information = filter_bids(results)
            set_bids_information(self, auction_document, bids_information)

            if doc_id and bids_information:
                self.approve_audit_info_on_announcement(approved=bids_information)
                if self.with_document_service:
                    doc_id = self.upload_audit_file_with_document_service(doc_id)
                else:
                    doc_id = self.upload_audit_file_without_document_service(doc_id)

                return True
        else:
            LOGGER.info(
                "Auctions results not approved",
                extra={"JOURNAL_REQUEST_ID": self.request_id,
                       "MESSAGE_ID": AUCTION_WORKER_API_AUCTION_RESULT_NOT_APPROVED}
            )

    def get_auction_data(self):
        self.generate_request_id()
        results = get_tender_data(
            self.tender_url,
            user=self.api_token,
            request_id=self.request_id,
            session=self.session
        )

        return results


class StagesServiceMixin(object):

    def prepare_auction_stages(self):
        pass

    def next_stage(self, switch_to_round=None):
        pass
