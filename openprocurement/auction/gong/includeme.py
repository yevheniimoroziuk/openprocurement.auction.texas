from openprocurement.auction.includeme import _register
from openprocurement.auction.interfaces import IAuctionsServer
from openprocurement.auction.gong.views import includeme


def kadastralProcedure(components):
    _register(components, 'kadastralProcedure')
    server = components.queryUtility(IAuctionsServer)
    includeme(server)
