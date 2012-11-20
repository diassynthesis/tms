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
import time
from datetime import datetime, date
from tools.translate import _
from tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, float_compare
import decimal_precision as dp
import netsvc
import openerp
from pytz import timezone

 # TMS Waybills
class tms_waybill(osv.osv):
    _name = 'tms.waybill'
    _description = 'Waybills'


#    def _get_order(self, cr, uid, ids, context=None):
#        result = {}
#        for line in self.pool.get('tms.waybill.line').browse(cr, uid, ids, context=context):
#            result[line.waybill_id.id] = True
#        return result.keys()


#    def _amount_line_tax(self, cr, uid, line, tax_type, context=None):
#        val = 0.0
#        for c in self.pool.get('account.tax').compute_all_tax_and_retention(cr, uid, line.tax_id, line.price_unit, 
#                               line.product_uom_qty, tax_type)['taxes']:
#            val += c.get('res', 0.0)
#        return val

    def _amount_all(self, cr, uid, ids, field_name, arg, context=None):
        print "_amount_all"
        cur_obj = self.pool.get('res.currency')
        res = {}
        for waybill in self.browse(cr, uid, ids, context=context):
            res[waybill.id] = {
                'amount_freight': 0.0,
                'amount_freight': 0.0,
                'amount_move': 0.0,
                'amount_highway_tolls': 0.0,
                'amount_insurance': 0.0,
                'amount_other': 0.0,
                'amount_subtotal': 0.0,
                'amount_tax': 0.0,
                'amount_total': 0.0,
            }
            cur = waybill.pricelist_id.currency_id
            x_freight = x_move = x_highway = x_insurance = x_other = x_subtotal = x_tax  = x_total = 0.0
            for line in waybill.waybill_line:
                    x_freight += line.price_subtotal if line.product_id.tms_category == 'freight' else 0.0
                    x_move += line.price_subtotal if line.product_id.tms_category == 'move' else 0.0
                    x_highway += line.price_subtotal if line.product_id.tms_category == 'highway_tolls' else 0.0
                    x_insurance += line.price_subtotal if line.product_id.tms_category == 'insurance' else 0.0
                    x_other += line.price_subtotal if line.product_id.tms_category == 'other' else 0.0
                    x_subtotal += line.price_subtotal
                    x_tax += line.tax_amount
                    x_total += line.price_total
        
            res[waybill.id] = { 'amount_freight'   : cur_obj.round(cr, uid, cur, x_freight),
                                'amount_move'       : cur_obj.round(cr, uid, cur, x_move),
                                'amount_highway_tolls'    : cur_obj.round(cr, uid, cur, x_highway),
                                'amount_insurance'  : cur_obj.round(cr, uid, cur, x_insurance),
                                'amount_other'      : cur_obj.round(cr, uid, cur, x_other),
                                'amount_untaxed'    : cur_obj.round(cr, uid, cur, x_subtotal),
                                'amount_tax'    : cur_obj.round(cr, uid, cur, x_tax),
                                'amount_total'    : cur_obj.round(cr, uid, cur, x_total),

                              }
            
#            x_travel = waybill.payment_factor * (1.0 if waybill.payment_type == 'travel' else
#                                                waybill.distance if waybill.payment_type == 'distance'    else
#                                                waybill.quantity if waybill.payment_type == 'quantity'    else
#                                                waybill.volume   if waybill.payment_type == 'volume'      else
#                                                waybill.tons     if waybill.payment_type == 'tons'        else 0.0
#                                                )
                        
        return res

    def _invoiced(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        for record in self.browse(cr, uid, ids, context=context):
            invoiced = (record.invoice_id.id)
            paid = (record.invoice_id.state == 'paid') if record.invoice_id.id else False
            res[record.id] =  { 'invoiced': invoiced,
                                'invoice_paid': paid,
                                'invoice_name': record.invoice_id.reference
                                }
        return res


    def _shipped_product(self, cr, uid, ids, field_name, args, context=None):
        res = {}

        context_wo_lang = context.copy()
        context_wo_lang.pop('lang', None)
        for waybill in self.browse(cr, uid, ids, context=context_wo_lang):
            volume = weight = qty = 0.0
            for record in waybill.waybill_shipped_product:
                qty += record.product_uom_qty
                print "Waybill - record.product_uom.category_id.name", record.product_uom.category_id.name
                volume += record.product_uom_qty if record.product_uom.category_id.name == 'Volume' else 0.0
                weight += record.product_uom_qty if record.product_uom.category_id.name == 'Weight' else 0.0
                res[waybill.id] =  {'product_qty': qty,
                                    'product_volume': volume,
                                    'product_weight': weight,
                                    'product_uom_type': (record.product_uom.category_id.name),
                                    }
        return res

    def _get_route_distance(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        distance=0.0
        for waybill in self.browse(cr, uid, ids, context=context):
            distance = waybill.route_id.distance
            res[waybill.id] = distance
        return res

    def _get_newer_travel_id(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        travel_id = False
        for waybill in self.browse(cr, uid, ids, context=context):
            for travel in waybill.travel_ids:
                travel_id = travel.id
            res[waybill.id] = travel_id
        return res

    def _get_waybill_type(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        waybill_type = 'self'
        for waybill in self.browse(cr, uid, ids, context=context):
            for travel in waybill.travel_ids:
                waybill_type = 'outsourced' if travel.unit_id.supplier_unit else 'self'
            res[waybill.id] = waybill_type
        return res


    _columns = {
        'name': openerp.osv.fields.char('Name', size=64, readonly=True, select=True),
        'shop_id': openerp.osv.fields.many2one('sale.shop', 'Shop', required=True, readonly=False, states={'confirmed': [('readonly', True)],'closed':[('readonly',True)]}),
        'sequence_id': openerp.osv.fields.many2one('ir.sequence', 'Sequence', required=True, readonly=False, states={'confirmed': [('readonly', True)],'closed':[('readonly',True)]}),
        'travel_ids': openerp.osv.fields.many2many('tms.travel', 'tms_waybill_travel_rel', 'waybill_id', 'travel_id', 'Travels', readonly=False, states={'confirmed': [('readonly', True)],'closed':[('readonly',True)]}),

        'travel_id': openerp.osv.fields.function(_get_newer_travel_id, method=True, relation='tms.travel', type="many2one", string='Actual Travel', readonly=True, store=True),

        'unit_id': openerp.osv.fields.related('travel_id', 'unit_id', type='many2one', relation='tms.unit', string='Unit', store=True, readonly=True),                
        'trailer1_id': openerp.osv.fields.related('travel_id', 'trailer1_id', type='many2one', relation='tms.unit', string='Trailer 1', store=True, readonly=True),                
        'dolly_id': openerp.osv.fields.related('travel_id', 'dolly_id', type='many2one', relation='tms.unit', string='Dolly', store=True, readonly=True),                
        'trailer2_id': openerp.osv.fields.related('travel_id', 'trailer2_id', type='many2one', relation='tms.unit', string='Trailer 2', store=True, readonly=True),                
        'employee_id': openerp.osv.fields.related('travel_id', 'employee_id', type='many2one', relation='hr.employee', string='Driver', store=True, readonly=True),                
        'route_id': openerp.osv.fields.related('travel_id', 'route_id', type='many2one', relation='tms.route', string='Route', store=True, readonly=True),                
        'departure_id': openerp.osv.fields.related('route_id', 'departure_id', type='many2one', relation='tms.place', string='Departure', store=True, readonly=True),                
        'arrival_id': openerp.osv.fields.related('route_id', 'arrival_id', type='many2one', relation='tms.place', string='Arrival', store=True, readonly=True),                

        'origin': openerp.osv.fields.char('Source Document', size=64, help="Reference of the document that generated this Waybill request.",readonly=False, states={'confirmed': [('readonly', True)],'closed':[('readonly',True)]}),
        'client_order_ref': openerp.osv.fields.char('Customer Reference', size=64, readonly=False, states={'confirmed': [('readonly', True)],'closed':[('readonly',True)]}),
        'state': openerp.osv.fields.selection([
            ('draft', 'Pending'),
            ('approved', 'Approved'),
            ('confirmed', 'Confirmed'),
            ('cancel', 'Cancelled')
            ], 'Waybill State', readonly=True, help="Gives the state of the Waybill. \n -The exception state is automatically set when a cancel operation occurs in the invoice validation (Invoice Exception) or in the picking list process (Shipping Exception). \nThe 'Waiting Schedule' state is set when the invoice is confirmed but waiting for the scheduler to run on the date 'Ordered Date'.", select=True),
        'billing_policy': openerp.osv.fields.selection([
            ('manual', 'Manual'),
            ('automatic', 'Automatic'),
            ], 'Billing Policy', readonly=False, states={'confirmed': [('readonly', True)],'closed':[('readonly',True)]},
            help="Gives the state of the Waybill. \n -The exception state is automatically set when a cancel operation occurs in the invoice validation (Invoice Exception) or in the picking list process (Shipping Exception). \nThe 'Waiting Schedule' state is set when the invoice is confirmed but waiting for the scheduler to run on the date 'Ordered Date'.", select=True),



        'waybill_type': openerp.osv.fields.function(_get_waybill_type, method=True, type='selection', selection=[('self', 'Self'), ('outsourced', 'Outsourced')], 
                                        string='Waybill Type', store=True, help=" - Self: Travel with our own units. \n - Outsourced: Travel without our own units."),


        'date_order': openerp.osv.fields.date('Date', required=True, select=True,readonly=False, states={'confirmed': [('readonly', True)],'closed':[('readonly',True)]}),
        'user_id': openerp.osv.fields.many2one('res.users', 'Salesman', select=True, readonly=False, states={'confirmed': [('readonly', True)],'closed':[('readonly',True)]}),

        'partner_id': openerp.osv.fields.many2one('res.partner', 'Customer', required=True, change_default=True, select=True, readonly=False, states={'confirmed': [('readonly', True)],'closed':[('readonly',True)]}),
        'pricelist_id': openerp.osv.fields.many2one('product.pricelist', 'Pricelist', required=True, help="Pricelist for Waybill.", readonly=False, states={'confirmed': [('readonly', True)],'closed':[('readonly',True)]}),
        'partner_invoice_id': openerp.osv.fields.many2one('res.partner.address', 'Invoice Address', required=True, help="Invoice address for current Waybill.", readonly=False, states={'confirmed': [('readonly', True)],'closed':[('readonly',True)]}),
        'partner_order_id': openerp.osv.fields.many2one('res.partner.address', 'Ordering Contact', required=True,  help="The name and address of the contact who requested the order or quotation.", readonly=False, states={'confirmed': [('readonly', True)],'closed':[('readonly',True)]}),
        'account_analytic_id': openerp.osv.fields.many2one('account.analytic.account', 'Analytic Account',  help="The analytic account related to a Waybill.", readonly=False, states={'confirmed': [('readonly', True)],'closed':[('readonly',True)]}),
        'departure_address_id': openerp.osv.fields.many2one('res.partner.address', 'Departure Address', required=True, help="Departure address for current Waybill.", readonly=False, states={'confirmed': [('readonly', True)],'closed':[('readonly',True)]}),
        'arrival_address_id': openerp.osv.fields.many2one('res.partner.address', 'Arrival Address', required=True, help="Arrival address for current Waybill.", readonly=False, states={'confirmed': [('readonly', True)],'closed':[('readonly',True)]}),
        'upload_point': openerp.osv.fields.char('Upload Point', size=128, readonly=False, states={'confirmed': [('readonly', True)],'closed':[('readonly',True)]}),
        'download_point': openerp.osv.fields.char('Download Point', size=128, required=False, readonly=False, states={'confirmed': [('readonly', True)],'closed':[('readonly',True)]}),
        'shipped': openerp.osv.fields.boolean('Delivered', readonly=True, help="It indicates that the Waybill has been delivered. This field is updated only after the scheduler(s) have been launched."),

        'invoice_id': openerp.osv.fields.many2one('account.invoice','Invoice Record', readonly=True),
        'invoiced':  openerp.osv.fields.function(_invoiced, method=True, string='Invoiced', type='boolean', multi='invoiced', store=True),
        'invoice_paid':  openerp.osv.fields.function(_invoiced, method=True, string='Paid', type='boolean', multi='invoiced', store=True),
        'invoice_name':  openerp.osv.fields.function(_invoiced, method=True, string='Invoice', type='char', size=64, multi='invoiced', store=True),

        'waybill_line': openerp.osv.fields.one2many('tms.waybill.line', 'waybill_id', 'Waybill Lines', readonly=False, states={'confirmed': [('readonly', True)],'closed':[('readonly',True)]}),
        'waybill_shipped_product': openerp.osv.fields.one2many('tms.waybill.shipped_product', 'waybill_id', 'Shipped Products', readonly=False, states={'confirmed': [('readonly', True)],'closed':[('readonly',True)]}),
        'product_qty':openerp.osv.fields.function(_shipped_product, method=True, string='Sum Qty', type='float', digits=(20, 6),  store=True, multi='product_qty'),
        'product_volume':openerp.osv.fields.function(_shipped_product, method=True, string='Sum Volume', type='float', digits=(20, 6),  store=True, multi='product_qty'),
        'product_weight':openerp.osv.fields.function(_shipped_product, method=True, string='Sum Weight', type='float', digits=(20, 6),  store=True, multi='product_qty'),
        'product_uom_type':openerp.osv.fields.function(_shipped_product, method=True, string='Product UoM Type', type='char', size=64, store=True, multi='product_qty'),

        'waybill_extradata': openerp.osv.fields.one2many('tms.waybill.extradata', 'waybill_id', 'Extra Data Fields', readonly=False, states={'confirmed': [('readonly', True)],'closed':[('readonly',True)]}),


        'amount_freight': openerp.osv.fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Freight', type='float',
                                            store=True, multi='amount_freight'),
        'amount_move': openerp.osv.fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Moves', type='float',
                                            store=True, multi='amount_freight'),
        'amount_highway_tolls': openerp.osv.fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Highway Tolls', type='float',
                                            store=True, multi='amount_freight'),
        'amount_insurance': openerp.osv.fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Insurance', type='float',
                                            store=True, multi='amount_freight'),
        'amount_other': openerp.osv.fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Other', type='float',
                                            store=True, multi='amount_freight'),
        'amount_untaxed': openerp.osv.fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='SubTotal', type='float',
                                            store=True, multi='amount_freight'),
        'amount_tax': openerp.osv.fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Taxes', type='float',
                                            store=True, multi='amount_freight'),

        'amount_total': openerp.osv.fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Total', type='float',
                                            store=True, multi='amount_freight'),



        'distance_route': openerp.osv.fields.function(_get_route_distance, string='Distance from route', method=True, type='float', digits=(18,6), help="Route Distance.", multi=False),
        'distance_real':  openerp.osv.fields.float('Distance Real', digits=(18,6), help="Route obtained by electronic reading"),
       
        'create_uid' : openerp.osv.fields.many2one('res.users', 'Created by', readonly=True),
        'create_date': openerp.osv.fields.datetime('Creation Date', readonly=True, select=True),
        'cancelled_by' : openerp.osv.fields.many2one('res.users', 'Cancelled by', readonly=True),
        'date_cancelled': openerp.osv.fields.datetime('Date Cancelled', readonly=True),
        'approved_by' : openerp.osv.fields.many2one('res.users', 'Approved by', readonly=True),
        'date_approved': openerp.osv.fields.datetime('Date Approved', readonly=True),
        'confirmed_by' : openerp.osv.fields.many2one('res.users', 'Confirmed by', readonly=True),
        'date_confirmed': openerp.osv.fields.datetime('Date Confirmed', readonly=True),
        'drafted_by' : openerp.osv.fields.many2one('res.users', 'Drafted by', readonly=True),
        'date_drafted': openerp.osv.fields.datetime('Date Drafted', readonly=True),

        'notes': openerp.osv.fields.text('Notes', readonly=False, states={'confirmed': [('readonly', True)],'closed':[('readonly',True)]}),

        
        'payment_term': openerp.osv.fields.many2one('account.payment.term', 'Payment Term', readonly=False, states={'confirmed': [('readonly', True)],'closed':[('readonly',True)]}),
        'fiscal_position': openerp.osv.fields.many2one('account.fiscal.position', 'Fiscal Position', readonly=False, states={'confirmed': [('readonly', True)],'closed':[('readonly',True)]}),
        'company_id': openerp.osv.fields.related('shop_id','company_id',type='many2one',relation='res.company',string='Company',store=True,readonly=True),


        'date_start': openerp.osv.fields.datetime('Load Date Sched', required=False, help="Date Start time for Load"),
        'date_up_start_sched': openerp.osv.fields.datetime('UpLd Start Sched', required=False),
        'date_up_end_sched': openerp.osv.fields.datetime('UpLd End Sched', required=False),
        'date_up_docs_sched': openerp.osv.fields.datetime('UpLd Docs Sched', required=False),
        'date_appoint_down_sched': openerp.osv.fields.datetime('Download Date Sched', required=False),
        'date_down_start_sched': openerp.osv.fields.datetime('Download Start Sched', required=False),
        'date_down_end_sched': openerp.osv.fields.datetime('Download End Sched', required=False),
        'date_down_docs_sched': openerp.osv.fields.datetime('Download Docs Sched', required=False),
        'date_end': openerp.osv.fields.datetime('Travel End Sched', required=False, help="Date End time for Load"),        

        'date_start_real': openerp.osv.fields.datetime('Load Date Real', required=False),
        'date_up_start_real': openerp.osv.fields.datetime('UpLoad Start Real', required=False),
        'date_up_end_real': openerp.osv.fields.datetime('UpLoad End Real', required=False),
        'date_up_docs_real': openerp.osv.fields.datetime('Load Docs Real', required=False),
        'date_appoint_down_real': openerp.osv.fields.datetime('Download Date Real', required=False),
        'date_down_start_real': openerp.osv.fields.datetime('Download Start Real', required=False),
        'date_down_end_real': openerp.osv.fields.datetime('Download End Real', required=False),
        'date_down_docs_real': openerp.osv.fields.datetime('Download Docs Real', required=False),
        'date_end_real': openerp.osv.fields.datetime('Travel End Real', required=False),



        
#        'time_from_appointment_to_uploading_std': openerp.osv.fields.float('Std Time from Appointment to Loading (Hrs)', digits=(10, 2), required=True, readonly=False),
#        'time_for_uploading_std': openerp.osv.fields.float('Std Time for loading (Hrs)', digits=(10, 2), required=True, readonly=False),
#        'time_from_uploading_to_docs_sched': openerp.osv.fields.float('Std Time from Load to Document Release (Hrs)', digits=(10, 2), required=True, readonly=False),
#        'time_travel_sched': openerp.osv.fields.float('Std Time for Travel (Hrs)', digits=(10, 2), required=True, readonly=False),
#        'time_from_appointment_to_downloading_std': openerp.osv.fields.float('Std Time from Download Appointment to Downloading (Hrs)', digits=(10, 2), required=True, readonly=False),
#        'time_for_downloading_sched': openerp.osv.fields.float('Std Time for downloading (Hrs)', digits=(10, 2), required=True, readonly=False),
#        'time_from_downloading_to_docs_sched': openerp.osv.fields.float('Std Time for Download Document Release (Hrs)', digits=(10, 2), required=True, readonly=False),                                                                                                        

        
#        'payment_type': openerp.osv.fields.selection([
#                                          ('quantity','Charge by Quantity'), 
#                                          ('tons','Charge by Tons'), 
#                                          ('distance','Charge by Distance (mi./kms)'), 
#                                          ('travel','Charge by Travel'), 
#                                          ('volume', 'Charge by Volume'),
#                                          ], 'Charge Type',required=True,),
#        'payment_factor': openerp.osv.fields.float('Factor', digits=(16, 4), required=True),
#      
        'amount_declared' : openerp.osv.fields.float('Amount Declared', digits_compute= dp.get_precision('Sale Price'), help=" Load value amount declared for insurance purposes..."),
        'replaced_waybill_id' : openerp.osv.fields.many2one('tms.waybill', 'Replaced Waybill', readonly=True),

    }
    _defaults = {
        'date_order'            : lambda *a: time.strftime(DEFAULT_SERVER_DATE_FORMAT),
        'date_start'            : lambda *a: time.strftime( DEFAULT_SERVER_DATETIME_FORMAT),
        'date_up_start_sched'   : lambda *a: time.strftime( DEFAULT_SERVER_DATETIME_FORMAT),
        'date_up_end_sched'     : lambda *a: time.strftime( DEFAULT_SERVER_DATETIME_FORMAT),
        'date_up_docs_sched'    : lambda *a: time.strftime( DEFAULT_SERVER_DATETIME_FORMAT),
        'date_appoint_down_sched': lambda *a: time.strftime( DEFAULT_SERVER_DATETIME_FORMAT),
        'date_down_start_sched' : lambda *a: time.strftime( DEFAULT_SERVER_DATETIME_FORMAT),
        'date_down_end_sched'   : lambda *a: time.strftime( DEFAULT_SERVER_DATETIME_FORMAT),
        'date_down_docs_sched'  : lambda *a: time.strftime( DEFAULT_SERVER_DATETIME_FORMAT),
        'date_end'              : lambda *a: time.strftime( DEFAULT_SERVER_DATETIME_FORMAT),
        'billing_policy'        : 'manual',
        'state'                 : lambda *a: 'draft',
        'waybill_type'          : 'self',
        'user_id'               : lambda obj, cr, uid, context: uid,
        'partner_invoice_id'    : lambda self, cr, uid, context: context.get('partner_id', False) and self.pool.get('res.partner').address_get(cr, uid, [context['partner_id']], ['invoice'])['invoice'],
        'partner_order_id'      : lambda self, cr, uid, context: context.get('partner_id', False) and  self.pool.get('res.partner').address_get(cr, uid, [context['partner_id']], ['contact'])['contact'],
        'departure_address_id'  : lambda self, cr, uid, context: context.get('partner_id', False) and self.pool.get('res.partner').address_get(cr, uid, [context['partner_id']], ['delivery'])['delivery'],
        'arrival_address_id'    : lambda self, cr, uid, context: context.get('partner_id', False) and self.pool.get('res.partner').address_get(cr, uid, [context['partner_id']], ['delivery'])['delivery'],
    }
    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Waybill must be unique !'),
    ]

    _order = 'name desc'


    def get_freight_from_factors(self, cr, uid, ids, context=None):
        prod_obj = self.pool.get('product.product')
        prod_id = prod_obj.search(cr, uid, [('tms_category', '=', 'freight'),('active','=', 1)], limit=1)
        if not prod_id:
            raise osv.except_osv(
                        _('Missing configuration !'),
                        _('There is no product defined as Freight !!!'))

        for product in prod_obj.browse(cr, uid, prod_id, context=None):
        
            prod_uom = product.uom_id.id
            prod_name = product.name
            prod_taxes = [(6, 0, [x.id for x in product.taxes_id])]


        factor = self.pool.get('tms.factor')


        line_obj = self.pool.get('tms.waybill.line')
        for waybill in self.browse(cr, uid, ids):
            for line in waybill.waybill_line:
                if line.control:
                    line_obj.unlink(cr, uid, [line.id])
            result = factor.calculate(cr, uid, 'waybill', ids, 'client', False)

            print result

            xline = {
                    'waybill_id'        : waybill.id,
                    'line_type'         : 'product',
                    'name'              : prod_name,
                    'sequence'          : 1,
                    'product_id'        : prod_id[0],
                    'product_uom'       : prod_uom,
                    'product_uom_qty'   : 1,
                    'price_unit'        : result,
                    'discount'          : 0.0,
                    'control'           : True,
                    'tax_id'            : prod_taxes
                }
        
            line_obj.create(cr, uid, xline)
        return True
        

    def write(self, cr, uid, ids, vals, context=None):
        super(tms_waybill, self).write(cr, uid, ids, vals, context=context)
        
        if 'state' in vals and vals['state'] not in ('confirmed', 'cancel') or self.browse(cr, uid, ids)[0].state in ('draft', 'approved')  :
            self.get_freight_from_factors(cr, uid, ids, context=context)
        return True

    def create(self, cr, uid, vals, context=None):
        res = super(tms_waybill, self).create(cr, uid, vals, context=context)
        self.get_freight_from_factors(cr, uid, [res], context=context)
        return res


    def onchange_sequence_id(self, cr, uid, ids, sequence_id):
        if not sequence_id:
            return {'value': {'billing_policy': 'manual', 
                        }}
        result = self.pool.get('ir.sequence').browse(cr, uid, [sequence_id])[0].tms_waybill_automatic
        return {'value': {'billing_policy': 'automatic' if result else 'manual', 
                        }}


    def onchange_travel_ids(self, cr, uid, ids, travel_ids):
        if not travel_ids or not len(travel_ids[0][2]):
            return {'value': {  'waybill_type'  : 'own',
                                'unit_id'       : False,
                                'trailer1_id'   : False,
                                'dolly_id'      : False,
                                'trailer2_id'   : False,
                                'employee_id'   : False,
                                'route_id'      : False,
                                'departure_id'  : False,
                                'arrival_id'    : False,
                                'travel_id'     : False,
                             }
                    }
        travel_id = False
        for rec in travel_ids:
            travel_id = rec[2][len(rec[2])-1] or False

        for travel in self.pool.get('tms.travel').browse(cr, uid, [travel_id]):
            return {'value': {  'waybill_type'  : 'outsourced' if (travel.unit_id.supplier_unit) else 'own',
                                'unit_id'       : travel.unit_id.id,
                                'trailer1_id'   : travel.trailer1_id.id,
                                'dolly_id'      : travel.dolly_id.id,
                                'trailer2_id'   : travel.trailer2_id.id,
                                'employee_id'   : travel.employee_id.id,
                                'route_id'      : travel.route_id.id,
                                'departure_id'  : travel.route_id.departure_id.id,
                                'arrival_id'    : travel.route_id.arrival_id.id,
                                'travel_id'     : travel_id,
                             }
                    }
        return {'value': {'travel_id': travel_id}}


    def onchange_partner_id(self, cr, uid, ids, partner_id):
        if not partner_id:
            return {'value': {'partner_invoice_id': False, 
                              'partner_order_id': False, 
                              'payment_term': False, 
                              'pricelist_id': False, 
                              'user_id': False}
                    }
                    
        addr = self.pool.get('res.partner').address_get(cr, uid, [partner_id], ['invoice', 'contact', 'default', 'delivery'])
        part = self.pool.get('res.partner').browse(cr, uid, partner_id)
        pricelist = part.property_product_pricelist and part.property_product_pricelist.id or False
        payment_term = part.property_payment_term and part.property_payment_term.id or False
        dedicated_salesman = part.user_id and part.user_id.id or uid
        val = {
            'partner_invoice_id': addr['invoice'] if addr['invoice'] else addr['default'],
            'partner_order_id': addr['contact'] if addr['contact'] else addr['default'],
            'payment_term': payment_term,
            'user_id': dedicated_salesman,
            'pricelist_id': pricelist,
        }
        return {'value': val}


    def copy(self, cr, uid, id, default=None, values=None, context=None):
        print "values: ", values
        print "cr: ", cr
        print "uid: ", uid
        print "id: ", id


        default = default or {}
        default.update({
                        'name'			: False, 
                        'state'			: 'draft',
                        'invoice_id'	: False, 
                        'cancelled_by'  : False,
                        'date_cancelled': False,
                        'approved_by'   : False,
                        'date_approved' : False,
                        'confirmed_by'  : False,
                        'date_confirmed': False,
                        'drafted_by'    : False,
                        'date_drafted'  : False,

						})
        if values:
            if 'replaced_waybill_id' in values:
                default.update({'replaced_waybill_id': values['replaced_waybill_id'] })
            if 'sequence_id' in values:
                default.update({'sequence_id': values['sequence_id'] })
            if 'date_order' in values:
                default.update({'date_order': values['date_order'] })
        print "default: ", default
        return super(tms_waybill, self).copy(cr, uid, id, default, context)


    def action_cancel_draft(self, cr, uid, ids, *args):
        if not len(ids):
            return False

        for waybill in self.browse(cr, uid, ids):
            if (waybill.travel_id.id) and waybill.travel_id.state in ('cancel'):
                raise osv.except_osv(
                        _('Could not set to draft this Waybill !'),
                        _('Travel is Cancelled !!!'))
            else:
		        self.write(cr, uid, ids, {'state':'draft', 'drafted_by':uid,'date_drafted':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
        for (id,name) in self.name_get(cr, uid, ids):
            message = "Waybill '%s' has been set to draft state." % name
            self.log(cr, uid, id, message)
        return True
    

    def action_cancel(self, cr, uid, ids, context=None):
        for waybill in self.browse(cr, uid, ids, context=context):
            if waybill.invoiced and waybill.invoice_paid:
                raise osv.except_osv(
                        _('Could not cancel Waybill !'),
                        _('This Waybill\'s Invoice is already paid'))

            elif waybill.invoiced and waybill.billing_policy=='manual':
                raise osv.except_osv(
                        _('Could not cancel Waybill !'),
                        _('This Waybill is already Invoiced'))

            elif waybill.billing_policy=='automatic' and waybill.invoiced and not waybill.invoice_paid:
                wf_service = netsvc.LocalService("workflow")
                wf_service.trg_validate(uid, 'account.invoice', waybill.invoice_id.id, 'invoice_cancel', cr)
                invoice_obj=self.pool.get('account.invoice')
                invoice_obj.unlink(cr, uid, [waybill.invoice_id.id], context=None)
#            elif waybill.state in ('draft','approved','confirmed') and waybill.travel_id.state in ('closed'):
#                raise osv.except_osv(
#                        _('Could not cancel Advance !'),
#                        _('This Waybill is already linked to Travel Expenses record'))
            self.write(cr, uid, ids, {'state':'cancel', 'cancelled_by':uid,'date_cancelled':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
            for (id,name) in self.name_get(cr, uid, ids):
                message = "Waybill '%s' is cancelled." % name
            self.log(cr, uid, id, message)
        return True

    def action_approve(self, cr, uid, ids, context=None):
        print "action_approve"
        for waybill in self.browse(cr, uid, ids, context=context):            
            if waybill.state in ('draft'):                
                if not waybill.sequence_id.id:
                    raise osv.except_osv('Could not Approve Waybill !', 'You have not selected a valid Waybill Sequence')
                elif not waybill.name:
                    seq_id = waybill.sequence_id.id
                    seq_number = self.pool.get('ir.sequence').get_id(cr, uid, seq_id)
                else:
                    seq_number = waybill.name

                self.write(cr, uid, ids, {'name':seq_number, 'state':'approved', 'approved_by' : uid, 'date_approved':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
                for (id,name) in self.name_get(cr, uid, ids):
                    message = _("Waybill '%s' is set to approved.") % name
                self.log(cr, uid, id, message)
        return True

    def action_confirm(self, cr, uid, ids, context=None):
        print "action_confirm"
        for waybill in self.browse(cr, uid, ids, context=None):
            if waybill.amount_untaxed <= 0.0:
                raise osv.except_osv(_('Could not confirm Waybill !'),_('Total Amount must be greater than zero.'))
            elif waybill.billing_policy == 'automatic':
                print "Entrando para generar la factura en automatico..."
                wb_invoice = self.pool.get('tms.waybill.invoice')
                wb_invoice.makeWaybillInvoicesq(cr, uid, ids, context=None)
            self.write(cr, uid, ids, {'state':'confirmed', 'confirmed_by' : uid, 'date_confirmed':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
            for (id,name) in self.name_get(cr, uid, ids, context=None):
                message = _("Waybill '%s' is set to confirmed.") % name
                self.log(cr, uid, id, message)
        return True

    def button_dummy(self, cr, uid, ids, context=None):
        return True


#    def copy(self, cr, uid, id, default=None, context=None):
#        if not default:
#            default = {}
#        default.update({
#                        'name'			: False, 
#                        'state'			: 'draft',
#                        'invoice_id'	: False, 
#                        'cancelled_by'  : False,
#                        'date_cancelled': False,
#                        'approved_by'   : False,
#                        'date_approved' : False,
#                        'confirmed_by'  : False,
#                        'date_confirmed': False,
#                        'drafted_by'    : False,
#                        'date_drafted'  : False,
#						})
#        print default
#        print id
#        return super(tms_waybill, self).copy(cr, uid, id, default, context=context)

tms_waybill()


# Adding relation between Waybills and Travels
class tms_travel(osv.osv):
    _inherit="tms.travel"

    _columns = {
        'waybill_ids': openerp.osv.fields.many2many('tms.waybill', 'tms_waybill_travel_rel', 'travel_id', 'waybill_id', 'Waybills'),
    }

tms_travel()


# Class for Waybill Lines
class tms_waybill_line(osv.osv):
    _name = 'tms.waybill.line'
    _description = 'Waybill Line'


    def _amount_line(self, cr, uid, ids, field_name, args, context=None):
        tax_obj = self.pool.get('account.tax')
        cur_obj = self.pool.get('res.currency')
        res = {}
        if context is None:
            context = {}
        for line in self.browse(cr, uid, ids, context=context):
            price = line.price_unit - line.price_unit *  (line.discount or 0.0) / 100.0
            taxes = tax_obj.compute_all(cr, uid, line.product_id.taxes_id, price, line.product_uom_qty, line.waybill_id.partner_invoice_id.id, line.product_id, line.waybill_id.partner_id)
            cur = line.waybill_id.pricelist_id.currency_id

            amount_with_taxes = cur_obj.round(cr, uid, cur, taxes['total_included'])
            amount_tax = cur_obj.round(cr, uid, cur, taxes['total_included']) - cur_obj.round(cr, uid, cur, taxes['total'])
            
            price_subtotal = line.price_unit * line.product_uom_qty
            price_discount = price_subtotal * (line.discount or 0.0) / 100.0
            res[line.id] =  {   'price_total'   : amount_with_taxes,
                                'price_amount': price_subtotal,
                                'price_discount': price_discount,
                                'price_subtotal': (price_subtotal - price_discount),
                                'tax_amount'    : amount_tax,
                                }
        return res



    _columns = {
#        'agreement_id': openerp.osv.fields.many2one('tms.agreement', 'Agreement', required=False, ondelete='cascade', select=True, readonly=True),
        'waybill_id': openerp.osv.fields.many2one('tms.waybill', 'Waybill', required=False, ondelete='cascade', select=True, readonly=True),
        'line_type': openerp.osv.fields.selection([
            ('product', 'Product'),
            ('note', 'Note'),
            ], 'Line Type', require=True),

        'name': openerp.osv.fields.char('Description', size=256, required=True),
        'sequence': openerp.osv.fields.integer('Sequence', help="Gives the sequence order when displaying a list of sales order lines."),
        'product_id': openerp.osv.fields.many2one('product.product', 'Product', 
                            domain=[('sale_ok', '=', True),
                                    ('tms_category', '=','freight'), 
                                    ('tms_category', '=','move'), 
                                    ('tms_category', '=','insurance'), 
                                    ('tms_category', '=','highway_tolls'), 
                                    ('tms_category', '=','other'),
                                    ], change_default=True),
        'price_unit': openerp.osv.fields.float('Unit Price', required=True, digits_compute= dp.get_precision('Sale Price')),
        'price_subtotal': openerp.osv.fields.function(_amount_line, method=True, string='Subtotal', type='float', digits_compute= dp.get_precision('Sale Price'),  store=True, multi='price_subtotal'),
        'price_amount': openerp.osv.fields.function(_amount_line, method=True, string='Price Amount', type='float', digits_compute= dp.get_precision('Sale Price'),  store=True, multi='price_subtotal'),
        'price_discount': openerp.osv.fields.function(_amount_line, method=True, string='Discount', type='float', digits_compute= dp.get_precision('Sale Price'),  store=True, multi='price_subtotal'),
        'price_total'   : openerp.osv.fields.function(_amount_line, method=True, string='Total Amount', type='float', digits_compute= dp.get_precision('Sale Price'),  store=True, multi='price_subtotal'),
        'tax_amount'   : openerp.osv.fields.function(_amount_line, method=True, string='Tax Amount', type='float', digits_compute= dp.get_precision('Sale Price'),  store=True, multi='price_subtotal'),
        'tax_id': openerp.osv.fields.many2many('account.tax', 'waybill_tax', 'waybill_line_id', 'tax_id', 'Taxes'),
        'product_uom_qty': openerp.osv.fields.float('Quantity (UoM)', digits=(16, 2)),
        'product_uom': openerp.osv.fields.many2one('product.uom', 'Unit of Measure '),
        'discount': openerp.osv.fields.float('Discount (%)', digits=(16, 2), help="Please use 99.99 format..."),
        'notes': openerp.osv.fields.text('Notes'),
        'waybill_partner_id': openerp.osv.fields.related('waybill_id', 'partner_id', type='many2one', relation='res.partner', store=True, string='Customer'),
        'salesman_id':openerp.osv.fields.related('waybill_id', 'user_id', type='many2one', relation='res.users', store=True, string='Salesman'),
        'company_id': openerp.osv.fields.related('waybill_id', 'company_id', type='many2one', relation='res.company', string='Company', store=True, readonly=True),
        'control': openerp.osv.fields.boolean('Control'),
    }
    _order = 'sequence, id desc'

    _defaults = {
        'line_type': 'product',
        'discount': 0.0,
        'product_uom_qty': 1,
        'sequence': 10,
        'price_unit': 0.0,
    }




    def on_change_product_id(self, cr, uid, ids, product_id):
        res = {}
        if not product_id:
            return {}
        prod_obj = self.pool.get('product.product')
        for product in prod_obj.browse(cr, uid, [product_id], context=None):
            print "Entrando aquí..."
            print "Taxes: ", product.taxes_id
            for x in product.taxes_id:
                print x.id
            res = {'value': {'product_uom' : product.uom_id.id,
                             'name': product.name,
                             'tax_id': [(6, 0, [x.id for x in product.taxes_id])],
                            }
                }
            print res
        return res

    def on_change_amount(self, cr, uid, ids, product_uom_qty, price_unit, discount, product_id):
        res = {'value': {
                    'price_amount': 0.0, 
                    'price_subtotal': 0.0, 
                    'price_discount': 0.0, 
                    'price_total': 0.0,
                    'tax_amount': 0.0, 
                        }
                }
        if not (product_uom_qty and price_unit and product_id ):
            return res
        tax_factor = 0.00
        prod_obj = self.pool.get('product.product')
        for line in prod_obj.browse(cr, uid, [product_id], context=None)[0].taxes_id:
            tax_factor = (tax_factor + line.amount) if line.amount <> 0.0 else tax_factor
#        if tax_factor == 0.00:
#            raise osv.except_osv(_('No taxes defined in product !'), _('You have to add taxes for this product. Para Mexico: Tiene que agregar el IVA que corresponda y el IEPS con factor 0.0.'))        

        price_amount = price_unit * product_uom_qty
        price_discount = (price_unit * product_uom_qty) * (discount/100.0)
        res = {'value': {
                    'price_amount': price_amount, 
                    'price_discount': price_discount, 
                    'price_subtotal': (price_amount - price_discount), 
                    'tax_amount': (price_amount - price_discount) * tax_factor, 
                    'price_total': (price_amount - price_discount) * (1.0 + tax_factor),
                        }
                }
        return res

tms_waybill_line()

# Class for Waybill Shipped Products
class tms_waybill_shipped_product(osv.osv):
    _name = 'tms.waybill.shipped_product'
    _description = 'Waybill Shipped Product'


    _columns = {
#        'agreement_id': openerp.osv.fields.many2one('tms.agreement', 'Agreement', required=False, ondelete='cascade', select=True, readonly=True),
        'waybill_id': openerp.osv.fields.many2one('tms.waybill', 'waybill', required=True, ondelete='cascade', select=True, readonly=True),
        'name': openerp.osv.fields.char('Description', size=256, required=True, select=True),
        'product_id': openerp.osv.fields.many2one('product.product', 'Product', 
                            domain=[
                                    ('tms_category', '=','transportable'), 
                                    ('tms_category', '=','move'), 
                                    ('tms_category', '=','insurance'), 
                                    ('tms_category', '=','highway_tolls'), 
                                    ('tms_category', '=','other'),
                                    ], change_default=True, required=True),
        'product_uom': openerp.osv.fields.many2one('product.uom', 'Unit of Measure ', required=True),
        'product_uom_qty': openerp.osv.fields.float('Quantity (UoM)', digits=(16, 2), required=True),
        'notes': openerp.osv.fields.text('Notes'),
        'waybill_partner_id': openerp.osv.fields.related('waybill_id', 'partner_id', type='many2one', relation='res.partner', store=True, string='Customer'),
        'salesman_id':openerp.osv.fields.related('waybill_id', 'user_id', type='many2one', relation='res.users', store=True, string='Salesman'),
        'shop_id': openerp.osv.fields.related('waybill_id', 'shop_id', type='many2one', relation='sale.shop', string='Shop', store=True, readonly=True),
        'company_id': openerp.osv.fields.related('waybill_id', 'company_id', type='many2one', relation='res.company', string='Company', store=True, readonly=True),
        'sequence': openerp.osv.fields.integer('Sequence', help="Gives the sequence order when displaying a list of sales order lines."),
    }
    _order = 'sequence, id desc'
    _defaults = {
        'product_uom_qty': 1,
        'sequence': 10,
    }

    def on_change_product_id(self, cr, uid, ids, product_id):
        res = {}
        if not product_id:
            return {}
        prod_obj = self.pool.get('product.product')
        for product in prod_obj.browse(cr, uid, [product_id], context=None):            
            res = {'value': {'product_uom' : product.uom_id.id,
                             'name': product.name}
                }
        return res



tms_waybill_shipped_product()


# Extra data fields for Waybills & Negotiations
class tms_waybill_extradata(osv.osv):
    _name = "tms.waybill.extradata"
    _description = "Tms Waybill Extra Data"

    _columns = {        
        'name': openerp.osv.fields.char('Name', size=30, required=True),
        'notes': openerp.osv.fields.text('Notes'),
        'sequence': openerp.osv.fields.integer('Sequence', help="Gives the sequence order when displaying this list of categories."),
        'mandatory': openerp.osv.fields.boolean('Mandatory'),
        'type_extra': openerp.osv.fields.selection([
            ('char', 'String (250)'),
            ('text', 'Text'),
            ('integer', 'Integer'),
            ('float', 'Float'),
            ('date', 'Date'),
            ('datetime', 'Datetime')
            ], 'Data Type', help="Useful to set wich field is used for extra data field", select=True),

        'value_char'    : openerp.osv.fields.char('Value', size=250),
        'value_text'    : openerp.osv.fields.text('Value'),
        'value_integer' : openerp.osv.fields.integer('Value'),
        'value_float'   : openerp.osv.fields.float('Value',digits=(16, 4)),
        'value_date'    : openerp.osv.fields.date('Value'),
        'value_datetime': openerp.osv.fields.datetime('Value'),
        'value_extra'   : openerp.osv.fields.text('Value'),

        'waybill_id': openerp.osv.fields.many2one('tms.waybill', 'Waybill', required=False, ondelete='cascade'), #, select=True, readonly=True),
#        'agreement_id': openerp.osv.fields.many2one('tms.agreement', 'Agreement', required=False, ondelete='cascade', select=True, readonly=True),
        
    }

    _defaults = {
#        'mandatory': True, 
        'sequence':10,
    }


    _order = "sequence"


    def on_change_value(self, cr, uid, ids, type_extra, value):
        if not type_extra and not value:
            return {}
        if type_extra == 'char' or type_extra == 'text':
            return {'value': {'value_extra' : value}}
        elif type_extra == 'integer' or type_extra=='float':
            return {'value': {'value_extra' : str(value)}}
        elif type_extra == 'date':
            xdate = filter(None, map(lambda x:int(x), value.split('-'))) 
            return {'value': {'value_extra' : date(xdate[0], xdate[1], xdate[2]).strftime(DEFAULT_SERVER_DATE_FORMAT)}}                
        elif type_extra == 'datetime':
            print "value: ", value            
            xvalue = value.split(' ')
            xdate = filter(None, map(lambda x:int(x), xvalue[0].split('-'))) 
            xtime = map(lambda x:int(x), xvalue[1].split(':')) 

            tzone = timezone(self.pool.get('res.users').browse(cr, uid, uid).tz)
            value = tzone.localize(datetime(xdate[0], xdate[1], xdate[2], xtime[0], xtime[1], xtime[2]))

            print value
            xvalue = value.split(' ')
            xdate = filter(None, map(lambda x:int(x), xvalue[0].split('-'))) 
            xtime = map(lambda x:int(x), xvalue[1].split(':')) 
            return {'value': {'value_extra' : datetime(xdate[0], xdate[1], xdate[2], xtime[0], xtime[1], xtime[2]).strftime( DEFAULT_SERVER_DATETIME_FORMAT)}}                
        return False


    
tms_waybill_extradata()


# Wizard que permite hacer una copia de la carta porte al momento de cancelarla
class tms_waybill_cancel(osv.osv_memory):

    """ To create a copy of Waybill when cancelled"""

    _name = 'tms.waybill.cancel'
    _description = 'Make a copy of Cancelled Waybill'

    _columns = {
            'company_id'    : openerp.osv.fields.many2one('res.company', 'Company'),
#            'shop_id'       : openerp.osv.fields.many2one('sale.shop', 'Shop', required=True),
            'copy_waybill'  : openerp.osv.fields.boolean('Create copy of this waybill?', required=False),
            'sequence_id'   : openerp.osv.fields.many2one('ir.sequence', 'Sequence', required=False),
            'date_order'    : openerp.osv.fields.date('Date', required=False),
        }

    _defaults = {'date_order'   : fields.date.context_today,
                 'company_id'   :  lambda self, cr, uid, context: self.pool.get('res.users').browse(cr, uid, uid).company_id.id
                 }

    def make_copy(self, cr, uid, ids, context=None):

        """
             To copy Waybills when cancelling them
             @param self: The object pointer.
             @param cr: A database cursor
             @param uid: ID of the user currently logged in
             @param context: A standard dictionary
             @return : retrun view of Invoice
        """

        record_id =  context.get('active_ids',[])

        print record_id

        if record_id:
            print "Si entra..."
            for record in self.browse(cr,uid, ids):
                print record.company_id.name
                print record.date_order
                waybill_obj = self.pool.get('tms.waybill')
                for waybill in waybill_obj.browse(cr, uid, record_id):
                    print waybill.name
                    if waybill.invoiced and waybill.invoice_paid:
                        raise osv.except_osv(
                                _('Could not cancel Waybill !'),
                                _('This Waybill\'s Invoice is already paid'))
                        return False
                    elif waybill.invoiced and waybill.billing_policy=='manual':
                        raise osv.except_osv(
                                _('Could not cancel Waybill !'),
                                _('This Waybill is already Invoiced'))
                        return False
                    elif waybill.billing_policy=='automatic' and waybill.invoiced and not waybill.invoice_paid:
                        wf_service = netsvc.LocalService("workflow")
                        wf_service.trg_validate(uid, 'account.invoice', waybill.invoice_id.id, 'invoice_cancel', cr)
                        invoice_obj=self.pool.get('account.invoice')
                        invoice_obj.unlink(cr, uid, [waybill.invoice_id.id], context=None)
        #            elif waybill.state in ('draft','approved','confirmed') and waybill.travel_id.state in ('closed'):
        #                raise osv.except_osv(
        #                        _('Could not cancel Advance !'),
        #                        _('This Waybill is already linked to Travel Expenses record'))
                    print "record_id:", record_id
                    waybill_obj.write(cr, uid, record_id, {'state':'cancel', 'cancelled_by':uid,'date_cancelled':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
          
                    if record.copy_waybill:                        
                        default ={} 
                        default.update({'replaced_waybill_id': waybill.id })
                        if record.sequence_id.id:
                            default.update({'sequence_id': record.sequence_id.id })
                        if record.date_order:
                            default.update({'date_order': record.date_order })
                        waybill=waybill_obj.copy(cr, uid, record_id[0], values=default)
        return {'type': 'ir.actions.act_window_close'}

tms_waybill_cancel()

# Wizard que permite conciliar los Vales de combustible en una factura
class tms_waybill_invoice(osv.osv_memory):

    """ To create invoice for each Waybill"""

    _name = 'tms.waybill.invoice'
    _description = 'Make Invoices from Waybill'

    def makeWaybillInvoices(self, cr, uid, ids, context=None):

        """
             To get Waybills and create Invoices
             @param self: The object pointer.
             @param cr: A database cursor
             @param uid: ID of the user currently logged in
             @param context: A standard dictionary
             @return : retrun view of Invoice
        """

        if context is None:
            record_ids = ids
        else:
            record_ids =  context.get('active_ids',[])

        if record_ids:
            res = False
            invoices = []
            property_obj=self.pool.get('ir.property')
            partner_obj=self.pool.get('res.partner')
            user_obj=self.pool.get('res.users')
            account_fiscal_obj=self.pool.get('account.fiscal.position')
            invoice_line_obj=self.pool.get('account.invoice.line')
            account_jrnl_obj=self.pool.get('account.journal')
            invoice_obj=self.pool.get('account.invoice')
            waybill_obj=self.pool.get('tms.waybill')


            journal_id = account_jrnl_obj.search(cr, uid, [('type', '=', 'sale')], context=None)
            journal_id = journal_id and journal_id[0] or False


#            partner = partner_obj.browse(cr,uid,user_obj.browse(cr,uid,[uid])[0].company_id.partner_id.id)


            cr.execute("select distinct partner_id, pricelist_id from tms_waybill where invoice_id is null and (state='confirmed' or (state='approved' and billing_policy='automatic')) and id IN %s",(tuple(record_ids),))
            data_ids = cr.fetchall()
            if not len(data_ids):
                raise osv.except_osv(_('Warning !'),
                                     _('Not all selected records are Confirmed yet or already invoiced...'))
            print data_ids

            for data in data_ids:
                partner = partner_obj.browse(cr,uid,data[0])
 
                cr.execute("select id from tms_waybill where invoice_id is null and (state='confirmed' or (state='approved' and billing_policy='automatic')) and partner_id=" + str(data[0]) + ' and pricelist_id=' + str(data[1]) + " and id IN %s", (tuple(record_ids),))
                waybill_ids = filter(None, map(lambda x:x[0], cr.fetchall()))
                
                inv_lines = []
                notes = "Waybills"
                inv_amount = 0.0
                empl_name = ''
                for waybill in waybill_obj.browse(cr,uid,waybill_ids):                    
                    currency_id = waybill.pricelist_id.currency_id.id
                    for line in waybill.waybill_line:
                        if line.line_type=='product':
                            if line.product_id:
                                a = line.product_id.product_tmpl_id.property_account_income.id
                                if not a:
                                    a = line.product_id.categ_id.property_account_income_categ.id
                                if not a:
                                    raise osv.except_osv(_('Error !'),
                                            _('There is no income account defined ' \
                                                    'for this product: "%s" (id:%d)') % \
                                                    (line.product_id.name, line.product_id.id,))
                            else:
                                a = property_obj.get(cr, uid,
                                        'property_account_expense_categ', 'product.category',
                                        context=context).id

                            a = account_fiscal_obj.map_account(cr, uid, False, a)
                            inv_line = (0,0, {
                                'name': line.name  + ' - ' + (line.waybill_id.travel_id.name or 'No travel') + ' - ' + line.waybill_id.name,
                                'origin': line.waybill_id.name,
                                'account_id': a,
                                'price_unit': line.price_unit,
                                'quantity': line.product_uom_qty,
                                'uos_id': line.product_uom.id,
                                'product_id': line.product_id.id,
                                'invoice_line_tax_id': [(6, 0, [x.id for x in line.product_id.taxes_id])],
                                'note': line.notes,
                                'account_analytic_id': False,
                                })
                            inv_lines.append(inv_line)
                        
                    notes += '\n' + line.waybill_id.name
                    departure_address_id = waybill.departure_address_id.id
                    arrival_address_id = waybill.arrival_address_id.id
                a = partner.property_account_receivable.id
                if partner and partner.property_payment_term.id:
                    pay_term = partner.property_payment_term.id
                else:
                    pay_term = False

                inv = {
                    'name'              : 'Fact.Pendiente',
                    'origin'            : 'TMS-Waybill',
                    'type'              : 'out_invoice',
                    'journal_id'        : journal_id,
                    'reference'         : 'TMS-Waybills',
                    'account_id'        : a,
                    'partner_id'        : waybill.partner_id.id,
                    'departure_address_id' : departure_address_id,
                    'arrival_address_id'   : arrival_address_id,
                    'address_invoice_id': self.pool.get('res.partner').address_get(cr, uid, [partner.id], ['default'])['default'],
                    'address_contact_id': self.pool.get('res.partner').address_get(cr, uid, [partner.id], ['default'])['default'],
                    'invoice_line'      : [x for x in inv_lines],
                    'currency_id'       : currency_id,
                    'comment'           : 'TMS-Waybills',
                    'payment_term'      : pay_term,
                    'fiscal_position'   : partner.property_account_position.id,
                    'comment'           : notes,
                    'tms_type'          : 'invoice' if waybill.billing_policy == 'manual' else 'waybill'
                }



                inv_id = invoice_obj.create(cr, uid, inv)
                invoices.append(inv_id)

                waybill_obj.write(cr,uid,waybill_ids, {'invoice_id': inv_id})   
                waybill_obj.write(cr,uid,waybill_ids, {'invoice_id': inv_id, 'state':'confirmed', 'confirmed_by':uid, 'date_confirmed':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})               



        return {
            'domain': "[('id','in', ["+','.join(map(str,invoices))+"])]",
            'name': _('Customer Invoices'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'account.invoice',
            'view_id': False,
            'context': "{'type':'out_invoice', 'journal_type': 'sale'}",
            'type': 'ir.actions.act_window'
        }
tms_waybill_invoice()


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
