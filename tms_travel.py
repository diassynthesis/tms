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
from tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, float_compare
import decimal_precision as dp
from osv.orm import browse_record, browse_null
import time
from datetime import datetime, date
import openerp


# Trips / travels
class tms_travel(osv.osv):
    _name ='tms.travel'
    _description = 'Travels'
    
    
    def _route_data(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        for record in self.browse(cr, uid, ids, context=context):
            res[record.id] = {
                'distance_route': 0.0,
                'fuel_efficiency_expected': 0.0,
            }
            
            distance  = record.route_id.distance
            fuel_efficiency_expected = record.route_id.fuel_efficiency_drive_unit if not record.trailer1_id else record.route_id.fuel_efficiency_1trailer if not record.trailer2_id else record.route_id.fuel_efficiency_2trailer
            
            res[record.id] = {
                'distance_route': distance,
                'fuel_efficiency_expected': fuel_efficiency_expected,
            }
        return res

    
    
    def _travel_duration(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        for record in self.browse(cr, uid, ids, context=context):
            res[record.id] = {
                'travel_duration': 0.0,
                'travel_duration_real': 0.0,
            }
            dur1 = datetime.strptime(record.date_end, '%Y-%m-%d %H:%M:%S') - datetime.strptime(record.date_start, '%Y-%m-%d %H:%M:%S')
            dur2 = datetime.strptime(record.date_end_real, '%Y-%m-%d %H:%M:%S') - datetime.strptime(record.date_start_real, '%Y-%m-%d %H:%M:%S')
            x1 = ((dur1.days * 24.0*60.0*60.0) + dur1.seconds) / 3600.0 if dur1 else 0.0
            x2 = ((dur2.days * 24.0*60.0*60.0) + dur2.seconds) / 3600.0 if dur2 else 0.0
            res[record.id]['travel_duration'] = x1
            res[record.id]['travel_duration_real'] = x2
        return res

    def _get_framework(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        for record in self.browse(cr, uid, ids, context=context):
            if record.trailer2_id.id and record.trailer1_id.id:
                res[record.id] = {
                    'framework': 'Double',
                    'framework_count': 2,
                    }
            elif record.trailer1_id.id:
                res[record.id] = {
                    'framework': 'Single',
                    'framework_count': 1,
                    }
            else:
                res[record.id] = {
                    'framework': 'Unit',
                    'framework_count': 0,
                    }
        return res
    
    _columns = {
        'shop_id': openerp.osv.fields.many2one('sale.shop', 'Shop', required=True, readonly=False, states={'cancel':[('readonly',True)], 'ended':[('readonly',True)], 'closed':[('readonly',True)]}),
        'company_id': openerp.osv.fields.related('shop_id','company_id',type='many2one',relation='res.company',string='Company',store=True,readonly=True),
        'name': openerp.osv.fields.char('Travel Number', size=64, required=False),
        'state': openerp.osv.fields.selection([('draft','Pending'), ('progress','In Progress'), ('ended','Ended'), ('closed','Closed'), ('cancel','Cancelled')], 'State', readonly=True),
        'route_id': openerp.osv.fields.many2one('tms.route', 'Route', required=True, states={'cancel':[('readonly',True)], 'closed':[('readonly',True)]}),
        'kit_id': openerp.osv.fields.many2one('tms.unit.kit', 'Kit', required=False, states={'cancel':[('readonly',True)], 'closed':[('readonly',True)]}),
        'unit_id': openerp.osv.fields.many2one('tms.unit', 'Transportation Unit', required=True, domain=[('fleet_type', '=', 'tractor')], states={'cancel':[('readonly',True)], 'closed':[('readonly',True)]}),
        'trailer1_id': openerp.osv.fields.many2one('tms.unit', 'Trailer1', required=False,  domain=[('fleet_type', '=', 'trailer')], states={'cancel':[('readonly',True)], 'closed':[('readonly',True)]}),
        'dolly_id': openerp.osv.fields.many2one('tms.unit', 'Dolly', required=False,        domain=[('fleet_type', '=', 'dolly')],   states={'cancel':[('readonly',True)], 'closed':[('readonly',True)]}),
        'trailer2_id': openerp.osv.fields.many2one('tms.unit', 'Trailer2', required=False,  domain=[('fleet_type', '=', 'trailer')], states={'cancel':[('readonly',True)], 'closed':[('readonly',True)]}),
        'employee_id': openerp.osv.fields.many2one('hr.employee', 'Driver', required=True, domain=[('tms_category', '=', 'driver')], states={'cancel':[('readonly',True)], 'closed':[('readonly',True)]}),
        'employee2_id': openerp.osv.fields.many2one('hr.employee', 'Driver 2', required=False, domain=[('tms_category', '=', 'driver')], states={'cancel':[('readonly',True)], 'closed':[('readonly',True)]}),
        'date': openerp.osv.fields.datetime('Date registered',required=True, states={'cancel':[('readonly',True)], 'closed':[('readonly',True)]}),
        'date_start': openerp.osv.fields.datetime('Start Sched',required=False, states={'cancel':[('readonly',True)], 'closed':[('readonly',True)]}),
        'date_end': openerp.osv.fields.datetime('End Sched',required=False, states={'cancel':[('readonly',True)], 'closed':[('readonly',True)]}),
        'date_start_real': openerp.osv.fields.datetime('Start Real',required=False, states={'cancel':[('readonly',True)], 'closed':[('readonly',True)]}),
        'date_end_real': openerp.osv.fields.datetime('End Real',required=False, states={'cancel':[('readonly',True)], 'closed':[('readonly',True)]}),
        'travel_duration': openerp.osv.fields.function(_travel_duration, string='Duration Sched', method=True, store=True, type='float', digits=(18,6), multi='travel_duration', 
                                                            help="Travel Scheduled duration in hours"),
        'travel_duration_real': openerp.osv.fields.function(_travel_duration, string='Duration Real', method=True, store=True, type='float', digits=(18,6), multi='travel_duration',
                                                                help="Travel Real duration in hours"),


        'distance_route': openerp.osv.fields.function(_route_data, string='Route Distance (mi./km)', method=True, store=True, type='float', digits=(18,6), multi='distance_route'),
        'fuel_efficiency_expected': openerp.osv.fields.function(_route_data, string='Fuel Efficiency Expected', method=True, store=True, type='float', digits=(18,6), multi='distance_route'),

        'distance_driver': openerp.osv.fields.float('Distance traveled by driver (mi./km)', required=False, digits=(14,4), states={'cancel':[('readonly',True)], 'closed':[('readonly',True)]}),
        'distance_loaded': openerp.osv.fields.float('Distance Loaded (mi./km)', required=False, digits=(14,4), states={'cancel':[('readonly',True)], 'closed':[('readonly',True)]}),
        'distance_empty': openerp.osv.fields.float('Distance Empty (mi./km)', required=False, digits=(14,4), states={'cancel':[('readonly',True)], 'closed':[('readonly',True)]}),
        'distance_extraction': openerp.osv.fields.float('Distance Extraction (mi./km)', required=False, digits=(14,4), states={'cancel':[('readonly',True)], 'closed':[('readonly',True)]}),
        
        'fuel_efficiency_travel': openerp.osv.fields.float('Fuel Efficiency Travel', required=False, digits=(14,4), states={'cancel':[('readonly',True)], 'closed':[('readonly',True)]}),
        'fuel_efficiency_extraction': openerp.osv.fields.float('Fuel Efficiency Extraction', required=False, digits=(14,4), states={'cancel':[('readonly',True)], 'closed':[('readonly',True)]}),
        'departure': openerp.osv.fields.related('route_id', 'departure_id', type='many2one', relation='tms.place', string='Departure', store=True, readonly=True),                
        'arrival': openerp.osv.fields.related('route_id', 'arrival_id', type='many2one', relation='tms.place', string='Arrival', store=True, readonly=True),                
#        'loaded': openerp.osv.fields.boolean('Cargado'),
#        'income': openerp.osv.fields.function(_get_income, method=True, string='To', type='float', digits=(14,4)),
        'notes': openerp.osv.fields.text('Descripción', required=False, states={'cancel':[('readonly',True)], 'closed':[('readonly',True)]}),

        'expense_id': openerp.osv.fields.many2one('tms.expense', 'Travel Expenses Record', required=False),
        'fuelvoucher_ids':openerp.osv.fields.one2many('tms.fuelvoucher', 'travel_id', string='Fuel Vouchers', states={'cancel':[('readonly',True)], 'closed':[('readonly',True)]}),
        'advance_ids':openerp.osv.fields.one2many('tms.advance', 'travel_id', string='Advances', states={'cancel':[('readonly',True)], 'closed':[('readonly',True)]}),
        'framework': openerp.osv.fields.function(_get_framework, string='Framework', method=True, store=True, type='char', size=15, multi='framework'),
        'framework_count': openerp.osv.fields.function(_get_framework, string='Framework Count', method=True, store=True, type='integer', multi='framework'),

        'create_uid' : openerp.osv.fields.many2one('res.users', 'Created by', readonly=True),
        'create_date': openerp.osv.fields.datetime('Creation Date', readonly=True, select=True),
        'cancelled_by' : openerp.osv.fields.many2one('res.users', 'Cancelled by', readonly=True),
        'date_cancelled': openerp.osv.fields.datetime('Date Cancelled', readonly=True),
        'dispatched_by' : openerp.osv.fields.many2one('res.users', 'Dispatched by', readonly=True),
        'date_dispatched': openerp.osv.fields.datetime('Date Dispatched', readonly=True),
        'ended_by' : openerp.osv.fields.many2one('res.users', 'Ended by', readonly=True),
        'date_ended': openerp.osv.fields.datetime('Date Ended', readonly=True),
        'closed_by' : openerp.osv.fields.many2one('res.users', 'Closed by', readonly=True),
        'date_closed': openerp.osv.fields.datetime('Date Closed', readonly=True),
        'drafted_by' : openerp.osv.fields.many2one('res.users', 'Drafted by', readonly=True),
        'date_drafted': openerp.osv.fields.datetime('Date Drafted', readonly=True),

        }


    _defaults = {
        'date': lambda *a: time.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
        'date_start': lambda *a: time.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
        'date_end': lambda *a: time.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
        'date_start_real': lambda *a: time.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
        'date_end_real': lambda *a: time.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
        'state': 'draft',
        }
    
    _sql_constraints = [
        ('name_uniq', 'unique(shop_id,name)', 'Travel number must be unique !'),
        ]
    _order = "date desc"
        

    def onchange_kit_id(self, cr, uid, ids, kit_id):
        if not kit_id:
            return {}        
        kit = self.pool.get('tms.unit.kit').browse(cr, uid, kit_id)
        return {'value' : {'unit_id': kit.unit_id.id, 'trailer1_id': kit.trailer1_id.id, 'dolly_id': kit.dolly_id.id, 'trailer2_id': kit.trailer2_id.id}}

    
    def onchange_route_id(self, cr, uid, ids, route_id, unit_id, trailer1_id, dolly_id, trailer2_id):
        if not route_id:
            return {'value': {'distance_route': 0.00, 'fuel_efficiency_expected': 0.00}}
        
        route = self.pool.get('tms.route').browse(cr, uid, route_id)
        distance  = route.distance
        fuel_efficiency_expected = route.fuel_efficiency_drive_unit if not trailer1_id else route.fuel_efficiency_1trailer if not trailer2_id else route.fuel_efficiency_2trailer
        val = {
            'distance_route': distance,
            'fuel_efficiency_expected': fuel_efficiency_expected,
        }
        return {'value': val}

    def onchange_dates(self, cr, uid, ids, date_start, date_end, date_start_real, date_end_real):
        if not date_start or not date_end or not date_start_real or not date_end_real:
            return {'value': {'travel_duration': 0.0, 'travel_duration_real': 0.0}}
        
        dur1 = datetime.strptime(date_end, '%Y-%m-%d %H:%M:%S') - datetime.strptime(date_start, '%Y-%m-%d %H:%M:%S')
        dur2 = datetime.strptime(date_end_real, '%Y-%m-%d %H:%M:%S') - datetime.strptime(date_start_real, '%Y-%m-%d %H:%M:%S')
        x1 = ((dur1.days * 24.0*60.0*60.0) + dur1.seconds) / 3600.0
        x2 = ((dur2.days * 24.0*60.0*60.0) + dur2.seconds) / 3600.0
        val = {
            'travel_duration': x1,
            'travel_duration_real': x2,
        }        
        return {'value': val}


    def create(self, cr, uid, vals, context=None):
        shop = self.pool.get('sale.shop').browse(cr, uid, vals['shop_id'])
        seq_id = shop.tms_travel_seq.id
        if shop.tms_travel_seq:
            seq_number = self.pool.get('ir.sequence').get_id(cr, uid, seq_id)
            vals['name'] = seq_number
        else:
            raise osv.except_osv(_('Travel Sequence Error !'), _('You have not defined Travel Sequence for shop ' + shop.name))
        return super(tms_travel, self).create(cr, uid, vals, context=context)

    def action_cancel_draft(self, cr, uid, ids, *args):
        if not len(ids):
            return False
        self.write(cr, uid, ids, {'state':'draft','drafted_by':uid,'date_drafted':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
        for (id,name) in self.name_get(cr, uid, ids):
            message = _("Travel '%s' has been set in draft state.") % name
            self.log(cr, uid, id, message)
        return True
    
    def action_cancel(self, cr, uid, ids, context=None):
        for travel in self.browse(cr, uid, ids, context=context):
            for fuelvouchers in travel.fuelvoucher_ids:
                if fuelvouchers.state not in ('cancel'):
                    raise osv.except_osv(
                        _('Could not cancel Travel !'),
                        _('You must first cancel all Fuel Vouchers attached to this Travel.'))
            for waybills in travel.waybill_ids:
                if waybills.state not in ('cancel'):
                    raise osv.except_osv(
                        _('Could not cancel Travel !'),
                        _('You must first cancel all Waybills attached to this Travel.'))
            
            for advances in travel.advance_ids:
                if advances.state not in ('cancel'):
                    raise osv.except_osv(
                        _('Could not cancel Travel !'),
                        _('You must first cancel all Advances for Drivers attached to this Travel.'))
            self.write(cr, uid, ids, {'state':'cancel', 'cancelled_by':uid,'date_cancelled':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
        for (id,name) in self.name_get(cr, uid, ids):
            message = _("Travel '%s' is cancelled.") % name
            self.log(cr, uid, id, message)
        return True

    def action_dispatch(self, cr, uid, ids, context=None):
        for travel in self.browse(cr, uid, ids, context=context):
            unit = travel.unit_id.id
            travels = self.pool.get('tms.travel')
            travel_id = travels.search(cr, uid, [('unit_id', '=', unit),('state', '=', 'progress')])
            if travel_id:
                raise osv.except_osv(
                        _('Could not dispatch Travel !'),
                        _('There is already a Travel in progress with Unit ' + travel.unit_id.name))
        self.write(cr, uid, ids, {  'state':'progress',
                                    'dispatched_by':uid,
                                    'date_dispatched':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                                    'date_start_real':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
        for (id,name) in self.name_get(cr, uid, ids):
            message = _("Travel '%s' is set to progress.") % name
            self.log(cr, uid, id, message)
        return True

    def action_end(self, cr, uid, ids, context=None):

        self.write(cr,uid,ids,{ 'state':'ended',
                                'ended_by':uid,
                                'date_ended':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                                'date_end_real':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
        for (id,name) in self.name_get(cr, uid, ids):
            message = _("Travel '%s' is ended.") % name
            self.log(cr, uid, id, message)
        return True

tms_travel()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
