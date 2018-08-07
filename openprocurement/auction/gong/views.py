from openprocurement.auction.auctions_server import auctions_proxy


def includeme(app):
    app.add_url_rule('/auctions/<auction_doc_id>/<path:path>', 'auctions',
                     auctions_proxy,
                     methods=['GET', 'POST'])
