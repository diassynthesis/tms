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


# Trip Fuel Vouchers

class tms_fuelvoucher(osv.osv):
    _name ='tms.fuelvoucher'
    _description = 'Fuel Vouchers'

    def _invoiced(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        invoiced = paid = name = False
        for record in self.browse(cr, uid, ids, context=context):
            if (record.invoice_id.id):                
                invoiced = True
                paid = (record.invoice_id.state == 'paid')
                name = record.invoice_id.reference
            res[record.id] =  { 'invoiced': invoiced,
                                'invoice_paid': paid,
                                'invoice_name': name 
                                }
        return res

    def _amount_calculation(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        for record in self.browse(cr, uid, ids, context=context):        
            tax_factor = 0.00
            for line in record.product_id.supplier_taxes_id:
                tax_factor = (tax_factor + line.amount) if line.amount <> 0.0 else tax_factor
            if (record.tax_amount) and tax_factor == 0.00:
                raise osv.except_osv(_('No taxes defined in product !'), _('You have to add taxes for this product. Para Mexico: Tiene que agregar el IVA que corresponda y el IEPS con factor 0.0.'))

            subtotal = (record.tax_amount / tax_factor) if tax_factor <> 0.0 else record.price_total
            special_tax_amount = (record.price_total - subtotal - record.tax_amount) if tax_factor else 0.0
            price_unit = subtotal / record.product_uom_qty
            res[record.id] =   {'price_subtotal': subtotal,
                                'special_tax_amount': special_tax_amount,
                                'price_unit': price_unit,
                                }
        return res

    
    _columns = {
        'name': openerp.osv.fields.char('Fuel Voucher', size=64, required=False),
        'state': openerp.osv.fields.selection([('draft','Draft'), ('approved','Approved'), ('confirmed','Confirmed'), ('closed','Closed'), ('cancel','Cancelled')], 'State', readonly=True),
        'date': openerp.osv.fields.date('Date', states={'cancel':[('readonly',True)], 'confirmed':[('readonly',True)],'closed':[('readonly',True)]}, required=True),
        'travel_id':openerp.osv.fields.many2one('tms.travel', 'Travel', required=True, states={'cancel':[('readonly',True)], 'confirmed':[('readonly',True)],'closed':[('readonly',True)]}),
        'unit_id': openerp.osv.fields.related('travel_id', 'unit_id', type='many2one', relation='tms.unit', string='Unit', store=True, readonly=True),                
        'employee_id': openerp.osv.fields.related('travel_id', 'employee_id', type='many2one', relation='hr.employee', string='Driver', store=True, readonly=True),                
        'shop_id': openerp.osv.fields.related('travel_id', 'shop_id', type='many2one', relation='sale.shop', string='Shop', store=True, readonly=True),                
        'partner_id': openerp.osv.fields.many2one('res.partner', 'Fuel Supplier', domain=[('tms_category', '=', 'fuel')],  required=True, states={'cancel':[('readonly',True)], 'confirmed':[('readonly',True)],'closed':[('readonly',True)]}),
        'product_id': openerp.osv.fields.many2one('product.product', 'Product', domain=[('purchase_ok', '=', True),('tms_category','=','fuel')],  required=True, states={'cancel':[('readonly',True)], 'confirmed':[('readonly',True)],'closed':[('readonly',True)]}),
        'product_uom_qty': openerp.osv.fields.float('Quantity', digits=(16, 4), required=True, states={'cancel':[('readonly',True)], 'confirmed':[('readonly',True)],'closed':[('readonly',True)]}),
        'product_uom': openerp.osv.fields.many2one('product.uom', 'UoM ', required=True),
        'price_unit': openerp.osv.fields.function(_amount_calculation, method=True, string='Unit Price', type='float', digits_compute= dp.get_precision('Sale Price'), multi='price_unit', store=True),
        'price_subtotal': openerp.osv.fields.function(_amount_calculation, method=True, string='SubTotal', type='float', digits_compute= dp.get_precision('Sale Price'), multi='price_unit', store=True),
        'tax_amount': openerp.osv.fields.float('Taxes', required=True, digits_compute= dp.get_precision('Sale Price'), states={'cancel':[('readonly',True)], 'confirmed':[('readonly',True)],'closed':[('readonly',True)]}),
        'special_tax_amount' : openerp.osv.fields.function(_amount_calculation, method=True, string='IEPS', type='float', digits_compute= dp.get_precision('Sale Price'), multi='price_unit', store=True),
        'price_total': openerp.osv.fields.float('Total', required=True, digits_compute= dp.get_precision('Sale Price'), states={'cancel':[('readonly',True)], 'confirmed':[('readonly',True)],'closed':[('readonly',True)]}),
        'notes': openerp.osv.fields.text('Notes', states={'cancel':[('readonly',True)], 'confirmed':[('readonly',True)],'closed':[('readonly',True)]}),

        'create_uid' : openerp.osv.fields.many2one('res.users', 'Created by', readonly=True),
        'create_date': openerp.osv.fields.datetime('Creation Date', readonly=True, select=True),        
        'cancelled_by' : openerp.osv.fields.many2one('res.users', 'Cancelled by', readonly=True),
        'date_cancelled': openerp.osv.fields.datetime('Date Cancelled', readonly=True),
        'approved_by' : openerp.osv.fields.many2one('res.users', 'Approved by', readonly=True),
        'date_approved': openerp.osv.fields.datetime('Date Approved', readonly=True),
        'confirmed_by' : openerp.osv.fields.many2one('res.users', 'Confirmed by', readonly=True),
        'date_confirmed': openerp.osv.fields.datetime('Date Confirmed', readonly=True),
        'closed_by' : openerp.osv.fields.many2one('res.users', 'Closed by', readonly=True),
        'date_closed': openerp.osv.fields.datetime('Date Closed', readonly=True),
        'drafted_by' : openerp.osv.fields.many2one('res.users', 'Drafted by', readonly=True),
        'date_drafted': openerp.osv.fields.datetime('Date Drafted', readonly=True),
        'invoice_id': openerp.osv.fields.many2one('account.invoice','Invoice Record', readonly=True, domain=[('state', '!=', 'cancel')],),
        'invoiced':  openerp.osv.fields.function(_invoiced, method=True, string='Invoiced', type='boolean', multi='invoiced'),               
        'invoice_paid':  openerp.osv.fields.function(_invoiced, method=True, string='Paid', type='boolean', multi='invoiced'),
        'invoice_name':  openerp.osv.fields.function(_invoiced, method=True, string='Invoice', type='char', size=64, multi='invoiced', store=True),
        'currency_id': openerp.osv.fields.many2one('res.currency', 'Currency', required=True, states={'cancel':[('readonly',True)], 'confirmed':[('readonly',True)],'closed':[('readonly',True)]}),
        }
    
    _defaults = {
        'date': lambda *a: time.strftime(DEFAULT_SERVER_DATE_FORMAT),
        'state': 'draft',
        'currency_id': lambda self,cr,uid,c: self.pool.get('res.users').browse(cr, uid, uid, c).company_id.currency_id.id,
        }
    
    _sql_constraints = [
        ('name_uniq', 'unique(partner_id,name)', 'Fuel Voucher number must be unique !'),
        ]
    _order = "name desc, date desc"


    def on_change_product_id(self, cr, uid, ids, product_id):
        res = {}
        if not product_id:
            return {}
        prod_obj = self.pool.get('product.product')
        return {'value': {'product_uom' : prod_obj.browse(cr, uid, [product_id], context=None)[0].uom_id.id }}

    def on_change_travel_id(self, cr, uid, ids, travel_id):
        res = {}
        if not travel_id:
            return {}
        travel_obj = self.pool.get('tms.travel')
        return {'value': {'employee_id' : travel_obj.browse(cr, uid, [travel_id], context=None)[0].employee_id.id,
                          'unit_id' : travel_obj.browse(cr, uid, [travel_id], context=None)[0].unit_id.id,  }               }


    def on_change_amount(self, cr, uid, ids, product_uom_qty, price_total, tax_amount, product_id):
        res = {'value': {'price_unit': 0.0, 'price_subtotal': 0.0, 'special_tax_amount': 0.0}}
        if not (product_uom_qty and price_total and product_id):
            return res
        tax_factor = 0.00
        prod_obj = self.pool.get('product.product')
        for line in prod_obj.browse(cr, uid, [product_id], context=None)[0].supplier_taxes_id:
            tax_factor = (tax_factor + line.amount) if line.amount <> 0.0 else tax_factor
        if (tax_amount) and tax_factor == 0.00:
            raise osv.except_osv(_('No taxes defined in product !'), _('You have to add taxes for this product. Para Mexico: Tiene que agregar el IVA que corresponda y el IEPS con factor 0.0.'))        
        subtotal = (tax_amount / tax_factor) if tax_factor <> 0.0 else price_total
        special_tax = (price_total - subtotal - tax_amount) if tax_factor else 0.0
        return {'value': {'price_unit': (subtotal / product_uom_qty), 'price_subtotal': subtotal, 'special_tax_amount': special_tax}}
                
    def create(self, cr, uid, vals, context=None):
        travel = self.pool.get('tms.travel').browse(cr, uid, vals['travel_id'])
        shop_id = travel.shop_id.id
        supplier_seq_id = self.pool.get('tms.sale.shop.fuel.supplier.seq').search(cr, uid, [('shop_id', '=', shop_id),('partner_id', '=', vals['partner_id'])])
        if supplier_seq_id:
            seq_id = self.pool.get('tms.sale.shop.fuel.supplier.seq').browse(cr, uid, supplier_seq_id)[0].fuel_sequence.id
        else:
            raise osv.except_osv(
                                 _('Fuel Voucher Sequence Error !'), 
                                 _('You have not defined Fuel Voucher Sequence for shop ' + shop.name + ' and Supplier' + str(vals['partner_id'])))
        if seq_id:
            seq_number = self.pool.get('ir.sequence').get_id(cr, uid, seq_id)
            vals['name'] = seq_number
        else:
            raise osv.except_osv(_('Fuel Voucher Sequence Error !'), _('You have not defined Fuel Voucher Sequence for shop ' + shop.name))
        return super(tms_fuelvoucher, self).create(cr, uid, vals, context=context)


    def action_cancel_draft(self, cr, uid, ids, *args):
        if not len(ids):
            return False
        for fuelvoucher in self.browse(cr, uid, ids):
            if fuelvoucher.travel_id.state in ('cancel', 'closed'):
                raise osv.except_osv(
                        _('Could not set to draft this Fuel Voucher !'),
                        _('Travel is Closed or Cancelled !!!'))
            else:
                self.write(cr, uid, ids, {'state':'draft','drafted_by':uid,'date_drafted':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
        for (id,name) in self.name_get(cr, uid, ids):
            message = _("Fuel Voucher '%s' has been set in draft state.") % name
            self.log(cr, uid, id, message)
        return True
    
    def action_cancel(self, cr, uid, ids, context=None):
        for fuelvoucher in self.browse(cr, uid, ids, context=context):
            if fuelvoucher.invoiced:
                raise osv.except_osv(
                        _('Could not cancel Fuel Voucher !'),
                        _('This Fuel Voucher is already Invoiced'))
            elif fuelvoucher.travel_id.state in ('closed'):
                raise osv.except_osv(
                        _('Could not cancel Fuel Voucher !'),
                        _('This Fuel Voucher is already linked to Travel Expenses record'))
            self.write(cr, uid, ids, {'state':'cancel', 'invoice_id':False, 'cancelled_by':uid,'date_cancelled':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
            for (id,name) in self.name_get(cr, uid, ids):
                message = _("Fuel Voucher '%s' is cancelled.") % name
            self.log(cr, uid, id, message)
        return True

    def action_approve(self, cr, uid, ids, context=None):
        for fuelvoucher in self.browse(cr, uid, ids, context=context):
            if fuelvoucher.state in ('draft'):
                self.write(cr, uid, ids, {'state':'approved', 'approved_by' : uid, 'date_approved':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
                for (id,name) in self.name_get(cr, uid, ids):
                    message = _("Fuel Voucher '%s' is set to approve.") % name
                self.log(cr, uid, id, message)
        return True

    def action_confirm(self, cr, uid, ids, context=None):
        for fuelvoucher in self.browse(cr, uid, ids, context=context):
            if fuelvoucher.product_uom_qty <= 0.0:
                 raise osv.except_osv(
                        _('Could not confirm Fuel Voucher !'),
                        _('Product quantity must be greater than zero.'))

            self.write(cr,uid,ids,{'state':'confirmed', 'confirmed_by':uid, 'date_confirmed':time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)})
            for (id,name) in self.name_get(cr, uid, ids):
                message = _("Fuel Voucher '%s' is set to confirmed.") % name
                self.log(cr, uid, id, message)
        return True

    def copy(self, cr, uid, id, default=None, context=None):
        default = default or {}
        default.update({
            'cancelled_by' : False,
            'date_cancelled': False,
            'approved_by' : False,
            'date_approved': False,
            'confirmed_by' : False,
            'date_confirmed': False,
            'closed_by' : False,
            'date_closed': False,
            'drafted_by' : False,
            'date_drafted': False,
            'invoice_id': False,
            'notes': False,
        })
        return super(tms_fuelvoucher, self).copy(cr, uid, id, default, context)


tms_fuelvoucher()

# Wizard que permite conciliar los Vales de combustible en una factura

class tms_fuelvoucher_invoice(osv.osv_memory):

    """ To create invoice for each Fuel Voucher"""

    _name = 'tms.fuelvoucher.invoice'
    _description = 'Make Invoices from Fuel Vouchers'

    def makeInvoices(self, cr, uid, ids, context=None):

        """
             To get Fuel Voucher and create Invoice
             @param self: The object pointer.
             @param cr: A database cursor
             @param uid: ID of the user currently logged in
             @param context: A standard dictionary
             @return : retrun view of Invoice
        """

        if context is None:
            context={}

        record_ids =  context.get('active_ids',[])
        if record_ids:
            res = False
            invoices = []
            property_obj=self.pool.get('ir.property')
            partner_obj=self.pool.get('res.partner')
            account_fiscal_obj=self.pool.get('account.fiscal.position')
            invoice_line_obj=self.pool.get('account.invoice.line')
            account_jrnl_obj=self.pool.get('account.journal')
            invoice_obj=self.pool.get('account.invoice')
            fuelvoucher_obj=self.pool.get('tms.fuelvoucher')

            journal_id = account_jrnl_obj.search(cr, uid, [('type', '=', 'purchase')], context=None)
            journal_id = journal_id and journal_id[0] or False

            cr.execute("select distinct partner_id, currency_id from tms_fuelvoucher where invoice_id is null and state='confirmed' and id IN %s",(tuple(record_ids),))

            data_ids = cr.fetchall()
            if not len(data_ids):
                raise osv.except_osv(_('Aviso !'),
                                 _('Selected records are not Confirmed or already invoiced...'))
            print data_ids

            for data in data_ids:
                partner = partner_obj.browse(cr,uid,data[0])

                cr.execute("select id from tms_fuelvoucher where invoice_id is null and state='confirmed' and partner_id=" + str(data[0]) + ' and currency_id=' + str(data[1]) + " and id IN %s", (tuple(record_ids),))
                fuelvoucher_ids = filter(None, map(lambda x:x[0], cr.fetchall()))
                
                inv_lines = []
                notes = "Conciliacion de Vales de Combustible. "
                for line in fuelvoucher_obj.browse(cr,uid,fuelvoucher_ids):
                    if (not line.invoiced) and (line.state not in ('draft','approved','cancel')):                      
                        if line.product_id:
                            a = line.product_id.product_tmpl_id.property_account_expense.id
                            if not a:
                                a = line.product_id.categ_id.property_account_expense_categ.id
                            if not a:
                                raise osv.except_osv(_('Error !'),
                                        _('There is no expense account defined ' \
                                                'for this product: "%s" (id:%d)') % \
                                                (line.product_id.name, line.product_id.id,))
                        else:
                            a = property_obj.get(cr, uid,
                                    'property_account_expense_categ', 'product.category',
                                    context=context).id

                    a = account_fiscal_obj.map_account(cr, uid, False, a)
                    inv_line = (0,0, {
                        'name': line.product_id.name + ' - ' + line.travel_id.name + ' - ' + line.name,
                        'origin': line.name,
                        'account_id': a,
                        'price_unit': line.price_unit,
                        'quantity': line.product_uom_qty,
                        'uos_id': line.product_uom.id,
                        'product_id': line.product_id.id,
                        'invoice_line_tax_id': [(6, 0, [x.id for x in line.product_id.supplier_taxes_id])],
                        'note': line.notes,
                        'account_analytic_id': False,
                        })
                    inv_lines.append(inv_line)
                
                    notes += '\n' + line.name

                a = partner.property_account_payable.id
                if partner and partner.property_payment_term.id:
                    pay_term = partner.property_payment_term.id
                else:
                    pay_term = False

                inv = {
                    'name'              : 'Fact.Pendiente',
                    'origin'            : 'TMS-Fuel Voucher',
                    'type'              : 'in_invoice',
                    'journal_id'        : journal_id,
                    'reference'         : 'TMS-Vales de Comb',
                    'account_id'        : a,
                    'partner_id'        : partner.id,
                    'address_invoice_id': self.pool.get('res.partner').address_get(cr, uid, [partner.id], ['default'])['default'],
                    'address_contact_id': self.pool.get('res.partner').address_get(cr, uid, [partner.id], ['default'])['default'],
                    'invoice_line'      : [x for x in inv_lines],
                    'currency_id'       : data[1],
                    'comment'           : 'TMS-Conciliacion de Vales de Combustible',
                    'payment_term'      : pay_term,
                    'fiscal_position'   : partner.property_account_position.id,
                    'comment'           : notes,
                }



                inv_id = invoice_obj.create(cr, uid, inv)
                invoices.append(inv_id)

                fuelvoucher_obj.write(cr,uid,fuelvoucher_ids, {'invoice_id': inv_id})               

        return {
            'domain': "[('id','in', ["+','.join(map(str,invoices))+"])]",
            'name': _('Supplier Invoices'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'account.invoice',
            'view_id': False,
            'context': "{'type':'in_invoice', 'journal_type': 'purchase'}",
            'type': 'ir.actions.act_window'
        }
tms_fuelvoucher_invoice()



# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

