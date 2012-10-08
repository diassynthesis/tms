# -*- encoding: utf-8 -*-
##############################################################################
#    
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.     
#
##############################################################################


from osv import osv, fields
import netsvc
import pooler
from tools.translate import _
import decimal_precision as dp
from osv.orm import browse_record, browse_null
import time
from tools.translate import _
from tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, float_compare
from datetime import datetime, date
import openerp




# Events category
class tms_event_category(osv.osv):
    _name = "tms.event.category"
    _description = "Events categories"

    def name_get(self, cr, uid, ids, context=None):
        if not len(ids):
            return []
        reads = self.read(cr, uid, ids, ['name','parent_id'], context=context)
        res = []
        for record in reads:
            name = record['name']
            if record['parent_id']:
                name = record['parent_id'][1]+' / '+name
            res.append((record['id'], name))
        return res

    def _name_get_fnc(self, cr, uid, ids, prop, unknow_none, context=None):
        res = self.name_get(cr, uid, ids, context=context)
        return dict(res)

    _columns = {
        'name': openerp.osv.fields.char('Name', size=30, required=True, translate=True),
        'complete_name': openerp.osv.fields.function(_name_get_fnc, method=True, type="char", size=300, string='Complete Name', store=True),
        'parent_id': openerp.osv.fields.many2one('tms.event.category','Parent Category', select=True),
        'child_id': openerp.osv.fields.one2many('tms.event.category', 'parent_id', string='Child Categories'),
        'notes': openerp.osv.fields.text('Notes'),
        'active': openerp.osv.fields.boolean('Active'),
        'company_id': openerp.osv.fields.many2one('res.company', 'Company', required=False),
    }

    _defaults = {
        'active': True,
    }

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Category name must be unique !'),
        ]

    _order = "name"
    
    def _check_recursion(self, cr, uid, ids, context=None):
        level = 100
        while len(ids):
            cr.execute('select distinct parent_id from tms_event_category where id IN %s',(tuple(ids),))
            ids = filter(None, map(lambda x:x[0], cr.fetchall()))
            if not level:
                return False
            level -= 1
        return True

    _constraints = [
        (_check_recursion, 'Error ! You can not create recursive categories.', ['parent_id'])
    ]

    def child_get(self, cr, uid, ids):
        return [ids]

tms_event_category()


# Events
class tms_event(osv.osv):
    _name = "tms.event"
    _description = "Events"

    _columns = {
        'name': openerp.osv.fields.char('Description', size=250, required=True),
        'date': openerp.osv.fields.datetime('Date event', required=True),
        'category_id': openerp.osv.fields.many2one('tms.event.category','Category', select=True, required=True),
        'notes': openerp.osv.fields.text('Notes'),
        'travel_id': openerp.osv.fields.many2one('tms.travel','Travel', select=True, required=True),
        'unit_id': openerp.osv.fields.related('travel_id', 'unit_id', type='many2one', relation='tms.unit', string='Unit', store=True, readonly=True),                
        'trailer1_id': openerp.osv.fields.related('travel_id', 'trailer1_id', type='many2one', relation='tms.unit', string='Trailer 1', store=True, readonly=True),                
        'dolly_id': openerp.osv.fields.related('travel_id', 'dolly_id', type='many2one', relation='tms.unit', string='Dolly', store=True, readonly=True),                
        'trailer2_id': openerp.osv.fields.related('travel_id', 'trailer2_id', type='many2one', relation='tms.unit', string='Trailer 2', store=True, readonly=True),                
        'employee_id': openerp.osv.fields.related('travel_id', 'employee_id', type='many2one', relation='hr.employee', string='Driver', store=True, readonly=True),                
        'route_id': openerp.osv.fields.related('travel_id', 'route_id', type='many2one', relation='tms.route', string='Route', store=True, readonly=True),                
        'departure_id': openerp.osv.fields.related('route_id', 'departure_id', type='many2one', relation='tms.place', string='Departure', store=True, readonly=True),                
        'arrival_id': openerp.osv.fields.related('route_id', 'arrival_id', type='many2one', relation='tms.place', string='Arrival', store=True, readonly=True),                
#        'waybill_id': openerp.osv.fields.many2one('tms.waybill','Travel', select=True, required=False),
        'shop_id': openerp.osv.fields.related('travel_id', 'shop_id', type='many2one', relation='sale.shop', string='Shop', store=True, readonly=True),                
        'company_id': openerp.osv.fields.related('shop_id', 'company_id', type='many2one', relation='res.company', string='Company', store=True, readonly=True),                
    }

    _defaults = {
        'date'            : lambda *a: time.strftime( DEFAULT_SERVER_DATETIME_FORMAT),
    }

    _order = "date, category_id"
    
tms_event()


# Adding relation between Travels and Events
class tms_travel(osv.osv):
    _inherit="tms.travel"

    _columns = {
        'event_ids': openerp.osv.fields.one2many('tms.event', 'travel_id', string='Events'),
    }

tms_travel()




# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

