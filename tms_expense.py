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

# TMS Travel Expenses
class tms_expense(osv.osv):
    _name = 'tms.expense'
    _description = 'TMS Travel Expenses'

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


    def _get_route_distance(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        distance=0.0
        for expense in self.browse(cr, uid, ids, context=context):
            for travel in expense.travel_ids:
                distance += travel.route_id.distance
            res[expense.id] = distance
        return res


    def _amount_all(self, cr, uid, ids, field_name, arg, context=None):
        cur_obj = self.pool.get('res.currency')
        res = {}
        for expense in self.browse(cr, uid, ids, context=context):
            res[expense.id] = {
                'amount_real_expense'       : 0.0,
                'amount_madeup_expense'     : 0.0,
                'amount_fuel'               : 0.0,
                'amount_fuel_voucher'       : 0.0,
                'amount_salary'             : 0.0,
                'amount_net_salary'         : 0.0,
                'amount_salary_retention'   : 0.0,
                'amount_salary_discount'    : 0.0,
                'amount_subtotal_real'      : 0.0,
                'amount_subtotal_total'     : 0.0,
                'amount_tax_real'           : 0.0,
                'amount_tax_total'          : 0.0,
                'amount_total_real'         : 0.0,
                'amount_total_total'        : 0.0,
                'amount_balance'            : 0.0,
                'amount_advance'            : 0.0,
                }            
            cur = expense.currency_id
            advance = fuel_voucher =  0.0
            for _advance in expense.advance_ids:
                if _advance.currency_id.id != cur.id:
                    raise osv.except_osv(
                         _('Currency Error !'), 
                         _('You can not create a Travel Expense Record with Advances with different Currency. This Expense record was created with %s and Advance is with %s ') % (expense.currency_id.name, _advance.currency_id.name))
                advance += _advance.total_amount

            for _fuelvoucher in expense.fuelvoucher_ids:
                if _fuelvoucher.currency_id.id != cur.id:
                    raise osv.except_osv(
                         _('Currency Error !'), 
                         _('You can not create a Travel Expense Record with Advances with different Currency. This Expense record was created with %s and Advance is with %s ') % (expense.currency_id.name, _advance.currency_id.name))
                fuel_voucher += _fuelvoucher.price_subtotal

            print "fuel_voucher:", fuel_voucher

            real_expense = madeup_expense = fuel = salary = salary_retention = salary_discount = tax_real = tax_total = subtotal_real = subtotal_total = total_real = total_total = balance = 0.0
            for line in expense.expense_line:
                    madeup_expense  += line.price_subtotal if line.product_id.tms_category == 'madeup_expense' else 0.0
                    real_expense    += line.price_subtotal if line.product_id.tms_category == 'real_expense' else 0.0
                    salary          += line.price_subtotal if line.product_id.tms_category == 'salary' else 0.0
                    salary_retention += line.price_subtotal if line.product_id.tms_category == 'salary_retention' else 0.0
                    salary_discount += line.price_subtotal if line.product_id.tms_category == 'salary_discount' else 0.0
                    fuel            += line.price_subtotal if (line.product_id.tms_category == 'fuel' and not line.fuel_voucher) else 0.0
                    tax_total       += line.tax_amount if line.product_id.tms_category != 'madeup_expense' else 0.0
                    tax_real        += line.tax_amount if (line.product_id.tms_category == 'real_expense' or (line.product_id.tms_category == 'fuel' and not line.fuel_voucher)) else 0.0

            print "fuel_voucher:", fuel_voucher
        
            subtotal_real = real_expense + fuel + salary + salary_retention + salary_discount
            total_real = subtotal_real + tax_real
            subtotal_total = subtotal_real + fuel_voucher
            total_total = subtotal_total + tax_total
            balance = total_real - advance
            res[expense.id] = { 
                'amount_real_expense'       : cur_obj.round(cr, uid, cur, real_expense),
                'amount_madeup_expense'     : cur_obj.round(cr, uid, cur, madeup_expense),
                'amount_fuel'               : cur_obj.round(cr, uid, cur, fuel),
                'amount_fuel_voucher'       : cur_obj.round(cr, uid, cur, fuel_voucher),
                'amount_salary'             : cur_obj.round(cr, uid, cur, salary),
                'amount_net_salary'         : cur_obj.round(cr, uid, cur, salary + salary_retention + salary_discount),
                'amount_salary_retention'   : cur_obj.round(cr, uid, cur, salary_retention),
                'amount_salary_discount'    : cur_obj.round(cr, uid, cur, salary_discount),
                'amount_subtotal_real'      : cur_obj.round(cr, uid, cur, subtotal_real),
                'amount_subtotal_total'     : cur_obj.round(cr, uid, cur, subtotal_total),
                'amount_tax_real'           : cur_obj.round(cr, uid, cur, tax_real),
                'amount_tax_total'          : cur_obj.round(cr, uid, cur, tax_total),
                'amount_total_real'         : cur_obj.round(cr, uid, cur, total_real),
                'amount_total_total'        : cur_obj.round(cr, uid, cur, total_total),
                'amount_advance'            : cur_obj.round(cr, uid, cur, advance),
                'amount_balance'            : cur_obj.round(cr, uid, cur, balance),
                              }

        return res


    _columns = {
        'name': openerp.osv.fields.char('Name', size=64, readonly=True, select=True),
        'shop_id': openerp.osv.fields.many2one('sale.shop', 'Shop', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'company_id': openerp.osv.fields.related('shop_id','company_id',type='many2one',relation='res.company',string='Company',store=True,readonly=True),
        'employee_id': openerp.osv.fields.many2one('hr.employee', 'Driver', required=True, domain=[('tms_category', '=', 'driver')], states={'cancel':[('readonly',True)], 'approved':[('readonly',True)], 'closed':[('readonly',True)]}),
        'travel_ids': openerp.osv.fields.many2many('tms.travel', 'tms_expense_travel_rel', 'expense_id', 'travel_id', 'Travels', readonly=False, states={'confirmed': [('readonly', True)],'closed':[('readonly',True)]}),
        'unit_id': openerp.osv.fields.many2one('tms.unit', 'Unit', required=False, readonly=True),
        'currency_id': openerp.osv.fields.many2one('res.currency', 'Currency', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'state': openerp.osv.fields.selection([
            ('draft', 'Draft'),
            ('approved', 'Approved'),
            ('confirmed', 'Confirmed'),
            ('cancel', 'Cancelled')
            ], 'Expense State', readonly=True, help="Gives the state of the Travel Expense. ", select=True),
        'expense_policy': openerp.osv.fields.selection([           
            ('manual', 'Manual'),
            ('automatic', 'Automatic'),
            ], 'Expense  Policy', readonly=True,
            help=" Manual - This expense record is manual\nAutomatic - This expense record is automatically generated by parametrization", select=True),
        'origin': openerp.osv.fields.char('Source Document', size=64, help="Reference of the document that generated this Expense Record",readonly=False, states={'confirmed': [('readonly', True)],'closed':[('readonly',True)]}),

        'expense_line': openerp.osv.fields.one2many('tms.expense.line', 'expense_id', 'Expense Lines', readonly=False, states={'confirmed': [('readonly', True)],'closed':[('readonly',True)]}),

        'date': openerp.osv.fields.date('Date', required=True, select=True,readonly=False, states={'confirmed': [('readonly', True)],'closed':[('readonly',True)]}),

        'invoice_id': openerp.osv.fields.many2one('account.invoice','Invoice Record', readonly=True),
        'invoiced':  openerp.osv.fields.function(_invoiced, method=True, string='Invoiced', type='boolean', multi='invoiced', store=True),
        'invoice_paid':  openerp.osv.fields.function(_invoiced, method=True, string='Paid', type='boolean', multi='invoiced', store=True),
        'invoice_name':  openerp.osv.fields.function(_invoiced, method=True, string='Invoice', type='char', size=64, multi='invoiced', store=True),

        'expense_line': openerp.osv.fields.one2many('tms.expense.line', 'expense_id', 'Expense Lines', readonly=False, states={'confirmed': [('readonly', True)],'closed':[('readonly',True)]}),


        'amount_real_expense': openerp.osv.fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Expenses', type='float',
                                            store=True, multi='amount_real_expense'),
        'amount_madeup_expense': openerp.osv.fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Fake Expenses', type='float',
                                            store=True, multi='amount_real_expense'),
        'amount_fuel': openerp.osv.fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Fuel (Cash)', type='float',
                                            store=True, multi='amount_real_expense'),
        'amount_fuel_voucher': openerp.osv.fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Fuel (Voucher)', type='float',
                                            store=True, multi='amount_real_expense'),
        'amount_salary': openerp.osv.fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Salary', type='float',
                                            store=True, multi='amount_real_expense'),
        'amount_net_salary': openerp.osv.fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Net Salary', type='float',
                                            store=True, multi='amount_real_expense'),
        'amount_salary_retention': openerp.osv.fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Salary Retentions', type='float',
                                            store=True, multi='amount_real_expense'),
        'amount_salary_discount': openerp.osv.fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Salary Discounts', type='float',
                                            store=True, multi='amount_real_expense'),
        'amount_advance': openerp.osv.fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Advances', type='float',
                                            store=True, multi='amount_real_expense'),

        'amount_balance': openerp.osv.fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Balance', type='float',
                                            store=True, multi='amount_real_expense'),
        'amount_tax_total': openerp.osv.fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Taxes (All)', type='float',
                                            store=True, multi='amount_real_expense'),
        'amount_tax_real': openerp.osv.fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Taxes (Real)', type='float',
                                            store=True, multi='amount_real_expense'),
        'amount_total_real': openerp.osv.fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Total (Real)', type='float',
                                            store=True, multi='amount_real_expense'),
        'amount_total_total': openerp.osv.fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Total (All)', type='float',
                                            store=True, multi='amount_real_expense'),
        'amount_subtotal_real': openerp.osv.fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Total (Real)', type='float',
                                            store=True, multi='amount_real_expense'),
        'amount_subtotal_total': openerp.osv.fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Total (All)', type='float',
                                            store=True, multi='amount_real_expense'),


        'distance_routes': openerp.osv.fields.function(_get_route_distance, string='Distance from routes', method=True, type='float', digits=(18,6), help="Routes Distance", multi="distance_route"),
        'distance_real':  openerp.osv.fields.float('Distance Real', digits=(18,6), help="Route obtained by electronic reading and/or GPS"),
       
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

        
        'fuelvoucher_ids':openerp.osv.fields.one2many('tms.fuelvoucher', 'expense_id', string='Fuel Vouchers', readonly=True),
        'advance_ids':openerp.osv.fields.one2many('tms.advance', 'expense_id', string='Advances', readonly=True),


    }
    _defaults = {
        'date'            : lambda *a: time.strftime(DEFAULT_SERVER_DATE_FORMAT),
        'expense_policy'        : 'manual',
        'state'                 : lambda *a: 'draft',
        'currency_id': lambda self,cr,uid,c: self.pool.get('res.users').browse(cr, uid, uid, c).company_id.currency_id.id,
    }
    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Expense record must be unique !'),
    ]

    _order = 'name desc'


    def get_salary_from_factors(self, cr, uid, ids, context=None):
        prod_obj = self.pool.get('product.product')
        prod_id = prod_obj.search(cr, uid, [('tms_category', '=', 'salary'),('active','=', 1)], limit=1)
        if not prod_id:
            raise osv.except_osv(
                        _('Missing configuration !'),
                        _('There is no product defined as Salary !!!'))

        for product in prod_obj.browse(cr, uid, prod_id, context=None):        
            prod_uom = product.uom_id.id
            prod_name = product.name
            prod_taxes = [(6, 0, [x.id for x in product.taxes_id])]
            prod_category = product.tms_category

        factor = self.pool.get('tms.factor')
        line_obj = self.pool.get('tms.expense.line')

        for expense in self.browse(cr, uid, ids):
            for line in expense.expense_line:
                if line.control:
                    line_obj.unlink(cr, uid, [line.id])
            result = factor.calculate(cr, uid, 'expense', ids, 'driver')
            print result

            xline = {
                    'expense_id'        : expense.id,
                    'line_type'         : prod_category,
                    'name'              : prod_name,
                    'sequence'          : 1,
                    'product_id'        : prod_id[0],
                    'product_uom'       : prod_uom,
                    'product_uom_qty'   : 1,
                    'price_unit'        : result,
                    'control'           : True,
                    'tax_id'            : prod_taxes
                }
        
            line_obj.create(cr, uid, xline)


        prod_id = prod_obj.search(cr, uid, [('tms_category', '=', 'fuel'),('active','=', 1)], limit=1)
        if not prod_id:
            raise osv.except_osv(
                        _('Missing configuration !'),
                        _('There is no product defined as Fuel !!!'))

        for product in prod_obj.browse(cr, uid, prod_id, context=None):        
            prod_uom = product.uom_id.id
            prod_name = product.name
            prod_taxes = [(6, 0, [x.id for x in product.taxes_id])]
            prod_category = product.tms_category


        qty = amount_untaxed = 0.0
        for fuelvoucher in expense.fuelvoucher_ids:
            qty             += fuelvoucher.product_uom_qty
            amount_untaxed  += fuelvoucher.price_subtotal

        xline = {
                'expense_id'        : expense.id,
                'line_type'         : prod_category,
                'name'              : prod_name + _(' from Fuel Voucher'),
                'sequence'          : 5,
                'product_id'        : prod_id[0],
                'product_uom'       : prod_uom,
                'product_uom_qty'   : qty,
                'price_unit'        : amount_untaxed / qty,
                'control'           : True,
                'tax_id'            : prod_taxes,
                'fuel_voucher'      : True,
            }
    
        line_obj.create(cr, uid, xline)




        return True

    def write(self, cr, uid, ids, vals, context=None):

        fuelvoucher_ids = False
        advance_ids = False
        if 'travel_ids' in vals:
            travel_obj      = self.pool.get('tms.travel')
            if vals['travel_ids'][0][2]:
                travel_ids = travel_obj.search(cr, uid, [('travel_id', 'in', (tuple(vals['travel_ids'][0][2]),))])
                if len(travel_ids) > 1:
                    units = ""
                    for travel in travel_obj.browse(cr,uid, travel_ids):
                        units += travel.unit_id.name + ", "
                    units = units[0:len(units)-1]
                    print units
                    raise osv.except_osv(
                             _('Travels Error !'), 
                             _('You can not create an Expense Record with Travels with different motorized units.') % (units))

            print vals['travel_ids']

            fuelvoucher_obj = self.pool.get('tms.fuelvoucher')
            advance_obj     = self.pool.get('tms.advance')


            fuelvoucher_ids = fuelvoucher_obj.search(cr, uid, [('expense_id', '=', ids[0])])
            if fuelvoucher_ids:
                fuelvoucher_obj.write(cr, uid, fuelvoucher_ids, {'expense_id': False, 'state':'confirmed', 'date_closed': False})

            advance_ids = advance_obj.search(cr, uid, [('expense_id', '=', ids[0])])
            if advance_ids:
                advance_obj.write(cr, uid, advance_ids, {'expense_id': False, 'state':'confirmed', 'date_closed': False})

            travel_ids = travel_obj.search(cr, uid, [('expense_id', '=', ids[0])])
            if travel_ids:
                travel_obj.write(cr, uid, travel_ids, {'expense_id': False, 'state':'done', 'date_closed': False})

            if vals['travel_ids'][0][2]:
                if not ('currency_id' in vals):
                    vals['currency_id'] = self.browse(cr, uid, ids)[0].currency_id.id

                fuelvoucher_ids = fuelvoucher_obj.search(cr, uid, [('travel_id', 'in', (tuple(vals['travel_ids'][0][2]),)),('state','!=', 'cancel')])
                for fuelvoucher in fuelvoucher_obj.browse(cr, uid, fuelvoucher_ids):
                    if fuelvoucher.state != 'confirmed':
                        raise osv.except_osv(
                             _('Fuel Voucher Error !'), 
                             _('Fuel Voucher %s in Travel %s is in state %s. You can not make an Expense Record with Fuel Vouchers whose state is not confirmed') % (fuelvoucher.name, fuelvoucher.travel_id.name, fuelvoucher.state))
                   
                    if fuelvoucher.currency_id.id != vals['currency_id']:
                        raise osv.except_osv(
                             _('Fuel Voucher Error !'), 
                             _('Fuel Voucher %s in Travel %s was created with %s currency, but this Expense record was created with %s currency.') % 
                                    (fuelvoucher.name, fuelvoucher.travel_id.name, fuelvoucher.currency_id.name, 
                                        self.pool.get('res.currency').browse(cr, uid, vals['currency_id'])[0].name))



                advance_ids = advance_obj.search(cr, uid, [('travel_id', 'in', (tuple(vals['travel_ids'][0][2]),)),('state','!=', 'cancel')])
                for advance in advance_obj.browse(cr, uid, advance_ids):
                    if advance.state != 'confirmed':
                        raise osv.except_osv(
                             _('Advance Error !'), 
                             _('Advance %s  in Travel %s is in state %s. You can not make an Expense Record with Advances whose state is not confirmed') % (advance.name, advance.travel_id.name, advance.state))
                    if advance.currency_id.id != vals['currency_id']:
                        raise osv.except_osv(
                             _('Advance Error !'), 
                             _('Advance %s in Travel %s was created with %s currency, but this Expense record was created with %s currency.') % 
                                    (advance.name, advance.travel_id.name, advance.currency_id.name, 
                                        self.pool.get('res.currency').browse(cr, uid, vals['currency_id'])[0].name))

        super(tms_expense, self).write(cr, uid, ids, vals, context=context)

        if fuelvoucher_ids:
            fuelvoucher_obj.write(cr, uid, fuelvoucher_ids, {'expense_id': ids[0], 'state':'closed','closed_by':uid,'date_closed':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
        if advance_ids:
            advance_obj.write(cr, uid, advance_ids, {'expense_id': ids[0], 'state':'closed','closed_by':uid,'date_closed':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
        if 'travel_ids' in vals and vals['travel_ids'][0][2]:                    
            travel_obj.write(cr, uid, vals['travel_ids'][0][2], {'expense_id': ids[0], 'state':'closed','closed_by':uid,'date_closed':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})  

        self.get_salary_from_factors(cr, uid, ids, context=context)
        
        return True



    def create(self, cr, uid, vals, context=None):
        if vals['shop_id']:
            shop = self.pool.get('sale.shop').browse(cr, uid, [vals['shop_id']])[0]
            seq_id = shop.tms_travel_expenses_seq.id
            if shop.tms_travel_expenses_seq:
                seq_number = self.pool.get('ir.sequence').get_id(cr, uid, seq_id)
                vals['name'] = seq_number
            else:
                raise osv.except_osv(_('Expense Sequence Error !'), _('You have not defined Expense Sequence for shop ' + shop.name))

        travel_obj = self.pool.get('tms.travel')
        if 'travel_ids' in vals:

            if vals['travel_ids'][0][2] and len(vals['travel_ids'][0][2]) > 1 :
                cr.execute("select distinct unit_id from tms_travel where id in %s",(tuple(vals['travel_ids'][0][2]),))
                unit_ids = filter(None, map(lambda x:x[0], cr.fetchall()))
                if len(unit_ids) > 1:
                    raise osv.except_osv(
                             _('Travels Error !'), 
                             _('You can not create an Expense Record with Travels with different motorized units.') % (units))

            fuelvoucher_obj = self.pool.get('tms.fuelvoucher')
            advance_obj = self.pool.get('tms.advance')

            fuelvoucher_ids = fuelvoucher_obj.search(cr, uid, [('travel_id', 'in', (tuple(vals['travel_ids'][0][2]),)),('state','!=', 'cancel')])
            for fuelvoucher in fuelvoucher_obj.browse(cr, uid, fuelvoucher_ids):
                if fuelvoucher.state != 'confirmed':
                    raise osv.except_osv(
                         _('Fuel Voucher Error !'), 
                         _('Fuel Voucher %s in Travel %s is in state %s. You can not make an Expense Record with Fuel Vouchers whose state is not confirmed') % (fuelvoucher.name, fuelvoucher.travel_id.name, fuelvoucher.state))
                if fuelvoucher.currency_id.id != vals['currency_id']:
                    raise osv.except_osv(
                         _('Fuel Voucher Error !'), 
                         _('Fuel Voucher %s in Travel %s was created with %s currency, but this Expense record was created with %s currency.') % 
                                (fuelvoucher.name, fuelvoucher.travel_id.name, fuelvoucher.currency_id.name, 
                                    self.pool.get('res.currency').browse(cr, uid, vals['currency_id'])[0].name))

            advance_ids = advance_obj.search(cr, uid, [('travel_id', 'in', (tuple(vals['travel_ids'][0][2]),)),('state','!=', 'cancel')])
            for advance in advance_obj.browse(cr, uid, advance_ids):
                if advance.state != 'confirmed':
                    raise osv.except_osv(
                         _('Advance Error !'), 
                         _('Advance %s  in Travel %s is in state %s. You can not make an Expense Record with Advances whose state is not confirmed') % (advance.name, advance.travel_id.name, advance.state))
                if advance.currency_id.id != vals['currency_id']:
                    raise osv.except_osv(
                         _('Advance Error !'), 
                         _('Advance %s in Travel %s was created with %s currency, but this Expense record was created with %s currency.') % 
                                (advance.name, advance.travel_id.name, advance.currency_id.name, 
                                    self.pool.get('res.currency').browse(cr, uid, vals['currency_id'])[0].name))

            

        


        res = super(tms_expense, self).create(cr, uid, vals, context=context)
        if fuelvoucher_ids:
            fuelvoucher_obj.write(cr, uid, fuelvoucher_ids, {'expense_id': res, 'state':'closed','closed_by':uid,'date_closed':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
        if advance_ids:
            advance_obj.write(cr, uid, advance_ids, {'expense_id': res, 'state':'closed','closed_by':uid,'date_closed':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
        if 'travel_ids' in vals:            
            travel_obj.write(cr, uid, vals['travel_ids'][0][2], {'expense_id': res, 'state':'closed','closed_by':uid,'date_closed':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
        return res


    def action_approve(self, cr, uid, ids, context=None):
        for expense in self.browse(cr, uid, ids, context=context):            
            if expense.state in ('draft'):
                if expense.amount_total_total == 0.0:
                     raise osv.except_osv(
                        _('Could not approve Expense !'),
                        _('Total Amount must be greater than zero.'))
                self.write(cr, uid, ids, {'state':'approved', 'approved_by' : uid, 'date_approved':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
                for (id,name) in self.name_get(cr, uid, ids):
                    message = _("Expense '%s' is set to approved.") % name
                self.log(cr, uid, id, message)
        return True




# Adding relation between Advances and Travel Expenses
class tms_advance(osv.osv):
    _inherit = "tms.advance"

    _columns = {
            'expense_id':openerp.osv.fields.many2one('tms.expense', 'Expense Record', required=False, readonly=True),
        }

# Adding relation between Fuel Vouchers and Travel Expenses
class tms_fuelvoucher(osv.osv):
    _inherit = "tms.fuelvoucher"

    _columns = {
            'expense_id':openerp.osv.fields.many2one('tms.expense', 'Expense Record', required=False, readonly=True),
        }

# Adding relation between Expense Records and Travels
class tms_travel(osv.osv):
    _inherit="tms.travel"

    _columns = {
        'expense_ids'   : openerp.osv.fields.many2many('tms.expense', 'tms_expense_travel_rel', 'travel_id', 'expense_id', 'Expense Record'),
        'expense_id'    : openerp.osv.fields.many2one('tms.expense', 'Expense Record', required=False, readonly=True),
    }

tms_travel()


# Class for Expense Lines
class tms_expense_line(osv.osv):
    _name = 'tms.expense.line'
    _description = 'Expense Line'

    def _amount_line(self, cr, uid, ids, field_name, args, context=None):
        tax_obj = self.pool.get('account.tax')
        cur_obj = self.pool.get('res.currency')
        res = {}
        if context is None:
            context = {}
        for line in self.browse(cr, uid, ids, context=context):
            price = line.price_unit
            partner_id = self.pool.get('res.users').browse(cr, uid, uid).company_id.partner_id.id
            print partner_id
            addr_id = self.pool.get('res.partner').address_get(cr, uid, [partner_id], ['invoice'])['invoice']


            taxes = tax_obj.compute_all(cr, uid, line.product_id.supplier_taxes_id, price, line.product_uom_qty, addr_id, line.product_id, line.company_id.partner_id)
            cur = line.expense_id.currency_id

            amount_with_taxes = cur_obj.round(cr, uid, cur, taxes['total_included'])
            amount_tax = cur_obj.round(cr, uid, cur, taxes['total_included']) - (cur_obj.round(cr, uid, cur, taxes['total']) or 0.0)
            
            price_subtotal = line.price_unit * line.product_uom_qty
            res[line.id] =  {   'price_subtotal': price_subtotal,
                                'price_total'   : amount_with_taxes,
                                'tax_amount'    : amount_tax,
                                }
        return res


    _columns = {
#        'agreement_id': openerp.osv.fields.many2one('tms.agreement', 'Agreement', required=False, ondelete='cascade', select=True, readonly=True),
        'expense_id': openerp.osv.fields.many2one('tms.expense', 'Expense', required=False, ondelete='cascade', select=True, readonly=True),
        'line_type': openerp.osv.fields.selection([
                                          ('real_expense','Real Expense'),
                                          ('madeup_expense','Made-up Expense'),
                                          ('salary','Salary'),
                                          ('salary_retention','Salary Retention'),
                                          ('salary_discount','Salary Discount'),
                                          ('fuel','Fuel'),
                                    ], 'Line Type', require=True),

        'name': openerp.osv.fields.char('Description', size=256, required=True),
        'sequence': openerp.osv.fields.integer('Sequence', help="Gives the sequence order when displaying a list of sales order lines."),
        'product_id': openerp.osv.fields.many2one('product.product', 'Product', 
                            domain=[('tms_category', 'in', ('expense_real', 'madeup_expense', 'salary','salary_retention' ,'salary_discount'))]),
        'price_unit': openerp.osv.fields.float('Price Unit', required=True, digits_compute= dp.get_precision('Sale Price')),
        'price_subtotal'   : openerp.osv.fields.function(_amount_line, method=True, string='SubTotal', type='float', digits_compute= dp.get_precision('Sale Price'),  store=True, multi='price_subtotal'),
        'price_total'   : openerp.osv.fields.function(_amount_line, method=True, string='Total', type='float', digits_compute= dp.get_precision('Sale Price'),  store=True, multi='price_subtotal'),
        'tax_amount'   : openerp.osv.fields.function(_amount_line, method=True, string='Tax Amount', type='float', digits_compute= dp.get_precision('Sale Price'),  store=True, multi='price_subtotal'),
        'tax_id': openerp.osv.fields.many2many('account.tax', 'waybill_tax', 'waybill_line_id', 'tax_id', 'Taxes'),
        'product_uom_qty': openerp.osv.fields.float('Quantity (UoM)', digits=(16, 2)),
        'product_uom': openerp.osv.fields.many2one('product.uom', 'Unit of Measure '),
        'notes': openerp.osv.fields.text('Notes'),
        'expense_employee_id': openerp.osv.fields.related('expense_id', 'employee_id', type='many2one', relation='res.partner', store=True, string='Driver'),
        'shop_id': openerp.osv.fields.related('expense_id', 'shop_id', type='many2one', relation='sale.shop', string='Shop', store=True, readonly=True),
        'company_id': openerp.osv.fields.related('expense_id', 'company_id', type='many2one', relation='res.company', string='Company', store=True, readonly=True),
        'fuel_voucher': openerp.osv.fields.boolean('Fuel Voucher'),
        'control': openerp.osv.fields.boolean('Control'), # Useful to mark those lines that must not be taken for Expense Record (like Fuel from Fuel Voucher, Toll Stations payed without cash (credit card, voucher, etc)
        'automatic': openerp.osv.fields.boolean('Automatic', help="Check this if you want to create Advances and/or Fuel Vouchers for this line automatically"),
        'credit': openerp.osv.fields.boolean('Credit', help="Check this if you want to create Fuel Vouchers for this line"),
        'fuel_supplier_id': openerp.osv.fields.many2one('res.partner', 'Fuel Supplier', domain=[('tms_category', '=', 'fuel')],  required=False),
    }
    _order = 'sequence'

    _defaults = {
        'line_type'         : 'real_expense',
        'product_uom_qty'   : 1,
        'sequence'          : 10,
        'price_unit'        : 0.0,
    }

    def on_change_product_id(self, cr, uid, ids, product_id):
        res = {}
        if not product_id:
            return {}
        prod_obj = self.pool.get('product.product')
        for product in prod_obj.browse(cr, uid, [product_id], context=None):
            res = {'value': {'product_uom' : product.uom_id.id,
                             'name': product.name,
                             'tax_id': [(6, 0, [x.id for x in product.supplier_taxes_id])],
                            }
                }
        return res

    def on_change_amount(self, cr, uid, ids, product_uom_qty, price_unit, product_id):
        res = {'value': {
                    'price_subtotal': 0.0, 
                    'price_total': 0.0,
                    'tax_amount': 0.0, 
                        }
                }
        if not (product_uom_qty and price_unit and product_id ):
            return res
        tax_factor = 0.00
        prod_obj = self.pool.get('product.product')
        for line in prod_obj.browse(cr, uid, [product_id], context=None)[0].supplier_taxes_id:
            tax_factor = (tax_factor + line.amount) if line.amount <> 0.0 else tax_factor
        price_subtotal = price_unit * product_uom_qty
        res = {'value': {
                    'price_subtotal': price_subtotal, 
                    'tax_amount': price_subtotal * tax_factor, 
                    'price_total': price_subtotal * (1.0 + tax_factor),
                        }
                }
        return res

# Wizard que permite validar la cancelacion de una Liquidacion
class tms_expense_cancel(osv.osv_memory):

    """ To validate Expense Record Cancellation"""

    _name = 'tms.expense.cancel'
    _description = 'Validate Expense Record Cancellation'


    def action_cancel(self, cr, uid, ids, context=None):

        """
             To Validate when cancelling Expense Record
             @param self: The object pointer.
             @param cr: A database cursor
             @param uid: ID of the user currently logged in
             @param context: A standard dictionary
             @return : retrun view of Invoice
        """

        record_id =  context.get('active_ids',[])

        print record_id

        if record_id:
            expense_obj = self.pool.get('tms.expense')
            for expense in expense_obj.browse(cr, uid, record_id):
                cr.execute("select id from tms_expense where state <> 'cancel' and employee_id = " + str(expense.employee_id.id) + " order by date desc limit 1")
                data = filter(None, map(lambda x:x[0], cr.fetchall()))
                if len(data) > 0 and data[0] != expense.id:
                    raise osv.except_osv(
                            _('Could not cancel Expense Record!'),
                            _('This Expense Record is not the last one for driver'))

                print expense.name
                if expense.invoiced and expense.invoice_paid:
                    raise osv.except_osv(
                            _('Could not cancel Expense Record!'),
                            _('This Expense Record\'s is already paid'))
                    return False
                expense_obj.write(cr, uid, record_id, {'state':'cancel', 'cancelled_by':uid,'date_cancelled':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
                travel_ids = []
                for travel in expense.travel_ids:
                    travel_ids.append(travel.id)

                fuelvoucher_obj = self.pool.get('tms.fuelvoucher')
                advance_obj     = self.pool.get('tms.advance')
                travel_obj     = self.pool.get('tms.travel')

                record_ids = fuelvoucher_obj.search(cr, uid, [('travel_id', 'in', (tuple(travel_ids),)),('state','!=', 'cancel')])
                fuelvoucher_obj.write(cr, uid, record_ids, {'expense_id': False, 'state':'confirmed','closed_by':False,'date_closed':False})

                record_ids = advance_obj.search(cr, uid, [('travel_id', 'in', (tuple(travel_ids),)),('state','!=', 'cancel')])
                advance_obj.write(cr, uid, record_ids, {'expense_id': False, 'state':'confirmed','closed_by':False,'date_closed':False})
    
                travel_obj.write(cr, uid, travel_ids, {'expense_id': False, 'state':'done','closed_by':False,'date_closed':False})
        
                

        return {'type': 'ir.actions.act_window_close'}

tms_expense_cancel()



# Wizard que permite generar la factura a pagar correspondiente a la liquidación del Operador

class tms_expense_invoice(osv.osv_memory):

    """ To create invoice for each Expense"""

    _name = 'tms.expense.invoice'
    _description = 'Make Invoices from Expense Records'

    def makeInvoices(self, cr, uid, ids, context=None):

        """
             To get Expense Record and create Invoice
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
            expense_obj=self.pool.get('tms.expense')
            adv_line_obj=self.pool.get('tms.expense.line')

            journal_id = account_jrnl_obj.search(cr, uid, [('type', '=', 'purchase'),('tms_expense_journal','=', 1)], context=None)
            if not journal_id:
                raise osv.except_osv('Error !',
                                 'You have not defined Advance Purchase Journal...')
            journal_id = journal_id and journal_id[0]

            partner = partner_obj.browse(cr,uid,user_obj.browse(cr,uid,[uid])[0].company_id.partner_id.id)


            cr.execute("select distinct employee_id, currency_id from tms_expense where invoice_id is null and state='approved' and id IN %s",(tuple(record_ids),))
            data_ids = cr.fetchall()
            if not len(data_ids):
                raise osv.except_osv('Aviso !',
                                 'Selected records are not Approved or already sent for payment...')
            print data_ids

            for data in data_ids:

                cr.execute("select id from tms_expense where invoice_id is null and state='approved' and employee_id=" + str(data[0]) + ' and currency_id=' + str(data[1]) + " and id IN %s", (tuple(record_ids),))
                expense_ids = filter(None, map(lambda x:x[0], cr.fetchall()))
                
                inv_lines = []
                notes = "Anticipos de Viaje."
                inv_amount = 0.0
                employee_name = ''
                expense_name = ''
                for line in expense_obj.browse(cr,uid,expense_ids):                    
                    a = line.employee_id.tms_expense_account_id.id
                    if not a:
                        raise osv.except_osv(_('Warning !'),
                                _('There is no expense account defined ' \
                                        'for this driver: "%s" (id:%d)') % \
                                        (line.employee_id.name, line.employee_id.id,))
                    a = account_fiscal_obj.map_account(cr, uid, False, a)


                    inv_line = (0,0, {
                        'name': line.product_id.name + ' - ' + line.travel_id.name + ' - ' + line.name,
                        'origin': line.name,
                        'account_id': a,
                        'price_unit': line.total_amount / line.product_uom_qty,
                        'quantity': line.product_uom_qty,
                        'uos_id': line.product_uom.id,
                        'product_id': line.product_id.id,
#                        'invoice_line_tax_id': [(6, 0, [x.id for x in line.product_id.supplier_taxes_id])],
                        'note': line.notes,
                        'account_analytic_id': False,
                        })
                    inv_lines.append(inv_line)
                    inv_amount += line.total_amount
                
                    notes += '\n' + line.name
                    employee_name = line.employee_id.name + ' (' + str(line.employee_id.id) + ')' # + time.strftime(DEFAULT_SERVER_DATE_FORMAT)
                    expense_name = line.name
                    expense_prod = line.product_id.name

                a = partner.property_account_payable.id
                if partner and partner.property_payment_term.id:
                    pay_term = partner.property_payment_term.id
                else:
                    pay_term = False

                inv = {
                    'name'              : 'Advance',
                    'origin'            : 'TMS-Travel Expense Record',
                    'type'              : 'in_invoice',
                    'journal_id'        : journal_id,
                    'reference'         : expense_name + ' -' + employee_name + ' - ' +  expense_prod,
                    'account_id'        : a,
                    'partner_id'        : partner.id,
                    'address_invoice_id': self.pool.get('res.partner').address_get(cr, uid, [partner.id], ['default'])['default'],
                    'address_contact_id': self.pool.get('res.partner').address_get(cr, uid, [partner.id], ['default'])['default'],
                    'invoice_line'      : [x for x in inv_lines],
                    'currency_id'       : data[1],
                    'comment'           : 'TMS-Travel Expense Record',
                    'payment_term'      : pay_term,
                    'fiscal_position'   : partner.property_account_position.id,
                    'comment'           : notes,
                    'check_total'       : inv_amount,
                }

                inv_id = invoice_obj.create(cr, uid, inv)
                if inv_id:
                    wf_service = netsvc.LocalService("workflow")
                    wf_service.trg_validate(uid, 'account.invoice', inv_id, 'invoice_open', cr)

                invoices.append(inv_id)

                expense_obj.write(cr,uid,expense_ids, {'invoice_id': inv_id, 'state':'confirmed', 'confirmed_by':uid, 'date_confirmed':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})               



        return {
            'domain': "[('id','in', ["+','.join(map(str,invoices))+"])]",
            'name': _('Drivers Advances'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'account.invoice',
            'view_id': False,
            'context': "{'type':'in_invoice', 'journal_type': 'purchase'}",
            'type': 'ir.actions.act_window'
        }
tms_expense_invoice()


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
