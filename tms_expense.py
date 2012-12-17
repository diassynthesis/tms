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
    _inherit = ['mail.thread', 'ir.needaction_mixin']
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
                advance += _advance.total

            for _fuelvoucher in expense.fuelvoucher_ids:
                if _fuelvoucher.currency_id.id != cur.id:
                    raise osv.except_osv(
                         _('Currency Error !'), 
                         _('You can not create a Travel Expense Record with Fuel Vouchers with different Currency. This Expense record was created with %s and Fuel Voucher is with %s ') % (expense.currency_id.name, _advance.currency_id.name))
                fuel_voucher += _fuelvoucher.price_subtotal

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
                'amount_balance2'            : cur_obj.round(cr, uid, cur, balance),
                              }

        return res


    _columns = {
        'name': openerp.osv.fields.char('Name', size=64, readonly=True, select=True),
        'shop_id': openerp.osv.fields.many2one('sale.shop', 'Shop', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'company_id': openerp.osv.fields.related('shop_id','company_id',type='many2one',relation='res.company',string='Company',store=True,readonly=True),
        'employee_id': openerp.osv.fields.many2one('hr.employee', 'Driver', required=True, domain=[('tms_category', '=', 'driver')]),
        'employee_id_control': openerp.osv.fields.many2one('hr.employee', 'Driver', required=True, domain=[('tms_category', '=', 'driver')], states={'cancel':[('readonly',True)], 'approved':[('readonly',True)], 'closed':[('readonly',True)]}),
        'travel_ids': openerp.osv.fields.many2many('tms.travel', 'tms_expense_travel_rel', 'expense_id', 'travel_id', 'Travels', readonly=False, states={'confirmed': [('readonly', True)],'closed':[('readonly',True)]}),
        'unit_id': openerp.osv.fields.many2one('fleet.vehicle', 'Unit', required=False, readonly=True),
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

#        'expense_line': openerp.osv.fields.one2many('tms.expense.line', 'expense_id', 'Expense Lines', readonly=False, states={'confirmed': [('readonly', True)],'closed':[('readonly',True)]}),

        'date': openerp.osv.fields.date('Date', required=True, select=True,readonly=False, states={'confirmed': [('readonly', True)],'closed':[('readonly',True)]}),

        'invoice_id': openerp.osv.fields.many2one('account.invoice','Invoice Record', readonly=True),
        'invoiced':  openerp.osv.fields.function(_invoiced, method=True, string='Invoiced', type='boolean', multi='invoiced', store=True),
        'invoice_paid':  openerp.osv.fields.function(_invoiced, method=True, string='Paid', type='boolean', multi='invoiced', store=True),
        'invoice_name':  openerp.osv.fields.function(_invoiced, method=True, string='Invoice', type='char', size=64, multi='invoiced', store=True),

        'expense_line': openerp.osv.fields.one2many('tms.expense.line', 'expense_id', 'Expense Lines', readonly=False, states={'confirmed': [('readonly', True)],'closed':[('readonly',True)]}),


        'amount_real_expense': openerp.osv.fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Expenses', type='float', multi=True),

        'amount_madeup_expense': openerp.osv.fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Fake Expenses', type='float', multi=True), 

        'amount_fuel': openerp.osv.fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Fuel (Cash)', type='float', multi=True),

        'amount_fuel_voucher': openerp.osv.fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Fuel (Voucher)', type='float', multi=True),

        'amount_salary': openerp.osv.fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Salary', type='float', multi=True),

        'amount_net_salary': openerp.osv.fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Net Salary', type='float', multi=True),

        'amount_salary_retention': openerp.osv.fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Salary Retentions', type='float', multi=True),

        'amount_salary_discount': openerp.osv.fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Salary Discounts', type='float', multi=True),

        'amount_advance': openerp.osv.fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Advances', type='float', multi=True),

        'amount_balance': openerp.osv.fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Balance', type='float', multi=True),
        'amount_balance2': openerp.osv.fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Balance', type='float', multi=True, store=True),

        'amount_tax_total': openerp.osv.fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Taxes (All)', type='float', multi=True),

        'amount_tax_real': openerp.osv.fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Taxes (Real)', type='float', multi=True),

        'amount_total_real': openerp.osv.fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Total (Real)', type='float', multi=True),

        'amount_total_total': openerp.osv.fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='Total (All)', type='float', multi=True),

        'amount_subtotal_real': openerp.osv.fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='SubTotal (Real)', type='float', multi=True),

        'amount_subtotal_total': openerp.osv.fields.function(_amount_all, method=True, digits_compute= dp.get_precision('Sale Price'), string='SubTotal (All)', type='float', multi=True),


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
        'move_id': fields.many2one('account.move', 'Journal Entry', readonly=True, select=1, ondelete='restrict', help="Link to the automatically generated Journal Items.\nThis move is only for Travel Expense Records with balance < 0.0"),
        
        'fuelvoucher_ids':openerp.osv.fields.one2many('tms.fuelvoucher', 'expense_id', string='Fuel Vouchers', readonly=True),
        'advance_ids':openerp.osv.fields.one2many('tms.advance', 'expense_id', string='Advances', readonly=True),


    }
    _defaults = {
        'date'              : lambda *a: time.strftime(DEFAULT_SERVER_DATE_FORMAT),
        'expense_policy'    : 'manual',
        'state'             : lambda *a: 'draft',
        'currency_id'       : lambda self,cr,uid,c: self.pool.get('res.users').browse(cr, uid, uid, c).company_id.currency_id.id,
    }
    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Expense record must be unique !'),
    ]

    def _check_units_in_travels(self, cr, uid, ids, context=None):
        for expense in self.browse(cr, uid, ids, context=context):  
            last_unit = False
            first = True
            for travel in expense.travel_ids:
                if not first:
                    if last_unit != travel.unit_id.id:
                        return False
                else:
                    last_unit = travel.unit_id.id
                    first = False
        return True

    _constraints = [
        (_check_units_in_travels, 'You can not create a Travel Expense Record with several units.', ['travel_ids']),
    ]


    _order = 'name desc'


    def on_change_employee_id(self, cr, uid, ids, employee_id, context=None):
        expense_obj = self.pool.get('tms.expense')
        res = expense_obj.search(cr, uid, [('employee_id', '=', employee_id),('state','in', ('draft','approved'))], limit=1)
        if res:
            raise osv.except_osv(
                        _('Warning !'),
                        _('There is already a Travel Expense Record pending to be confirmed. You can not create another Travel Expense record with the same driver !!!'))   
        return {'value': {'employee_id': employee_id}}


    def get_salary_advances_and_fuel_vouchers(self, cr, uid, ids, vals, context=None):  

#        expenses = [x for x in expense_line if 'control' not in x[2] or not x[2]['control']] if expense_line else []

        print vals

        prod_obj = self.pool.get('product.product')

        prod_search = ['salary', 'fuel']
        products = {}
        
        for xprod in prod_search:
            xid = prod_obj.search(cr, uid, [('tms_category', '=', xprod),('active','=', 1)], limit=1)
            if not xid:
                raise osv.except_osv(
                            _('Missing configuration !'),
                            _('There is no product defined as Salary and/or Fuel !!!'))
            for product in prod_obj.browse(cr, uid, xid, context=None):        
                products[xprod] = { 'id': product.id, 'uom': product.uom_id.id, 'name': product.name, 'taxes' : [(6, 0, [x.id for x in product.supplier_taxes_id])], 'category' : product.tms_category }


        qty = amount_untaxed = 0.0

        factor = self.pool.get('tms.factor')
        expense_line_obj = self.pool.get('tms.expense.line')
        expense_obj = self.pool.get('tms.expense')
        travel_obj = self.pool.get('tms.travel')
        fuelvoucher_obj = self.pool.get('tms.fuelvoucher')
        advance_obj     = self.pool.get('tms.advance')

        res = expense_line_obj.search(cr, uid, [('expense_id', '=', ids[0]),('control','=', 1)])
        if len(res):
            res = expense_line_obj.unlink(cr, uid, res)
        salary = fuel = 0.0

        for expense in self.browse(cr, uid, ids):
            currency_id = expense.currency_id.id
            # Quitamos la referencia en caso de que ya existan registros asociados a la Liquidacion
            fuelvoucher_ids = advance_ids = travel_ids = False
            fuelvoucher_ids = fuelvoucher_obj.search(cr, uid, [('expense_id', '=', expense.id)])
            if fuelvoucher_ids:
                fuelvoucher_obj.write(cr, uid, fuelvoucher_ids, {'expense_id': False, 'state':'confirmed', 'closed_by': False,'date_closed': False})

            advance_ids = advance_obj.search(cr, uid, [('expense_id', '=', expense.id)])
            if advance_ids:
                advance_obj.write(cr, uid, advance_ids, {'expense_id': False, 'state':'confirmed', 'closed_by': False, 'date_closed': False})

            travel_ids = travel_obj.search(cr, uid, [('expense_id', '=', expense.id)])
            if travel_ids:
                travel_obj.write(cr, uid, travel_ids, {'expense_id': False, 'state':'done', 'closed_by': False, 'date_closed': False})

            travel_ids = []
            for travel in expense.travel_ids:
                travel_ids.append(travel.id)
                print "Calculando sueldo para el viaje: ", travel.name
                result = factor.calculate(cr, uid, 'expense', False, 'driver', [travel.id])
                salary += result
                xline = {
                        'travel_id'         : travel.id,
                        'expense_id'        : expense.id,
                        'line_type'         : products['salary']['category'],
                        'name'              : products['salary']['name'] + ' - ' + _('Travel: ') + travel.name, 
                        'sequence'          : 1,
                        'product_id'        : products['salary']['id'],
                        'product_uom'       : products['salary']['uom'],
                        'product_uom_qty'   : 1,
                        'price_unit'        : result,
                        'control'           : True,
                        'tax_id'            : products['salary']['taxes']
                        }
                res = expense_line_obj.create(cr, uid, xline)
                
                for fuelvoucher in travel.fuelvoucher_ids:
                    qty             += fuelvoucher.product_uom_qty
                    amount_untaxed  += fuelvoucher.price_subtotal / fuelvoucher.currency_id.rate
                    fuelvoucher_obj.write(cr, uid, [fuelvoucher.id], {'expense_id': expense.id, 'state':'closed','closed_by':uid,'date_closed':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})

                if qty:
                    xline = {
                            'travel_id'         : travel.id,
                            'expense_id'        : expense.id,
                            'line_type'         : products['fuel']['category'],
                            'name'              : products['fuel']['name'] + _(' from Fuel Vouchers - Travel: ') + travel.name,
                            'sequence'          : 5,
                            'product_id'        : products['fuel']['id'],
                            'product_uom'       : products['fuel']['uom'],
                            'product_uom_qty'   : qty,
                            'price_unit'        : amount_untaxed / qty,
                            'control'           : True,
                            'tax_id'            : products['fuel']['taxes'],
                            'fuel_voucher'      : True,
                            }
                    res = expense_line_obj.create(cr, uid, xline)
                for advance in travel.advance_ids:
                    if advance.auto_expense:
                        xline = {
                            'travel_id'         : travel.id,
                            'expense_id'        : expense.id,
                            'line_type'         : advance.product_id.tms_category,
                            'name'              : advance.product_id.name + ' - ' + _('Travel: ') + travel.name, 
                            'sequence'          : 7,
                            'product_id'        : advance.product_id.id,
                            'product_uom'       : advance.product_id.uom_id.id,
                            'product_uom_qty'   : advance.product_uom_qty,
                            'price_unit'        : advance.price_unit,
                            'control'           : True,
                            'tax_id'            : [(6, 0, [x.id for x in advance.product_id.supplier_taxes_id])]
                            }
                        res = expense_line_obj.create(cr, uid, xline)

                    advance_obj.write(cr, uid, [advance.id], {'expense_id': expense.id, 'state':'closed','closed_by':uid,'date_closed':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
                travel_obj.write(cr, uid, [travel.id], {'expense_id': expense.id, 'state':'closed','closed_by':uid,'date_closed':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
        return


    def write(self, cr, uid, ids, vals, context=None):
        print "vals en metodo write:", vals
        super(tms_expense, self).write(cr, uid, ids, vals, context=context)

        if 'state' in vals and vals['state'] not in ('cancel', 'confirmed') :
            print "Antes,,,"
            self.get_salary_advances_and_fuel_vouchers(cr, uid, ids, vals)
            print "Despues,,,"

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

        res = super(tms_expense, self).create(cr, uid, vals, context=context)
        self.get_salary_advances_and_fuel_vouchers(cr, uid, [res], vals)
        return res


    def action_approve(self, cr, uid, ids, context=None):
        for expense in self.browse(cr, uid, ids, context=context):            
            if expense.amount_total_total == 0.0:
                 raise osv.except_osv(
                    _('Could not approve Expense !'),
                    _('Total Amount must be greater than zero.'))
            self.write(cr, uid, ids, {'state':'approved', 'approved_by' : uid, 'date_approved':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
            for (id,name) in self.name_get(cr, uid, ids):
                message = _("Expense '%s' is set to approved.") % name
            self.log(cr, uid, id, message)
        return True


    def action_confirm(self, cr, uid, ids, context=None):
        exp_invoice = self.pool.get('tms.expense.invoice')
        exp_invoice.makeInvoices(cr, uid, ids, context=None)
        for expense in self.browse(cr, uid, ids, context=None):           
            for (id,name) in self.name_get(cr, uid, ids, context=None):
                message = _("Travel Expense Record '%s' is set to confirmed.") % name
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
        'travel_id'        : openerp.osv.fields.many2one('tms.travel', 'Travel', required=False),
        'expense_id'        : openerp.osv.fields.many2one('tms.expense', 'Expense', required=False, ondelete='cascade', select=True, readonly=True),
        'line_type'         : openerp.osv.fields.selection([
                                          ('real_expense','Real Expense'),
                                          ('madeup_expense','Made-up Expense'),
                                          ('salary','Salary'),
                                          ('salary_retention','Salary Retention'),
                                          ('salary_discount','Salary Discount'),
                                          ('fuel','Fuel'),
                                          ('indirect','Indirect'),
                                    ], 'Line Type', require=True),

        'name'              : openerp.osv.fields.char('Description', size=256, required=True),
        'sequence'          : openerp.osv.fields.integer('Sequence', help="Gives the sequence order when displaying a list of sales order lines."),
        'product_id'        : openerp.osv.fields.many2one('product.product', 'Product', 
                                    domain=[('tms_category', 'in', ('expense_real', 'madeup_expense', 'salary','salary_retention' ,'salary_discount'))]),
        'price_unit'        : openerp.osv.fields.float('Price Unit', required=True, digits_compute= dp.get_precision('Sale Price')),
        'price_subtotal'    : openerp.osv.fields.function(_amount_line, method=True, string='SubTotal', type='float', digits_compute= dp.get_precision('Sale Price'),  store=True, multi='price_subtotal'),
        'price_total'       : openerp.osv.fields.function(_amount_line, method=True, string='Total', type='float', digits_compute= dp.get_precision('Sale Price'),  store=True, multi='price_subtotal'),
        'tax_amount'        : openerp.osv.fields.function(_amount_line, method=True, string='Tax Amount', type='float', digits_compute= dp.get_precision('Sale Price'),  store=True, multi='price_subtotal'),
        'special_tax_amount': openerp.osv.fields.float('Special Tax', required=False, digits_compute= dp.get_precision('Sale Price')),
        'tax_id'            : openerp.osv.fields.many2many('account.tax', 'expense_tax', 'tms_expense_line_id', 'tax_id', 'Taxes'),
        'product_uom_qty'   : openerp.osv.fields.float('Quantity (UoM)', digits=(16, 2)),
        'product_uom'       : openerp.osv.fields.many2one('product.uom', 'Unit of Measure '),
        'notes'             : openerp.osv.fields.text('Notes'),
        'expense_employee_id': openerp.osv.fields.related('expense_id', 'employee_id', type='many2one', relation='res.partner', store=True, string='Driver'),
        'shop_id'           : openerp.osv.fields.related('expense_id', 'shop_id', type='many2one', relation='sale.shop', string='Shop', store=True, readonly=True),
        'company_id'        : openerp.osv.fields.related('expense_id', 'company_id', type='many2one', relation='res.company', string='Company', store=True, readonly=True),
        'fuel_voucher'      : openerp.osv.fields.boolean('Fuel Voucher'),

        'control'           : openerp.osv.fields.boolean('Control'), # Useful to mark those lines that must not be taken for Expense Record (like Fuel from Fuel Voucher, Toll Stations payed without cash (credit card, voucher, etc)
        'automatic'         : openerp.osv.fields.boolean('Automatic', help="Check this if you want to create Advances and/or Fuel Vouchers for this line automatically"),
        'credit'            : openerp.osv.fields.boolean('Credit', help="Check this if you want to create Fuel Vouchers for this line"),
        'fuel_supplier_id'  : openerp.osv.fields.many2one('res.partner', 'Fuel Supplier', domain=[('tms_category', '=', 'fuel')],  required=False),
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

#    def unlink(self, cr, uid, ids, context=None):
#        for line in self.browse(cr, uid, ids):
#            print line
#            if line.control:
#                raise osv.except_osv(
#                        _('Warning!'),
#                        _('You can not delete expense lines that are created automatically (Salary & Fuel Vouchers) !!! Click Cancel button to continue.'))

#        super(tms_expense_line, self).unlink(cr, uid, ids, context=context)
#        return True

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


                if expense.invoiced and expense.invoice_paid:
                    raise osv.except_osv(
                            _('Could not cancel Expense Record!'),
                            _('This Expense Record\'s is already paid'))
                    return False
                elif expense.invoiced and not expense.invoice_paid:
                    wf_service = netsvc.LocalService("workflow")
                    wf_service.trg_validate(uid, 'account.invoice', expense.invoice_id.id, 'invoice_cancel', cr)               
                    invoice_obj=self.pool.get('account.invoice')
                    invoice_obj.write(cr,uid,[expense.invoice_id.id], {'internal_number':False})
                    invoice_obj.unlink(cr, uid, [expense.invoice_id.id], context=None)



                expense_obj.write(cr, uid, record_id, {'state':'cancel', 'cancelled_by':uid,'date_cancelled':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT), 'invoice_id': False, 'move_id': False})
                if expense.move_id.id:                
                    move_obj = self.pool.get('account.move')
                    if expense.move_id.state != 'draft':
                        move_obj.button_cancel(cr, uid, [expense.move_id.id]) 
                    move_obj.unlink(cr, uid, [expense.move_id.id])



                travel_ids = []
                for travel in expense.travel_ids:
                    travel_ids.append(travel.id)

                fuelvoucher_obj = self.pool.get('tms.fuelvoucher')
                advance_obj     = self.pool.get('tms.advance')
                travel_obj     = self.pool.get('tms.travel')

                record_ids = fuelvoucher_obj.search(cr, uid, [('travel_id', 'in', tuple(travel_ids),), ('state','!=', 'cancel')])
                fuelvoucher_obj.write(cr, uid, record_ids, {'expense_id': False, 'state':'confirmed','closed_by':False,'date_closed':False})

                record_ids = advance_obj.search(cr, uid, [('travel_id', 'in', tuple(travel_ids),),('state','!=', 'cancel')])
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
#            expense_line_obj=self.pool.get('tms.expense.line')
            period_obj = self.pool.get('account.period')
            move_obj = self.pool.get('account.move')


            journal_id = account_jrnl_obj.search(cr, uid, [('type', '=', 'purchase'),('tms_expense_journal','=', 1)], context=None)
            if not journal_id:
                raise osv.except_osv('Error !',
                                 'You have not defined Travel Expense Purchase Journal...')
            journal_id = journal_id and journal_id[0]




            partner = partner_obj.browse(cr,uid,user_obj.browse(cr,uid,[uid])[0].company_id.partner_id.id)
            cr.execute("select distinct employee_id, currency_id from tms_expense where invoice_id is null and state='approved' and id IN %s",(tuple(record_ids),))
            data_ids = cr.fetchall()
            if not len(data_ids):
                raise osv.except_osv('Warning !',
                                 'Selected records are not Approved or already sent for payment...')
            print data_ids

            for data in data_ids:

                expenses_ids = expense_obj.search(cr, uid, [('state','=','approved'),('employee_id','=', data[0]), ('currency_id','=', data[1]), ('id','in', tuple(record_ids),)])

                for expense in expense_obj.browse(cr, uid, expenses_ids):

                    period_id = period_obj.search(cr, uid, [('date_start', '<=', expense.date),('date_stop','>=', expense.date), ('state','=','draft')], context=None)
                    if not period_id:
                        raise osv.except_osv(_('Warning !'),
                                _('There is no valid account period for this date %s. Period does not exists or is already closed') % \
                                        (expense.date,))


                    advance_account = expense.employee_id.tms_advance_account_id.id
                    negative_balance_account = expense.employee_id.tms_expense_negative_balance_account_id.id
                    if not (expense.employee_id.tms_advance_account_id.id and expense.employee_id.tms_expense_negative_balance_account_id.id):
                        raise osv.except_osv(_('Warning !'),
                                _('There is no advance account and/or Travel Expense Negative Balance account defined ' \
                                        'for this driver: "%s" (id:%d)') % \
                                        (expense.employee_id.name, expense.employee_id.id,))
                    advance_account = account_fiscal_obj.map_account(cr, uid, False, advance_account)
                    negative_balance_account = account_fiscal_obj.map_account(cr, uid, False, negative_balance_account)


                    if expense.amount_balance > 0.0:
                        inv_lines = []
                        notes = _("Travel Expense Record ")
                        inv_amount = 0.0

                        if expense.amount_advance:
                            

                            inv_line = (0,0, {
                                    'name'          : _('Advance Discount'),
                                    'origin'        : _('Advance Discount'),
                                    'account_id'    : advance_account,
                                    'price_unit'    : expense.amount_advance * -1.0,
                                    'quantity'      : 1,
                                    'uos_id'        : 1,
#                                    'product_id'    : False,
                                    'invoice_line_tax_id': [],
                                    'note'          : _('Advance Discount'),
                                    'account_analytic_id': False,
                                    })
                            inv_lines.append(inv_line)
                            inv_amount += expense.amount_advance * -1.0
                            notes += '\n' + _('Advance Discount')

                        for line in expense.expense_line:                    

                            prod_account = negative_balance_account if line.product_id.tms_category == 'negative_balance' else line.product_id.property_account_expense.id if line.product_id.property_account_expense.id else line.product_id.categ_id.property_account_expense_categ.id if line.product_id.categ_id.property_account_expense_categ.id else False
                            if not prod_account:
                                raise osv.except_osv(_('Warning !'),
                                        _('Expense Account is not defined for product %s (id:%d)') % \
                                            (line.product_id.name, line.product_id.id,))


                            if line.line_type != ('madeup_expense') and not line.fuel_voucher:
                                inv_line = (0,0, {
                                    'name': line.product_id.name + ' - ' + line.expense_id.name + ' - ' + line.name,
                                    'origin': line.name,
                                    'account_id': account_fiscal_obj.map_account(cr, uid, False, prod_account),
                                    'price_unit': line.price_subtotal / line.product_uom_qty,
                                    'quantity': line.product_uom_qty,
                                    'uos_id': line.product_uom.id,
                                    'product_id': line.product_id.id,
                                    'invoice_line_tax_id': [(6, 0, [x.id for x in line.product_id.supplier_taxes_id])],
                                    'note': line.notes,
                                    'account_analytic_id': False,
                                    })
                                inv_lines.append(inv_line)
                                inv_amount += line.price_total
                        
                                notes += '\n' + line.name
                        
                        a = partner.property_account_payable.id
                        if partner and partner.property_payment_term.id:
                            pay_term = partner.property_payment_term.id
                        else:
                            pay_term = False

                        inv = {
                            'name'              : _('Expense Record'),
                            'origin'            : _('TMS-Travel Expense Record'),
                            'type'              : 'in_invoice',
                            'journal_id'        : journal_id,
                            'period_id'         : period_id[0],
                            'reference'         : expense.name + ' -' + expense.employee_id.name + ' (' + str(expense.employee_id.id) + ')', 
                            'account_id'        : a,
                            'partner_id'        : partner.id,
                            'address_invoice_id': self.pool.get('res.partner').address_get(cr, uid, [partner.id], ['default'])['default'],
                            'address_contact_id': self.pool.get('res.partner').address_get(cr, uid, [partner.id], ['default'])['default'],
                            'invoice_line'      : [x for x in inv_lines],
                            'currency_id'       : data[1],
                            'comment'           : _('TMS-Travel Expense Record'),
                            'payment_term'      : pay_term,
                            'fiscal_position'   : partner.property_account_position.id,
                            'comment'           : notes,
                            'check_total'       : inv_amount,
                            'date_invoice'      : expense.date,
                            }

                        inv_id = invoice_obj.create(cr, uid, inv)
                        if inv_id:
                            wf_service = netsvc.LocalService("workflow")
                            wf_service.trg_validate(uid, 'account.invoice', inv_id, 'invoice_open', cr)
                            for new_inv in self.pool.get('account.invoice').browse(cr, uid, [inv_id]):
                                invoice_name = new_inv.name                            

                        invoices.append(inv_id)
                        expense_obj.write(cr,uid,[expense.id], {'invoice_id': inv_id, 'state':'confirmed', 'confirmed_by':uid, 'date_confirmed':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})               
                        expense_obj.message_post(cr, uid, [expense.id], body=_("Invoice %s is waiting to be paid</b>.") % (invoice_name), context=context)

                    else: # El operador quedó a deber o salio tablas (cero), se tiene que generar la póliza contable correspondiente.
                        move_lines = []
 
                        notes = _("Travel Expense Record ")

                        if expense.amount_advance:
                            move_line = (0,0, {
                                    'name'          : _('Advance Discount'),
                                    'account_id'    : advance_account,
                                    'debit'         : 0.0,
                                    'credit'        : expense.amount_advance,
                                    'journal_id'    : journal_id,
                                    'period_id'     : period_id[0],
                                    })
                            move_lines.append(move_line)
                            notes += '\n' + _('Advance Discount')

                        for line in expense.expense_line:
                            if line.line_type != ('madeup_expense') and not line.fuel_voucher:
                                prod_account = negative_balance_account if line.product_id.tms_category == 'negative_balance' else line.product_id.property_account_expense.id if line.product_id.property_account_expense.id else line.product_id.categ_id.property_account_expense_categ.id if line.product_id.categ_id.property_account_expense_categ.id else False
                                if not prod_account:
                                    raise osv.except_osv(_('Warning !'),
                                            _('Expense Account is not defined for product %s (id:%d)') % \
                                                (line.product_id.name, line.product_id.id,))

                                move_line = (0,0, {
                                    'name'              : expense.name + ' - ' + ' - '  + line.name + ' (' + str(line.product_id.id) + ') - ' + expense.employee_id.name + ' (' + str(expense.employee_id.id) + ')',
                                    'product_id'        : line.product_id.id,
                                    'product_uom_id'    : line.product_uom.id,
                                    'account_id'        : account_fiscal_obj.map_account(cr, uid, False, prod_account),
                                    'debit'             : line.price_subtotal if line.price_subtotal > 0.0 else 0.0,
                                    'credit'            : abs(line.price_subtotal) if line.price_subtotal <= 0.0 else 0.0,
                                    'quantity'          : line.product_uom_qty,
                                    'journal_id'        : journal_id,
                                    'period_id'         : period_id[0],
                                    })
                                move_lines.append(move_line)
                                notes += '\n' + line.name
                                for tax in line.tax_id:
                                    tax_account = tax.account_collected_id.id
                                    if not tax_account:
                                        raise osv.except_osv(_('Warning !'),
                                                _('Tax Account is not defined for Tax %s (id:%d)') % \
                                                    (tax.name, tax.id,))
                                    tax_amount = line.price_subtotal * amount
                                    move_lines = (0,0, {
                                        'name'              : expense.name + ' - ' + tax.name + ' - ' + line.name + ' - ' + line.employee_id.name + ' (' + line.employee_id.id + ')',
#                                        'product_id'        : line.product_id.id,
#                                        'product_uom_id'    : line.product_uom.id,
                                        'account_id'        : account_fiscal_obj.map_account(cr, uid, False, tax_account),
                                        'debit'             : tax_amount if tax_amount > 0.0 else 0.0,
                                        'credit'            : abs(tax_amount) if tax_amount <= 0.0 else 0.0,
                                        'account_tax_id'    : tax.id,
                                        'tax_amount'        : tax_amount,
                                        'tax_code_id'       : tax.tax_code_id.id,
                                        'journal_id'        : journal_id,
                                        'period_id'         : period_id[0],
                                        })
                                    move_line.append(inv_line)

                        if expense.amount_balance:
                            move_line = (0,0, {
                                        'name'          : _('Debit Balance'),
                                        'account_id'    : advance_account,
                                        'debit'         : expense.amount_balance * -1.0,
                                        'credit'        : 0.0,
                                        'journal_id'    : journal_id,
                                        'period_id'     : period_id[0],
                                        })
                            move_lines.append(move_line)
                            notes += '\n' + _('Debit Balance')

                        print "move_lines: \n", move_lines
                        move = {
                            'ref'               : expense.name,
                            'journal_id'        : journal_id,
                            'narration'         : _('TMS-Travel Expense Record') + ' - ' + expense.name + ' - ' + expense.employee_id.name + ' (' + str(expense.employee_id.id) + ')',
                            'line_id'         : [x for x in move_lines],
                            'date'              : expense.date,
                            'period_id'         : period_id[0],
                            }
                        print "move: \n", move
                        move_id = move_obj.create(cr, uid, move)
                        if move_id:
                            move_obj.button_validate(cr, uid, [move_id])                            

                        expense_obj.write(cr,uid,[expense.id], {'move_id': move_id, 'state':'confirmed', 'confirmed_by':uid, 'date_confirmed':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})               



        return {}

tms_expense_invoice()


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
