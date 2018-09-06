# -*- coding: utf-8 -*-
from openprocurement.auction.includeme import _register


def texasProcedure(components, procurement_method_types):
    for procurementMethodType in procurement_method_types:
        _register(components, procurementMethodType)
